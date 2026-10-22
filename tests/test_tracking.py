import json

import cv2
import numpy as np
import pytest

from app.processing import process_pose2d
from core.pose2d.interface import Keypoint2D, Pose2DError, Pose2DResult, TrackingInfo
from core.pose2d.rtmpose_backend import RTMPoseBackend
from core.pose2d.tracker import TargetTracker, suppress_duplicate_boxes


BLUE = (240, 30, 30)
RED = (30, 30, 240)
A = (20, 20, 100, 180)
B = (210, 20, 290, 180)


def scene(*people):
    frame = np.zeros((200, 320, 3), np.uint8)
    boxes = []
    for box, color in people:
        x1, y1, x2, y2 = box
        frame[y1:y2, x1:x2] = color
        boxes.append(box)
    return frame, np.asarray(boxes, dtype=np.float32).reshape(-1, 4)


def test_explicit_index_selects_smaller_person_and_keeps_target():
    tracker = TargetTracker(target_index=0)
    decision = tracker.select(*scene((A, BLUE), (B, RED)))
    assert decision.bbox == A
    for i in range(1, 12):
        target = (20 + i * 2, 20, 100 + i * 2, 180)
        bigger_other = (180, 0, 319, 199)
        decision = tracker.select(*scene((target, BLUE), (bigger_other, RED)))
        assert decision.info.state == "tracked"
        assert decision.bbox == target
        assert decision.info.track_id == 1


def test_explicit_second_candidate():
    result = TargetTracker(target_index=1).select(*scene((A, BLUE), (B, RED)))
    assert result.bbox == B


def test_box_selection():
    result = TargetTracker(target_box=(15, 15, 110, 190)).select(*scene((A, BLUE), (B, RED)))
    assert result.bbox == A


def test_multiple_initial_people_require_selection():
    with pytest.raises(Pose2DError, match="Multiple initial people"):
        TargetTracker().select(*scene((A, BLUE), (B, RED)))


def test_initial_absence_is_not_loss_of_an_existing_target():
    tracker = TargetTracker()
    decision = tracker.select(*scene())
    assert decision.info.state == "uninitialized"
    assert decision.info.track_id is None
    assert tracker.select(*scene((A, BLUE))).bbox == A


def test_short_detection_gap_reconnects_same_target():
    tracker = TargetTracker()
    tracker.select(*scene((A, BLUE)))
    for _ in range(2):
        decision = tracker.select(*scene())
        assert decision.info.state == "uncertain"
        assert not decision.info.requires_reselection
        assert decision.bbox is None
    decision = tracker.select(*scene((A, BLUE)))
    assert decision.info.state == "tracked"
    assert decision.info.reason == "short_gap_reconnected"
    assert decision.bbox == A


def test_departed_target_is_not_replaced_by_remaining_person():
    tracker = TargetTracker(target_index=0)
    tracker.select(*scene((A, BLUE), (B, RED)))
    for _ in range(6):
        decision = tracker.select(*scene((B, RED)))
        assert decision.bbox is None
    assert decision.info.state == "lost"
    assert decision.info.requires_reselection


def test_long_gap_remains_lost_even_if_someone_returns_to_same_position():
    tracker = TargetTracker()
    tracker.select(*scene((A, BLUE)))
    for _ in range(6):
        tracker.select(*scene())
    decision = tracker.select(*scene((A, BLUE)))
    assert decision.info.state == "lost"
    assert decision.bbox is None


def test_appearance_rejects_different_person_at_same_position():
    tracker = TargetTracker()
    tracker.select(*scene((A, BLUE)))
    decision = tracker.select(*scene((A, RED)))
    assert decision.bbox is None
    assert decision.info.reason == "target_not_matched"


def test_observed_crossing_latches_uncertainty_instead_of_switching():
    tracker = TargetTracker(target_index=0)
    tracker.select(*scene((A, BLUE), (B, RED)))
    target = (30, 20, 110, 180)
    crossing = (70, 20, 150, 180)
    decision = tracker.select(*scene((target, BLUE), (crossing, RED)))
    assert decision.bbox is None
    assert decision.info.requires_reselection
    assert decision.info.reason == "overlapping_people"
    for _ in range(6):
        decision = tracker.select(*scene((target, BLUE)))
        assert decision.bbox is None
    assert decision.info.state == "lost"


@pytest.mark.parametrize("kwargs", [
    {"target_index": -1}, {"target_index": 0, "target_box": A},
    {"target_box": (0, 0, 0, 1)}, {"target_box": (0, 0, float("nan"), 2)},
    {"target_box": (-1, 0, 20, 20)},
])
def test_invalid_selection_parameters(kwargs):
    with pytest.raises(Pose2DError):
        TargetTracker(**kwargs)


@pytest.mark.parametrize("kwargs,people", [
    ({"target_index": 3}, ((A, BLUE),)),
    ({"target_index": 0}, ()),
    ({"target_box": (0, 0, 500, 500)}, ((A, BLUE),)),
    ({"target_box": (200, 0, 250, 10)}, ((A, BLUE),)),
])
def test_unavailable_initial_selection_is_an_error(kwargs, people):
    with pytest.raises(Pose2DError):
        TargetTracker(**kwargs).select(*scene(*people))


def fake_backend(boxes):
    backend = RTMPoseBackend.__new__(RTMPoseBackend)
    backend.threshold = .3
    backend.target_index = None
    backend.target_box = None
    backend.reset_tracking()
    backend.detector = lambda frame: np.asarray(boxes, dtype=np.float32).reshape(-1, 4)

    def pose(frame, bboxes):
        assert len(bboxes) == 1
        coords = np.full((1, 17, 2), 50.0, np.float32)
        scores = np.full((1, 17), .9, np.float32)
        scores[0, 0] = .1
        coords[0, 1, 0] = 500
        coords[0, 2, 0] = np.nan
        return coords, scores

    backend.pose = pose
    return backend


def test_joint_low_confidence_is_separate_from_target_loss():
    backend = fake_backend([A])
    frame, _ = scene((A, BLUE))
    result = backend.infer(frame)
    assert result.tracking.state == "tracked"
    assert result.joint_states[:4] == ("low_confidence", "out_of_frame", "nonfinite", "valid")
    assert not any(p.valid for p in result.keypoints[:3])
    assert set(result.to_dict()) == {"person_bbox", "keypoints", "people_detected"}
    backend.detector = lambda frame: np.empty((0, 4))
    result = backend.infer(frame)
    assert result.tracking.state == "uncertain"
    assert result.joint_states == ("target_unavailable",) * 17
    assert result.keypoints == ()


def test_candidate_indexes_are_sorted_left_to_right():
    backend = fake_backend([B, A])
    frame, _ = scene((A, BLUE), (B, RED))
    assert backend.detect(frame).tolist() == [list(A), list(B)]


def test_nested_duplicate_does_not_permanently_lose_single_person():
    # Measured boxes at vivian frame 40: one body, a tighter and a wider detection.
    wider = (7.7521, 177.5673, 561.4322, 1279.0)
    tighter = (177.0267, 204.6068, 545.5355, 1276.0507)
    boxes = np.asarray([wider, tighter], dtype=np.float32)
    clean = suppress_duplicate_boxes(boxes)
    assert len(clean) == 1
    backend = fake_backend([A])
    frame, _ = scene((A, BLUE))
    assert backend.infer(frame).tracking.state == "tracked"
    backend.detector = lambda _: np.asarray([A, (22, 22, 98, 178)], dtype=np.float32)
    result = backend.infer(frame)
    assert result.people_detected == 1
    assert result.tracking.state == "tracked"
    backend.detector = lambda _: np.asarray([A], dtype=np.float32)
    assert backend.infer(frame).tracking.state == "tracked"


def test_partial_overlap_stays_separate_for_crossing_guard():
    boxes = np.asarray([(30, 20, 110, 180), (70, 20, 150, 180)], dtype=np.float32)
    assert len(suppress_duplicate_boxes(boxes)) == 2


def test_non_nested_high_overlap_stays_separate():
    boxes = np.asarray([(20, 20, 100, 180), (35, 20, 115, 180)], dtype=np.float32)
    assert len(suppress_duplicate_boxes(boxes)) == 2


def test_reset_tracking_allows_explicit_new_session():
    backend = fake_backend([A])
    frame, _ = scene((A, BLUE))
    backend.infer(frame)
    backend.detector = lambda frame: np.empty((0, 4))
    for _ in range(6):
        result = backend.infer(frame)
    assert result.tracking.state == "lost"
    backend.reset_tracking()
    backend.detector = lambda frame: np.asarray([A], dtype=np.float32)
    result = backend.infer(frame)
    assert result.tracking.state == "tracked" and result.tracking.reason == "initial_selection"


def test_tracking_sidecar_preserves_pose_payload_and_output_alignment(tmp_path):
    source = tmp_path / "input.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 30, (320, 200))
    assert writer.isOpened()
    for _ in range(4):
        writer.write(np.zeros((200, 320, 3), np.uint8))
    writer.release()

    class Backend:
        calls = 0

        def infer(self, frame):
            self.calls += 1
            if self.calls == 2:
                return Pose2DResult(None, (), 1,
                                    TrackingInfo("uncertain", "target_not_matched", 1, 1, False),
                                    ("target_unavailable",) * 17)
            return Pose2DResult(A, tuple(Keypoint2D(50, 50, .9, True) for _ in range(17)), 1,
                                TrackingInfo("tracked", "matched", 1, 0, False), ("valid",) * 17)

    output = tmp_path / "output"
    report = process_pose2d(source, output, Backend())
    pose = json.loads((output / "pose2d.json").read_text())
    diagnostics = json.loads((output / "tracking.json").read_text())
    assert len(pose["frames"]) == len(diagnostics["frames"]) == 4
    assert "tracking" not in pose["frames"][0]
    assert report["tracking_state_counts"]["uncertain"] == 1
    assert report["frames_with_detections"] == 4
    assert report["frames_with_target"] == 3
    assert diagnostics["frames"][1]["joint_states"] == ["target_unavailable"] * 17
    assert diagnostics["status"] == pose["status"] == "completed_with_warnings"
