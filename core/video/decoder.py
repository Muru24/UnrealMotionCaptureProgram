"""Read local MP4 metadata without loading the entire video."""

from dataclasses import asdict, dataclass
import math
from pathlib import Path

import cv2


class VideoInputError(ValueError):
    """An input cannot safely be inspected as a supported video."""


@dataclass(frozen=True)
class VideoMetadata:
    width: int
    height: int
    fps: float
    frame_count: int
    duration_seconds_estimate: float
    size_bytes: int

    def to_dict(self) -> dict:
        return asdict(self)


def inspect_video(source: str | Path) -> VideoMetadata:
    path = Path(source).expanduser()
    # Only local regular files are allowed; never pass URLs to VideoCapture.
    if str(source).startswith(("\\\\", "//")) or "://" in str(source):
        raise VideoInputError("Only local files are supported.")
    try:
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            raise VideoInputError("Symbolic links are not supported.")
        if not path.is_file():
            raise VideoInputError("Input file does not exist or is not a regular file.")
        if path.suffix.lower() != ".mp4":
            raise VideoInputError("M0 supports MP4 files only.")
        size = path.stat().st_size
        if size == 0 or size > 2 * 1024**3:
            raise VideoInputError("Input must be non-empty and at most 2 GiB.")
        with path.open("rb") as stream:
            header = stream.read(12)
        if len(header) < 12 or header[4:8] != b"ftyp":
            raise VideoInputError("Input does not have a supported MP4 signature.")
        return _read_metadata(path.resolve(), size)
    except OSError as exc:
        raise VideoInputError("Cannot access input file.") from exc


def _read_metadata(path: Path, size: int) -> VideoMetadata:
    capture = cv2.VideoCapture()
    try:
        opened = capture.open(
            str(path), cv2.CAP_FFMPEG,
            [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
             cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000],
        )
        if not opened:
            raise VideoInputError("Cannot open video: damaged file or unsupported codec.")
        values = [capture.get(prop) for prop in (
            cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT,
            cv2.CAP_PROP_FPS, cv2.CAP_PROP_FRAME_COUNT,
        )]
        if any(not math.isfinite(v) or v <= 0 for v in values):
            raise VideoInputError("Video metadata is missing or invalid.")
        width, height, fps, frames = values
        if width > 7680 or height > 7680 or width * height > 7680 * 4320:
            raise VideoInputError("Video exceeds the M0 decode resolution limit.")
        ok, frame = capture.read()
        if not ok or frame is None or frame.size == 0:
            raise VideoInputError("Cannot decode the first video frame.")
        return VideoMetadata(int(width), int(height), fps, int(frames), frames / fps, size)
    except cv2.error as exc:
        raise VideoInputError("Video decoder failed.") from exc
    finally:
        capture.release()
