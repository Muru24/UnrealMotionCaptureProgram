"""Local Full model, full-frame VIDEO inference and conservative target selection.

Primary inference uses fixed full-frame coordinates. A short detection gap can
retry the last target crop with exact image-coordinate/depth remapping.
MediaPipe's internal tracking does not choose the user's identity; TargetTracker
selects one observed candidate and rejects ambiguity or a long disappearance.
"""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from core.pose2d.interface import Keypoint2D, Pose2DResult
from core.pose2d.tracker import TargetTracker, box_iou
from .interface import (COCO_TO_MP, LANDMARK33, Landmark3D, Pose3DError,
                        Pose3DResult, missing_landmarks)
from .observations import mask_support, same_foreground, shared_previous_observation


MODEL_SHA256 = '5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1'


def validate_model(directory: Path) -> Path:
    directory = Path(directory)
    if str(directory).startswith(('\\\\', '//')) or '://' in str(directory):
        raise Pose3DError('Model directory must be local.')
    if directory.is_symlink() or any(p.is_symlink() for p in directory.parents):
        raise Pose3DError('Model symbolic links are not supported.')
    try:
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8-sig'))
        if manifest['file'] != 'pose_landmarker_full.task' or manifest['sha256'] != MODEL_SHA256:
            raise Pose3DError('Unsupported M2 model manifest. Expected the approved Full v1 task.')
        path = directory / manifest['file']
        if path.is_symlink() or not path.is_file():
            raise Pose3DError('Local Full task is missing. See models/pose3d/README.md.')
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != MODEL_SHA256:
            raise Pose3DError('Full model integrity check failed.')
        return path.resolve()
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise Pose3DError('Cannot read local Full model or manifest.') from exc


def finite_or_none(value):
    return float(value) if value is not None and np.isfinite(value) else None


def convert_landmarks(image, world, width, height, threshold=.5):
    if len(image) != 33 or len(world) != 33:
        raise Pose3DError('Unexpected MediaPipe landmark schema; expected 33 image/world landmarks.')
    points = []
    for im, xyz in zip(image, world):
        values = [finite_or_none(v) for v in (xyz.x, xyz.y, xyz.z, im.x, im.y, im.z,
                                             im.visibility, im.presence)]
        x, y, z, ix, iy, iz, visibility, presence = values
        reason = ('nonfinite_or_missing' if any(v is None for v in values) else
                  'invalid_score' if not (0 <= visibility <= 1 and 0 <= presence <= 1) else
                  'out_of_frame' if not (0 <= ix < 1 and 0 <= iy < 1) else
                  'low_visibility' if visibility < threshold else
                  'low_presence' if presence < threshold else 'valid')
        points.append(Landmark3D(x, y, z, None if ix is None else ix * width,
                                 None if iy is None else iy * height, iz,
                                 visibility, presence, reason == 'valid', reason))
    return tuple(points)


def candidate_box(points, width, height):
    # Ignore extrapolated/invisible extremities when associating people.
    visible = [(p.image_x, p.image_y) for p in points if p.image_x is not None and
               p.image_y is not None and p.visibility is not None and p.presence is not None
               and min(p.visibility, p.presence) >= .5 and
               0 <= p.image_x < width and 0 <= p.image_y < height]
    torso = [points[i] for i in (11, 12, 23, 24) if points[i].valid]
    if len(visible) < 5 or len(torso) < 2:
        return None
    xy = np.asarray(visible)
    low, high = xy.min(axis=0), xy.max(axis=0)
    padding = np.maximum((high - low) * .08, 4)
    box = np.r_[np.maximum(low - padding, 0), np.minimum(high + padding, [width-1, height-1])]
    return box.astype(np.float32) if min(box[2:] - box[:2]) >= 8 else None


class MediaPipeBackend:
    name = 'mediapipe_full_v1_cpu'

    def __init__(self, model_directory: Path, target_index=None, target_box=None, max_people=4):
        if type(max_people) is not int or not 1 <= max_people <= 4:
            raise Pose3DError('M2 supports max-people from 1 to 4.')
        if target_index is not None and target_index >= max_people:
            raise Pose3DError('Target index must be smaller than max-people.')
        self.max_people = max_people
        self.model_path = validate_model(model_directory)
        self.model_bytes = self.model_path.read_bytes()
        self.target_index, self.target_box = target_index, target_box
        self.selection_config = {'mode': 'index' if target_index is not None else
                                 'box' if target_box is not None else 'auto_single',
                                 'target_index': target_index, 'target_box': target_box,
                                 'candidate_backend': self.name, 'max_candidates': max_people,
                                 'single_person_input_asserted': max_people == 1,
                                 'recovery_max_candidates': 2}
        self.landmarker = None
        self._recovery_landmarker = None
        self._previous_supports = []
        self.last_diagnostics = {}
        self._last_timestamp = -1
        self.tracker = TargetTracker(target_index, target_box)
        self._create_landmarker()

    def _create_landmarker(self):
        try:
            import mediapipe as mp
            self.mp = mp
            options = mp.tasks.vision.PoseLandmarkerOptions(
                # The Windows native loader cannot open this Korean project path.
                # A verified local buffer avoids changing the user's folder names.
                base_options=mp.tasks.BaseOptions(model_asset_buffer=self.model_bytes,
                                                 delegate=mp.tasks.BaseOptions.Delegate.CPU),
                running_mode=mp.tasks.vision.RunningMode.VIDEO, num_poses=self.max_people,
                min_pose_detection_confidence=.5, min_pose_presence_confidence=.5,
                min_tracking_confidence=.5, output_segmentation_masks=True)
            self.landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(options)
        except ImportError as exc:
            raise Pose3DError('MediaPipe is missing. Install requirements.lock.') from exc
        except Exception as exc:
            raise Pose3DError('Cannot initialize the local MediaPipe Full CPU model.') from exc

    def reset_tracking(self):
        self.close()
        self.tracker = TargetTracker(self.target_index, self.target_box)
        self._last_timestamp = -1
        self._previous_supports = []
        self.last_diagnostics = {}
        self._create_landmarker()

    def _candidates(self, frame, timestamp_ms):
        if self.landmarker is None:
            raise Pose3DError('3D backend is closed.')
        if timestamp_ms <= self._last_timestamp:
            raise Pose3DError('Video timestamps must increase strictly.')
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB,
                              data=np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        try:
            raw = self.landmarker.detect_for_video(image, timestamp_ms)
        except Exception as exc:
            raise Pose3DError('Local MediaPipe inference failed.') from exc
        self._last_timestamp = timestamp_ms
        if len(raw.pose_landmarks) != len(raw.pose_world_landmarks):
            raise Pose3DError('MediaPipe image/world pose counts differ.')
        h, w = frame.shape[:2]
        masks = raw.segmentation_masks or []
        if masks and len(masks) != len(raw.pose_landmarks):
            raise Pose3DError('MediaPipe mask/pose counts differ.')
        candidates = []
        for index, (image_points, world_points) in enumerate(zip(raw.pose_landmarks, raw.pose_world_landmarks)):
            points = convert_landmarks(image_points, world_points, w, h)
            support = mask_support(masks[index].numpy_view(),w,h) if masks else None
            # Association should not shrink to the few visible joints during a turn.
            # Mask support never changes a joint's raw measurement or valid flag.
            box = support.bbox if support is not None else candidate_box(points, w, h)
            if box is not None:
                candidates.append((box, points, support, index))
        kept = []
        suppressed = []
        for candidate in sorted(candidates, key=lambda p: float(np.prod(p[0][2:]-p[0][:2])),
                                reverse=True):
            duplicate = next((p for p in kept if (duplicate_observation(candidate,p) and
                              (not self._previous_supports or
                               shared_previous_observation(candidate[2],p[2],self._previous_supports))) or
                              same_foreground(candidate[2],p[2],self._previous_supports)),None)
            if duplicate is None:
                kept.append(candidate)
            else:
                suppressed.append({'raw_index':candidate[3],'kept_raw_index':duplicate[3],
                                   'reason':'matching_joints' if duplicate_observation(candidate,duplicate)
                                   else 'nested_foreground_shared_previous_observation'})
        kept.sort(key=lambda p:(p[0][0],p[0][1]))
        self._previous_supports = [p[2] for p in kept]
        self.last_diagnostics = {'raw_pose_count':len(raw.pose_landmarks),
                                 'candidate_count':len(kept), 'duplicates_suppressed':len(suppressed),
                                 'suppression':suppressed,
                                 'box_sources':['segmentation' if p[2] is not None else 'landmarks'
                                                for p in kept]}
        return [(p[0],p[1]) for p in kept]

    def detect(self, frame):
        return np.asarray([p[0] for p in self._candidates(frame, 0)], dtype=np.float32).reshape(-1, 4)

    def infer(self, frame, timestamp_ms):
        candidates = self._candidates(frame, timestamp_ms)
        if not candidates and self.tracker.box is not None and not self.tracker.latched:
            candidates = self._recover_candidates(frame)
        guide = getattr(self, 'joint_guide', None)
        if guide is not None:
            candidates, reselect = guide.candidates(candidates, self.guidance_frame)
            if reselect:
                self.tracker = TargetTracker(target_index=0)
            self.last_diagnostics['torso_guidance_candidates'] = len(candidates)
        boxes = np.asarray([c[0] for c in candidates], dtype=np.float32).reshape(-1, 4)
        decision = self.tracker.select(frame, boxes)
        if decision.bbox is None:
            points = missing_landmarks('target_unavailable')
        else:
            # TargetTracker returns an observed candidate box, not a predicted pose.
            selected = next((c for c in candidates if np.allclose(c[0], decision.bbox)), None)
            if selected is None:
                raise Pose3DError('Selected target has no matching 3D observation.')
            points = selected[1]
        coco = tuple(Keypoint2D(p.image_x or 0., p.image_y or 0.,
                                min(p.visibility or 0., p.presence or 0.), p.valid)
                     for p in (points[i] for i in COCO_TO_MP))
        pose2d = Pose2DResult(decision.bbox, coco, len(candidates), decision.info,
                              tuple(points[i].reason for i in COCO_TO_MP))
        # Invalidate temporal model state at the start of an observation gap.
        if decision.bbox is None and decision.info.missing_frames == 1:
            self.close()
            self._create_landmarker()
        return Pose3DResult(pose2d, points)

    def _recover_candidates(self, frame):
        """Retry an actual observation near the last target; never fill a pose gap."""
        height, width = frame.shape[:2]
        box = self.tracker.box
        padding = np.maximum((box[2:]-box[:2])*.2, 32.)
        x, y = np.maximum(np.floor(box[:2]-padding), 0).astype(int)
        x2, y2 = np.minimum(np.ceil(box[2:]+padding), [width,height]).astype(int)
        if x2-x < 32 or y2-y < 32:
            return []
        if self._recovery_landmarker is None:
            self._create_recovery_landmarker()
        view = frame[y:y2, x:x2]
        try:
            raw = self._recovery_landmarker.detect(self.mp.Image(
                image_format=self.mp.ImageFormat.SRGB,
                data=np.ascontiguousarray(cv2.cvtColor(view, cv2.COLOR_BGR2RGB))))
        except Exception as exc:
            raise Pose3DError('Local Full recovery inference failed.') from exc
        if len(raw.pose_landmarks) != len(raw.pose_world_landmarks):
            raise Pose3DError('Recovery image/world pose counts differ.')
        masks = raw.segmentation_masks or []
        if masks and len(masks) != len(raw.pose_landmarks):
            raise Pose3DError('Recovery mask/pose counts differ.')
        candidates = []
        for index, (image,world) in enumerate(zip(raw.pose_landmarks,raw.pose_world_landmarks)):
            local_points = convert_landmarks(image,world,x2-x,y2-y)
            points = tuple(replace(p,
                                   image_x=None if p.image_x is None else p.image_x+x,
                                   image_y=None if p.image_y is None else p.image_y+y,
                                   image_z_normalized=None if p.image_z_normalized is None else
                                   p.image_z_normalized*(x2-x)/width,
                                   reason='outside_recovery_crop' if p.reason=='out_of_frame' else p.reason)
                           for p in local_points)
            support = mask_support(masks[index].numpy_view(),x2-x,y2-y) if masks else None
            observed_box = support.bbox+np.array([x,y,x,y]) if support else candidate_box(points,width,height)
            if observed_box is not None:
                candidates.append((observed_box,points,'recovery_segmentation' if support else 'recovery_landmarks'))
        candidates.sort(key=lambda p:(p[0][0],p[0][1]))
        # Retry supports are not mixed into full-frame mask history.
        self._previous_supports = []
        self.last_diagnostics.update({
            'candidate_count':len(candidates), 'box_sources':[p[2] for p in candidates],
            'recovery':{'roi':[int(x),int(y),int(x2),int(y2)],
                        'raw_pose_count':len(raw.pose_landmarks),'candidate_count':len(candidates)}})
        return [(p[0],p[1]) for p in candidates]

    def _create_recovery_landmarker(self):
        try:
            self._recovery_landmarker = self.mp.tasks.vision.PoseLandmarker.create_from_options(
                self.mp.tasks.vision.PoseLandmarkerOptions(
                    base_options=self.mp.tasks.BaseOptions(model_asset_buffer=self.model_bytes,
                                                          delegate=self.mp.tasks.BaseOptions.Delegate.CPU),
                    running_mode=self.mp.tasks.vision.RunningMode.IMAGE,
                    # A retry must expose ambiguity even for an asserted single-person input.
                    num_poses=2, min_pose_detection_confidence=.5,
                    min_pose_presence_confidence=.5, output_segmentation_masks=True))
        except Exception as exc:
            raise Pose3DError('Cannot initialize local Full recovery inference.') from exc

    def close(self):
        if self.landmarker is not None:
            self.landmarker.close()
            self.landmarker = None
        recovery = getattr(self, '_recovery_landmarker', None)
        if recovery is not None:
            recovery.close()
            self._recovery_landmarker = None


def duplicate_observation(a, b):
    if box_iou(a[0], b[0]) <= .85:
        return False
    diagonal = max(float(np.linalg.norm(a[0][2:]-a[0][:2])), 1.)
    for index in (11, 12, 23, 24):
        p, q = a[1][index], b[1][index]
        if not p.valid or not q.valid or np.hypot(p.image_x-q.image_x, p.image_y-q.image_y) > diagonal*.03:
            return False
    return True
