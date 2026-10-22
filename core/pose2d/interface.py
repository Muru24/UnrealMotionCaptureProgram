"""Pixel-space pose results; independent of Unreal and the Motion Skeleton."""

from dataclasses import asdict, dataclass
from typing import Protocol

import numpy as np


COCO17 = (
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
)
CONNECTIONS = (
    (0, 1), (0, 2), (1, 3), (2, 4), (5, 6), (5, 7), (7, 9),
    (6, 8), (8, 10), (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16),
)


class Pose2DError(ValueError):
    """An expected pose processing or output error."""


@dataclass(frozen=True)
class Keypoint2D:
    x: float
    y: float
    confidence: float
    valid: bool


@dataclass(frozen=True)
class TrackingInfo:
    state: str
    reason: str
    track_id: int | None
    missing_frames: int
    requires_reselection: bool


@dataclass(frozen=True)
class Pose2DResult:
    person_bbox: tuple[float, float, float, float] | None
    keypoints: tuple[Keypoint2D, ...]
    people_detected: int
    tracking: TrackingInfo | None = None
    joint_states: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        # Keep the original Pose2D payload; tracking diagnostics use a sidecar.
        return {"person_bbox": self.person_bbox,
                "keypoints": [asdict(p) for p in self.keypoints],
                "people_detected": self.people_detected}


class Pose2DBackend(Protocol):
    def infer(self, frame_bgr: np.ndarray) -> Pose2DResult: ...

    def close(self) -> None: ...
