"""Stream local video through a 2D pose backend and export diagnostics."""

import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Callable

import cv2

from core.pose2d.interface import COCO17, CONNECTIONS, Pose2DBackend, Pose2DError, Pose2DResult
from core.video.decoder import VideoInputError, inspect_video
from core.video.limits import MAX_VIDEO_FRAMES, validate_duration


def draw_pose(frame, pose: Pose2DResult):
    if pose.tracking is not None:
        color = (0, 220, 0) if pose.tracking.state == "tracked" else (0, 100, 255)
        cv2.putText(frame, f"Target: {pose.tracking.state.upper()} / {pose.tracking.reason}",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, .55, color, 2, cv2.LINE_AA)
    if pose.person_bbox:
        x1, y1, x2, y2 = (int(v) for v in pose.person_bbox)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 180, 0), 2)
    for a, b in CONNECTIONS:
        if pose.keypoints and pose.keypoints[a].valid and pose.keypoints[b].valid:
            p, q = pose.keypoints[a], pose.keypoints[b]
            cv2.line(frame, (round(p.x), round(p.y)), (round(q.x), round(q.y)),
                     (0, 240, 0), 3, cv2.LINE_AA)
    for point in pose.keypoints:
        if point.valid:
            cv2.circle(frame, (round(point.x), round(point.y)), 4,
                       (0, 140, 255), -1, cv2.LINE_AA)
    return frame


def process_pose2d(source: str | Path, output: Path, backend: Pose2DBackend,
                   progress: Callable[[int, int], None] | None = None,
                   cancelled: Callable[[], bool] | None = None) -> dict:
    metadata = inspect_video(source)
    validate_duration(metadata, Pose2DError)
    if max(metadata.width, metadata.height) > 1920:
        raise Pose2DError("M1 supports resolutions up to 1920 pixels per side.")
    if metadata.width % 2 or metadata.height % 2:
        raise Pose2DError("M1 MP4 output requires even width and height.")
    if str(output).startswith(("\\\\", "//")) or "://" in str(output):
        raise Pose2DError("Output directory must be local.")
    if output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise Pose2DError("Output symbolic links are not supported.")
    try:
        # An exclusive new directory protects the input and all existing results.
        output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise Pose2DError("Choose a new, writable output directory; existing results are never overwritten.") from exc

    capture = cv2.VideoCapture()
    writer = None
    count = detected = multi = valid = measured = 0
    score_sum = 0.0
    tracking_counts = {state: 0 for state in ("tracked", "uncertain", "lost", "uninitialized")}
    joint_counts = {state: 0 for state in ("valid", "low_confidence", "out_of_frame",
                                         "nonfinite", "target_unavailable")}
    joint_issue_frames = {state: 0 for state in ("low_confidence", "out_of_frame", "nonfinite")}
    detections = reselection = 0
    started = perf_counter()
    status = "failed"
    try:
        if hasattr(backend, "reset_tracking"):
            backend.reset_tracking()
        with (output / "pose2d.json").open("x", encoding="utf-8") as data, \
                (output / "tracking.json").open("x", encoding="utf-8") as diagnostics:
            header = {
                "version": 1, "stage": "pose2d", "schema": "coco17",
                "joint_names": COCO17, "coordinates": "pixels_x_right_y_down",
                "timestamp_mode": "frame_index_divided_by_nominal_fps",
                "backend": getattr(backend, "name", "custom"),
                "video": metadata.to_dict(),
            }
            data.write(json.dumps(header, allow_nan=False)[:-1] + ', "frames": [\n')
            diagnostics.write(json.dumps({"version": 1, "joint_names": COCO17,
                                          "selection": getattr(backend, "selection_config", {})})[:-1]
                              + ', "frames": [\n')
            try:
                if not capture.open(str(Path(source).resolve()), cv2.CAP_FFMPEG,
                                    [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                                     cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000]):
                    raise VideoInputError("Cannot reopen video for pose processing.")
                writer = cv2.VideoWriter(str(output / "overlay.mp4"),
                                         cv2.VideoWriter_fourcc(*"mp4v"), metadata.fps,
                                         (metadata.width, metadata.height))
                if not writer.isOpened():
                    raise Pose2DError("Cannot initialize MP4 output encoder.")
                while True:
                    if cancelled and cancelled():
                        raise KeyboardInterrupt
                    ok, frame = capture.read()
                    if not ok:
                        break
                    if count >= MAX_VIDEO_FRAMES:
                        raise Pose2DError("Decoded video exceeds M1 frame limit.")
                    if frame.shape[:2] != (metadata.height, metadata.width):
                        raise VideoInputError("Decoded frame dimensions changed.")
                    pose = backend.infer(frame)
                    record = {"frame_index": count, "timestamp": count / metadata.fps,
                              **pose.to_dict()}
                    # Serialize before writing either artifact so invalid floats fail clearly.
                    encoded = json.dumps(record, allow_nan=False)
                    diagnostic = json.dumps({"frame_index": count, "timestamp": count / metadata.fps,
                                             "tracking": asdict(pose.tracking) if pose.tracking else None,
                                             "people_detected": pose.people_detected,
                                             "joint_states": pose.joint_states}, allow_nan=False)
                    writer.write(draw_pose(frame, pose))
                    data.write((",\n" if count else "") + encoded)
                    diagnostics.write((",\n" if count else "") + diagnostic)
                    count += 1
                    detected += int(pose.person_bbox is not None)
                    multi += int(pose.people_detected > 1)
                    valid += sum(p.valid for p in pose.keypoints)
                    measured += len(pose.keypoints)
                    score_sum += sum(p.confidence for p in pose.keypoints)
                    detections += int(pose.people_detected > 0)
                    if pose.tracking:
                        tracking_counts[pose.tracking.state] += 1
                        reselection += int(pose.tracking.requires_reselection)
                    for state in pose.joint_states:
                        joint_counts[state] += 1
                    for state in joint_issue_frames:
                        joint_issue_frames[state] += int(state in pose.joint_states)
                    if progress and (count == 1 or count % 15 == 0):
                        progress(count, metadata.frame_count)
                if count == 0:
                    raise VideoInputError("No video frames could be decoded.")
                # Fragmented MP4 containers may expose an estimated frame count.
                # Preserve the mismatch as a warning; EOF alone cannot prove integrity.
                status = ("completed" if count == metadata.frame_count and
                          multi == 0 and detected == count and not any(joint_issue_frames.values())
                          else "completed_with_warnings")
            except KeyboardInterrupt:
                status = "cancelled"
                raise
            finally:
                data.write('\n], "status": ' + json.dumps(status) + "}\n")
                diagnostics.write('\n], "status": ' + json.dumps(status) + "}\n")
    except (cv2.error, OSError) as exc:
        raise Pose2DError("Cannot read video or write pose output.") from exc
    finally:
        capture.release()
        if writer is not None:
            writer.release()
        report = {
            "status": status, "frames_processed": count,
            "expected_frames": metadata.frame_count, "frames_with_person": detected,
            "frames_without_person": count - detected, "multi_person_frames": multi,
            "valid_keypoint_ratio": valid / measured if measured else 0.0,
            "mean_keypoint_score": score_sum / measured if measured else 0.0,
            "processing_seconds": round(perf_counter() - started, 3),
            "selection": "initial_selection_then_conservative_tracking" if hasattr(backend, "tracker") else "backend_defined",
            "frames_with_detections": detections,
            "frames_with_target": detected,
            "tracking_state_counts": tracking_counts,
            "frames_requiring_reselection": reselection,
            "joint_state_counts": joint_counts,
            "joint_issue_frame_counts": joint_issue_frames,
            "frame_count_matches_metadata": count == metadata.frame_count,
            "warnings": (["decoded_frame_count_differs_from_metadata"]
                         if count != metadata.frame_count else []) +
                        (["multiple_people_detected"] if multi else []) +
                        (["target_unavailable_in_some_frames"] if count != detected else []) +
                        (["target_reselection_required"] if reselection else []) +
                        (["unreliable_joints_in_some_frames"] if any(joint_issue_frames.values()) else []),
        }
        try:
            (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        except OSError as exc:
            raise Pose2DError("Cannot save processing report; output is incomplete.") from exc
    return report
