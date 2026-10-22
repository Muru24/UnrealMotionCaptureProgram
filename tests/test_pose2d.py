import json
from pathlib import Path
import socket
import subprocess
import sys

import cv2
import numpy as np
import pytest

from app.processing import process_pose2d
from core.pose2d.interface import COCO17, Keypoint2D, Pose2DError, Pose2DResult
from core.pose2d.rtmpose_backend import RTMPoseBackend, validate_models
from core.video.decoder import VideoInputError, inspect_video


@pytest.fixture
def clip(tmp_path):
    path = tmp_path / "입력 영상.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (320, 240))
    assert writer.isOpened()
    try:
        for _ in range(6):
            writer.write(np.zeros((240, 320, 3), np.uint8))
    finally:
        writer.release()
    return path


class StubBackend:
    def __init__(self, empty=False):
        self.calls = 0
        self.empty = empty

    def infer(self, frame):
        self.calls += 1
        if self.empty:
            return Pose2DResult(None, (), 0)
        points = tuple(Keypoint2D(50.0 + i * 5, 50.0 + i * 3, 0.9, i != 16)
                       for i in range(17))
        return Pose2DResult((20.0, 20.0, 250.0, 220.0), points, 2)

    def close(self):
        pass


def test_export_frame_alignment_and_overlay(clip, tmp_path):
    output = tmp_path / "결과 폴더"
    backend = StubBackend()
    report = process_pose2d(clip, output, backend)
    data = json.loads((output / "pose2d.json").read_text())
    assert report["status"] == data["status"] == "completed_with_warnings"
    assert backend.calls == report["frames_processed"] == 6
    assert report["multi_person_frames"] == 6
    assert data["joint_names"] == list(COCO17)
    assert [f["frame_index"] for f in data["frames"]] == list(range(6))
    assert data["frames"][5]["timestamp"] == pytest.approx(5 / 30)
    assert not data["frames"][0]["keypoints"][16]["valid"]
    assert inspect_video(output / "overlay.mp4").frame_count == 6
    capture = cv2.VideoCapture(str(output / "overlay.mp4"))
    try:
        ok, frame = capture.read()
        assert ok and frame.max() > 100, "Overlay should modify a black input frame"
    finally:
        capture.release()


def test_no_person_stays_empty(clip, tmp_path):
    output = tmp_path / "empty-result"
    report = process_pose2d(clip, output, StubBackend(empty=True))
    data = json.loads((output / "pose2d.json").read_text())
    assert report["frames_without_person"] == 6
    assert all(f["keypoints"] == [] and f["person_bbox"] is None for f in data["frames"])


def test_existing_output_is_preserved(clip, tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "overlay.mp4"
    sentinel.write_bytes(b"user content")
    with pytest.raises(Pose2DError, match="never overwritten"):
        process_pose2d(clip, output, StubBackend())
    assert sentinel.read_bytes() == b"user content"


def test_cancel_partial_results_are_readable(clip, tmp_path):
    output = tmp_path / "cancelled"
    backend = StubBackend()
    with pytest.raises(KeyboardInterrupt):
        process_pose2d(clip, output, backend, cancelled=lambda: backend.calls >= 2)
    data = json.loads((output / "pose2d.json").read_text())
    report = json.loads((output / "report.json").read_text())
    assert data["status"] == report["status"] == "cancelled"
    assert len(data["frames"]) == report["frames_processed"] == 2
    assert inspect_video(output / "overlay.mp4").frame_count == 2
    tracking = json.loads((output / "tracking.json").read_text())
    assert tracking["status"] == "cancelled" and len(tracking["frames"]) == 2


def test_inference_failure_is_not_completed(clip, tmp_path):
    class FailingBackend(StubBackend):
        def infer(self, frame):
            if self.calls == 2:
                raise Pose2DError("inference failed")
            return super().infer(frame)

    output = tmp_path / "failed"
    with pytest.raises(Pose2DError, match="inference failed"):
        process_pose2d(clip, output, FailingBackend())
    data = json.loads((output / "pose2d.json").read_text())
    report = json.loads((output / "report.json").read_text())
    assert data["status"] == report["status"] == "failed"
    assert len(data["frames"]) == 2
    tracking = json.loads((output / "tracking.json").read_text())
    assert tracking["status"] == "failed" and len(tracking["frames"]) == 2


def test_estimated_count_mismatch_is_explicit_warning(clip, tmp_path, monkeypatch):
    from dataclasses import replace
    metadata = inspect_video(clip)
    monkeypatch.setattr("app.processing.inspect_video", lambda _: replace(metadata, frame_count=7))
    output = tmp_path / "count-mismatch"
    report = process_pose2d(clip, output, StubBackend())
    assert report["status"] == "completed_with_warnings"
    assert report["frames_processed"] == 6
    assert not report["frame_count_matches_metadata"]
    assert "decoded_frame_count_differs_from_metadata" in report["warnings"]


def test_missing_model_does_not_download(tmp_path, monkeypatch):
    import rtmlib.tools.base as base

    def deny(*args, **kwargs):
        pytest.fail("Runtime must not download a model")

    monkeypatch.setattr(base, "download_checkpoint", deny)
    with pytest.raises(Pose2DError, match="model"):
        RTMPoseBackend(tmp_path)


def test_model_integrity_and_path_validation(tmp_path):
    manifest = {role: {"file": "fake.onnx", "sha256": "bad"} for role in ("detector", "pose")}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "fake.onnx").write_bytes(b"bad model")
    with pytest.raises(Pose2DError, match="integrity"):
        validate_models(tmp_path)
    manifest["detector"]["file"] = "../escape.onnx"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(Pose2DError, match="filename"):
        validate_models(tmp_path)


def test_actual_model_empty_frame_offline(monkeypatch):
    model_dir = Path(__file__).resolve().parents[1] / "models" / "pose2d"
    if not (model_dir / "rtmpose-m.onnx").is_file():
        pytest.skip("Local models are required for this integration test")

    def deny(*args, **kwargs):
        pytest.fail("Network access attempted during local inference")

    monkeypatch.setattr(socket.socket, "connect", deny)
    import rtmlib.tools.base as base
    monkeypatch.setattr(base, "download_checkpoint", deny)
    backend = RTMPoseBackend(model_dir)
    try:
        result = backend.infer(np.zeros((240, 320, 3), np.uint8))
        assert result.people_detected == 0
        assert result.keypoints == ()
    finally:
        backend.close()


@pytest.mark.parametrize("args", [["missing.mp4", "--pose2d"],
                                 ["missing.mp4", "--output", "out"],
                                 ["missing.mp4", "--target-index", "0"],
                                 ["missing.mp4", "--pose2d", "--output", "out", "--target-index", "-1"],
                                 ["missing.mp4", "--pose2d", "--list-targets"],
                                 ["missing.mp4", "--pose2d", "--output", "out", "--target-index", "0",
                                  "--target-box", "1", "1", "2", "2"],
                                 ["missing.mp4", "--preview-output", "preview.png"]])
def test_cli_argument_validation(args):
    run = subprocess.run([sys.executable, "-m", "app.cli", *args],
                         capture_output=True, text=True, timeout=20)
    assert run.returncode == 2
    assert "Traceback" not in run.stderr


def test_candidate_preview_is_numbered_output_and_never_overwrites(clip, tmp_path):
    model_dir = Path(__file__).resolve().parents[1] / "models" / "pose2d"
    if not (model_dir / "rtmpose-m.onnx").is_file():
        pytest.skip("Local models required")
    preview = tmp_path / "candidate.png"
    command = [sys.executable, "-m", "app.cli", str(clip), "--list-targets",
               "--preview-output", str(preview)]
    first = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)["candidates"] == []
    original = preview.read_bytes()
    image = cv2.imdecode(np.frombuffer(original, np.uint8), cv2.IMREAD_COLOR)
    assert image.shape[:2] == (240, 320)
    second = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert second.returncode == 1
    assert "new, writable filename" in second.stderr
    assert preview.read_bytes() == original
