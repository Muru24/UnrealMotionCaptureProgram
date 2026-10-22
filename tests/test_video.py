import json
import subprocess
import sys

import cv2
import numpy as np
import pytest

from core.video.decoder import VideoInputError, inspect_video


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "테스트 영상.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (320, 240))
    assert writer.isOpened(), "Test MP4 encoder unavailable"
    try:
        for i in range(60):
            frame = np.zeros((240, 320, 3), dtype=np.uint8)
            cv2.rectangle(frame, (i, 30), (i + 30, 80), (0, 255, 0), -1)
            writer.write(frame)
    finally:
        writer.release()
    return path


def test_real_mp4(video):
    result = inspect_video(video)
    assert (result.width, result.height) == (320, 240)
    assert result.fps == pytest.approx(30)
    assert result.frame_count == 60
    assert result.duration_seconds_estimate == pytest.approx(2)


def test_cli_real_mp4(video):
    run = subprocess.run([sys.executable, "-m", "app.cli", str(video), "--json"],
                         capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["frame_count"] == 60


@pytest.mark.parametrize("kind", ["missing", "directory", "empty", "fake", "extension", "corrupt"])
def test_reject_invalid(tmp_path, kind):
    path = tmp_path / ("input.txt" if kind == "extension" else "input.mp4")
    if kind == "directory":
        path.mkdir()
    elif kind != "missing":
        path.write_bytes(b"" if kind == "empty" else
                         b"\x00\x00\x00\x18ftypisom" if kind == "corrupt" else b"not a video")
    with pytest.raises(VideoInputError):
        inspect_video(path)


@pytest.mark.parametrize("path", ["https://example.com/video.mp4", r"\\server\video.mp4"])
def test_reject_remote(path):
    with pytest.raises(VideoInputError, match="local"):
        inspect_video(path)


def test_cli_error(tmp_path):
    run = subprocess.run([sys.executable, "-m", "app.cli", str(tmp_path / "missing.mp4")],
                         capture_output=True, text=True, timeout=20)
    assert run.returncode == 1
    assert "Error:" in run.stderr
    assert "Traceback" not in run.stderr


@pytest.mark.parametrize("invalid", [0, -1, float("nan"), float("inf")])
def test_invalid_metadata_releases_decoder(video, monkeypatch, invalid):
    class Capture:
        released = False

        def open(self, *args):
            return True

        def get(self, prop):
            return invalid if prop == cv2.CAP_PROP_FPS else 30

        def release(self):
            self.released = True

    capture = Capture()
    monkeypatch.setattr(cv2, "VideoCapture", lambda: capture)
    with pytest.raises(VideoInputError, match="metadata"):
        inspect_video(video)
    assert capture.released
