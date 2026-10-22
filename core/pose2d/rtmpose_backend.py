"""RTMPose-m + YOLOX-tiny on CPU, using explicitly supplied local models."""

from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path

import numpy as np

from .interface import COCO17, Keypoint2D, Pose2DBackend, Pose2DError, Pose2DResult
from .tracker import TargetTracker, suppress_duplicate_boxes


def validate_models(directory: Path) -> dict[str, Path]:
    if str(directory).startswith(("\\\\", "//")) or "://" in str(directory):
        raise Pose2DError("Model directory must be local.")
    try:
        if directory.is_symlink() or any(p.is_symlink() for p in directory.parents):
            raise Pose2DError("Model directory symbolic links are not supported.")
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8-sig"))
        paths = {}
        for role in ("detector", "pose"):
            spec = manifest[role]
            name = spec["file"]
            if Path(name).name != name or not name.endswith(".onnx"):
                raise Pose2DError("Invalid model filename in manifest.")
            path = directory / name
            if path.is_symlink() or not path.is_file():
                raise Pose2DError("Local model is missing. See models/pose2d/README.md.")
            with path.open("rb") as model_file:
                digest = hashlib.file_digest(model_file, "sha256").hexdigest()
            if digest != spec["sha256"]:
                raise Pose2DError("Model integrity check failed.")
            paths[role] = path.resolve()
        return paths
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise Pose2DError("Cannot read local model files or manifest. See models/pose2d/README.md.") from exc


class RTMPoseBackend(Pose2DBackend):
    name = "rtmpose-m_yolox-tiny_cpu"

    def __init__(self, model_directory: Path, threshold: float = 0.3,
                 target_index: int | None = None, target_box=None, detector_only=False, association_pose=False):
        if not np.isfinite(threshold) or not 0 <= threshold <= 1:
            raise Pose2DError("Confidence threshold must be between 0 and 1.")
        self.threshold = threshold
        self.detector_only = detector_only
        self.target_index = target_index
        self.target_box = target_box
        self.selection_config = {"mode": "index" if target_index is not None else
                                 "box" if target_box is not None else "auto_single",
                                 "target_index": target_index, "target_box": target_box}
        self.reset_tracking()
        paths = validate_models(model_directory)
        try:
            import onnxruntime as ort
            from rtmlib import RTMPose, YOLOX

            ort.disable_telemetry_events()
            # rtmlib prints full paths when loading; keep the CLI output concise.
            with redirect_stdout(io.StringIO()):
                self.detector = YOLOX(str(paths["detector"]), model_input_size=(416, 416),
                                      backend="onnxruntime", device="cpu")
                self.pose = None if detector_only and not association_pose else RTMPose(str(paths["pose"]), model_input_size=(192, 256),
                                                              backend="onnxruntime", device="cpu")
            for model in (self.detector, self.pose):
                if model is not None and model.session.get_providers() != ["CPUExecutionProvider"]:
                    raise Pose2DError("Only the local CPU execution provider is supported in M1.")
        except ImportError as exc:
            raise Pose2DError("Pose dependencies are missing. Install requirements.lock.") from exc
        except Pose2DError:
            raise
        except Exception as exc:
            raise Pose2DError("Cannot initialize local pose models.") from exc

    def reset_tracking(self):
        self.tracker = TargetTracker(self.target_index, self.target_box)

    def detect(self, frame_bgr: np.ndarray) -> np.ndarray:
        if self.detector is None:
            raise Pose2DError("Pose backend is closed.")
        try:
            boxes = np.asarray(self.detector(frame_bgr), dtype=np.float32).reshape(-1, 4)
            height, width = frame_bgr.shape[:2]
            boxes = boxes[np.isfinite(boxes).all(axis=1)]
            boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, width - 1)
            boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, height - 1)
            boxes = boxes[(boxes[:, 2] > boxes[:, 0]) & (boxes[:, 3] > boxes[:, 1])]
            # Candidate indexes are deterministic for the same first frame.
            clean=suppress_duplicate_boxes(boxes,frame_bgr if getattr(self,'detector_only',False) else None)
            self.last_detection_diagnostics={'raw_count':len(boxes),'duplicates_suppressed':len(boxes)-len(clean)}
            return clean
        except Exception as exc:
            raise Pose2DError("Local person detection failed.") from exc

    def infer(self, frame_bgr: np.ndarray) -> Pose2DResult:
        if self.detector is None or self.pose is None:
            raise Pose2DError("Pose backend is closed.")
        try:
            boxes = self.detect(frame_bgr)
            decision = self.tracker.select(frame_bgr, boxes)
            if decision.bbox is None:
                return Pose2DResult(None, (), len(boxes), decision.info,
                                    ("target_unavailable",) * len(COCO17))
            box = decision.bbox
            height, width = frame_bgr.shape[:2]
            coords, scores = self.pose(frame_bgr, bboxes=[box])
            if coords.shape != (1, len(COCO17), 2) or scores.shape != (1, len(COCO17)):
                raise Pose2DError("Unexpected RTMPose output schema.")
            points = []
            states = []
            for (x, y), score in zip(coords[0], scores[0]):
                if not np.isfinite([x, y, score]).all():
                    points.append(Keypoint2D(0.0, 0.0, 0.0, False))
                    states.append("nonfinite")
                else:
                    state = ("out_of_frame" if not (0 <= x < width and 0 <= y < height)
                             else "low_confidence" if score < self.threshold else "valid")
                    states.append(state)
                    points.append(Keypoint2D(float(x), float(y), float(score),
                                            state == "valid"))
            return Pose2DResult(box, tuple(points), len(boxes), decision.info, tuple(states))
        except Pose2DError:
            raise
        except Exception as exc:
            raise Pose2DError("Local pose inference failed.") from exc

    def association_keypoints(self,frame,boxes):
        if self.pose is None:raise Pose2DError('Association pose model is not loaded.')
        if not len(boxes):return np.empty((0,17,2)),np.empty((0,17))
        coords,scores=self.pose(frame,bboxes=boxes)
        coords=np.asarray(coords);scores=np.asarray(scores).copy()
        if coords.shape!=(len(boxes),17,2) or scores.shape!=(len(boxes),17):
            raise Pose2DError('Unexpected association pose dimensions.')
        h,w=frame.shape[:2]
        valid=np.isfinite(coords).all(axis=2)&np.isfinite(scores)&(coords[:,:,0]>=0)&(coords[:,:,0]<w)&(coords[:,:,1]>=0)&(coords[:,:,1]<h)
        for i,box in enumerate(boxes):
            padding=(box[2:]-box[:2])*.1
            valid[i]&=(coords[i]>=box[:2]-padding).all(axis=1)&(coords[i]<=box[2:]+padding).all(axis=1)
        scores[~valid]=0
        return coords,scores

    def detect_region(self,frame,region):
        x1,y1,x2,y2=map(int,region)
        h,w=frame.shape[:2]
        if not (0<=x1<x2<=w and 0<=y1<y2<=h):
            raise Pose2DError('Invalid regional detection bounds.')
        crop=frame[y1:y2,x1:x2]
        previous=getattr(self,'last_detection_diagnostics',{})
        try:
            boxes=self.detect(crop)
            coords,scores=self.association_keypoints(crop,boxes)
            return boxes+np.array([x1,y1,x1,y1]),(coords+np.array([x1,y1]),scores)
        finally:self.last_detection_diagnostics=previous

    def close(self) -> None:
        self.detector = None
        self.pose = None
