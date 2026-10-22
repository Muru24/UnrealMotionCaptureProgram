"""Stream the approved local 3D backend to model-native JSON and MP4 previews."""

from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
from time import perf_counter

import cv2

from core.pose2d.interface import COCO17
from core.pose3d.interface import COCO_TO_MP, LANDMARK33, Pose3DError
from core.pose3d.preview import draw_landmarks, render_preview
from core.video.decoder import VideoInputError, inspect_video
from core.video.limits import MAX_VIDEO_FRAMES, validate_duration


def process_pose3d(source, output: Path, backend, progress=None, cancelled=None, anchors=None):
    metadata = inspect_video(source)
    guide = None
    if anchors:
        from core.pose3d.guidance import JointGuide
        guide = JointGuide(anchors, metadata.width, metadata.height, metadata.fps, metadata.frame_count)
    validate_duration(metadata, Pose3DError)
    if max(metadata.width, metadata.height) > 1920 or min(metadata.width, metadata.height) < 32:
        raise Pose3DError('M2 supports dimensions from 32 to 1920 pixels per side.')
    if metadata.width % 2 or metadata.height % 2 or not 1 <= metadata.fps <= 240:
        raise Pose3DError('M2 requires even dimensions and 1..240 fps.')
    output = Path(output)
    if str(output).startswith(('\\\\', '//')) or '://' in str(output):
        raise Pose3DError('Output directory must be local.')
    if output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise Pose3DError('Output symbolic links are not supported.')
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise Pose3DError('Choose a new writable output directory; results are never overwritten.') from exc
    count = accepted = usable = valid = reselection = multi = 0
    states, reasons = Counter(), Counter()
    duplicates_suppressed = segmentation_box_frames = 0
    recovery_attempts = recovered_frames = 0
    status = 'failed'
    started = perf_counter()
    capture = cv2.VideoCapture()
    writers, streams = [], []
    report = {}
    guidance_counts = Counter()
    unapplied_anchors = []
    try:
        backend.reset_tracking()
        if guide is not None:
            backend.joint_guide = guide
        headers = {
            'pose3d.json': {'version': 1, 'stage': 'pose3d', 'schema': 'mediapipe33',
                            'joint_names': LANDMARK33, 'units': 'meters',
                            'coordinates': 'mediapipe_native_world_xyz',
                            'origin': 'midpoint_of_hips_model_estimated', 'root_motion': False,
                            'image_coordinates': 'original_pixels_x_right_y_down',
                            'image_z_normalized': 'model_depth_relative_to_hips_in_image_width_units',
                            'timestamp_mode': 'frame_index_divided_by_nominal_fps',
                            'backend': backend.name, 'video': metadata.to_dict()},
            'pose2d.json': {'version': 1, 'stage': 'pose2d', 'schema': 'coco17',
                            'joint_names': COCO17, 'coordinates': 'pixels_x_right_y_down',
                            'backend': backend.name, 'video': metadata.to_dict(),
                            'score_meaning': 'min_mediapipe_visibility_presence_not_rtmpose_score',
                            'source_indices': COCO_TO_MP,
                            'timestamp_mode': 'frame_index_divided_by_nominal_fps'},
            'tracking.json': {'version': 1, 'joint_names': LANDMARK33,
                              'selection': backend.selection_config},
        }
        for name, header in headers.items():
            stream = (output/name).open('x', encoding='utf-8')
            streams.append(stream)
            stream.write(json.dumps(header, allow_nan=False)[:-1]+', "frames": [\n')
        if guide is not None:
            guidance_stream = (output/'guidance2d.json').open('x', encoding='utf-8')
            streams.append(guidance_stream)
            guidance_stream.write(json.dumps({'version':1, 'coordinates':'original_pixels_x_right_y_down',
                'world_coordinates':False, 'max_prediction_seconds':guide.max_gap,
                'anchors':guide.anchors},allow_nan=False)[:-1]+', "frames": [\n')
        if not capture.open(str(Path(source).resolve()), cv2.CAP_FFMPEG,
                            [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                             cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000]):
            raise VideoInputError('Cannot reopen video for 3D processing.')
        for name, size in (('overlay.mp4', (metadata.width, metadata.height)),
                           ('preview3d.mp4', (1280, 720))):
            writer = cv2.VideoWriter(str(output/name), cv2.VideoWriter_fourcc(*'mp4v'),
                                     metadata.fps, size)
            writers.append(writer)
            if not writer.isOpened():
                raise Pose3DError('Cannot initialize M2 MP4 encoder.')
        while True:
            if cancelled and cancelled():
                raise KeyboardInterrupt
            ok, frame = capture.read()
            if not ok:
                break
            if count >= MAX_VIDEO_FRAMES:
                raise Pose3DError('Decoded video exceeds the M2 frame limit.')
            if frame.shape[:2] != (metadata.height, metadata.width):
                raise VideoInputError('Decoded frame dimensions changed.')
            backend.guidance_frame = count
            pose = backend.infer(frame, round(count/metadata.fps*1000))
            timing = {'frame_index': count, 'timestamp': count/metadata.fps}
            tracking = pose.pose2d.tracking
            payloads = [{**timing, **pose.to_dict()}, {**timing, **pose.pose2d.to_dict()},
                        {**timing, 'tracking': asdict(tracking),
                         'people_detected': pose.pose2d.people_detected,
                         'observation': getattr(backend,'last_diagnostics',{}),
                         'joint_states': [p.reason for p in pose.landmarks]}]
            encoded = [json.dumps(p, allow_nan=False) for p in payloads]
            if guide is not None:
                from core.pose3d.guidance import draw_guidance
                guided = guide.process(pose, count, frame=frame)
                requested = guide.anchors.get(count, {})
                if requested and (guided['torso'] is None or any(
                        guided['joints'].get(name,{}).get('state') != 'manual'
                        for name in requested if name not in ('pelvis','chest'))):
                    unapplied_anchors.append(count)
                guidance_stream.write((',\n' if count else '')+json.dumps(guided,allow_nan=False))
                guidance_counts.update(p['state'] for p in guided['joints'].values())
                overlay = draw_guidance(frame, guided)
            else:
                overlay = draw_landmarks(frame, pose)
            preview = render_preview(overlay, pose, count, metadata.fps)
            writers[0].write(overlay)
            writers[1].write(preview)
            for stream, data in zip(streams, encoded):
                stream.write((',\n' if count else '')+data)
            count += 1
            accepted += pose.pose2d.person_bbox is not None
            # A usable torso is a coverage indicator, never a correctness claim.
            usable += all(pose.landmarks[i].valid for i in (11, 12, 23, 24))
            valid += sum(p.valid for p in pose.landmarks)
            multi += pose.pose2d.people_detected > 1
            reselection += tracking.requires_reselection
            states[tracking.state] += 1
            reasons.update(p.reason for p in pose.landmarks)
            observation = getattr(backend,'last_diagnostics',{})
            duplicates_suppressed += observation.get('duplicates_suppressed',0)
            segmentation_box_frames += 'segmentation' in observation.get('box_sources',[])
            recovery_attempts += 'recovery' in observation
            recovered_frames += 'recovery' in observation and pose.pose2d.person_bbox is not None
            if progress and (count == 1 or count % 15 == 0):
                progress(count, metadata.frame_count)
        if not count:
            raise VideoInputError('No frames decoded.')
        status = ('completed' if count == metadata.frame_count and valid == count*33 and not multi
                  and not reselection and not duplicates_suppressed and not recovery_attempts and guide is None
                  else 'completed_with_warnings')
    except KeyboardInterrupt:
        status = 'cancelled'
        raise
    except (cv2.error, OSError) as exc:
        raise Pose3DError('Cannot read video or write M2 output.') from exc
    finally:
        if guide is not None:
            backend.joint_guide = None
        capture.release()
        for writer in writers:
            writer.release()
        for stream in streams:
            try:
                stream.write('\n], "status": '+json.dumps(status)+'}\n')
            finally:
                stream.close()
        report = {'stage': 'pose3d', 'status': status, 'backend': backend.name,
                  'frames_processed': count, 'expected_frames': metadata.frame_count,
                  'frames_with_target': accepted, 'frames_with_valid_torso': usable,
                  'valid_joint_ratio': valid/(count*33) if count else 0.,
                  'tracking_state_counts': dict(states), 'joint_state_counts': dict(reasons),
                  'multi_person_frames': multi, 'frames_requiring_reselection': reselection,
                  'frame_count_matches_metadata': count == metadata.frame_count,
                  'processing_seconds': round(perf_counter()-started, 3),
                  'selection': backend.selection_config,
                  'duplicates_suppressed': duplicates_suppressed,
                  'frames_with_segmentation_boxes': segmentation_box_frames,
                  'recovery_attempts': recovery_attempts, 'recovered_frames': recovered_frames,
                  'warnings': (['decoded_frame_count_differs_from_metadata'] if count != metadata.frame_count else [])+
                              (['target_unavailable_in_some_frames'] if accepted != count else [])+
                              (['unreliable_joints_in_some_frames'] if valid != count*33 else [])+
                              (['target_reselection_required'] if reselection else [])+
                              (['duplicate_candidates_suppressed'] if duplicates_suppressed else [])+
                              (['local_crop_recovery_used'] if recovery_attempts else [])+
                              (['multiple_people_detected'] if multi else []),
                  'limits': ['root_relative_estimate_not_measured_global_motion',
                             'visibility_presence_are_not_accuracy',
                             'no_smoothing_or_gap_interpolation', 'maximum_four_candidates',
                             'foreground_support_is_not_identity_or_joint_accuracy']}
        if guide is not None:
            report['guidance2d_state_counts'] = dict(guidance_counts)
            report['unused_anchor_frames'] = sorted(i for i in guide.anchors if i >= count)
            report['unapplied_anchor_frames'] = unapplied_anchors
            report['warnings'].append('manual_2d_guidance_world_unchanged')
            if unapplied_anchors or report['unused_anchor_frames']:
                report['warnings'].append('joint_anchors_unapplied')
        try:
            (output/'report.json').write_text(json.dumps(report, allow_nan=False, indent=2), encoding='utf-8')
        except OSError as exc:
            raise Pose3DError('Cannot save M2 report; output is incomplete.') from exc
    return report
