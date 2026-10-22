"""MediaPipe's native 33-joint schema; not the future Motion JSON."""

from dataclasses import asdict, dataclass

from core.pose2d.interface import Pose2DResult


LANDMARK33 = (
    'nose', 'left_eye_inner', 'left_eye', 'left_eye_outer',
    'right_eye_inner', 'right_eye', 'right_eye_outer', 'left_ear', 'right_ear',
    'mouth_left', 'mouth_right', 'left_shoulder', 'right_shoulder',
    'left_elbow', 'right_elbow', 'left_wrist', 'right_wrist',
    'left_pinky', 'right_pinky', 'left_index', 'right_index',
    'left_thumb', 'right_thumb', 'left_hip', 'right_hip', 'left_knee',
    'right_knee', 'left_ankle', 'right_ankle', 'left_heel', 'right_heel',
    'left_foot_index', 'right_foot_index',
)
COCO_TO_MP = (0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28)
CONNECTIONS33 = (
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8), (9, 10),
    (11, 12), (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (17, 19),
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20),
    (11, 23), (12, 24), (23, 24), (23, 25), (24, 26), (25, 27), (26, 28),
    (27, 29), (28, 30), (29, 31), (30, 32), (27, 31), (28, 32),
)


class Pose3DError(ValueError):
    """Expected local model, inference or export error."""


@dataclass(frozen=True)
class Landmark3D:
    # None explicitly represents missing or nonfinite measurements.
    x: float | None
    y: float | None
    z: float | None
    image_x: float | None
    image_y: float | None
    image_z_normalized: float | None
    visibility: float | None
    presence: float | None
    valid: bool
    reason: str


@dataclass(frozen=True)
class Pose3DResult:
    pose2d: Pose2DResult
    landmarks: tuple[Landmark3D, ...]

    def to_dict(self):
        return {'person_bbox': self.pose2d.person_bbox,
                'landmarks': [asdict(p) for p in self.landmarks]}


def missing_landmarks(reason):
    return tuple(Landmark3D(None, None, None, None, None, None,
                            None, None, False, reason) for _ in LANDMARK33)
