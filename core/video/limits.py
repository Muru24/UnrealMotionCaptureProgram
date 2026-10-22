"""Shared processing limits; metadata inspection has its own decode safeguards."""
from core.video.decoder import VideoInputError

MAX_VIDEO_SECONDS = 300
MAX_VIDEO_FRAMES = 18000


def validate_duration(metadata, error_type=VideoInputError):
    if (metadata.duration_seconds_estimate > MAX_VIDEO_SECONDS
            or metadata.frame_count > MAX_VIDEO_FRAMES):
        raise error_type('현재 추출은 5분(300초) / 18,000프레임 이하 영상을 지원합니다.')
