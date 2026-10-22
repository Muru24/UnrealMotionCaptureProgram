"""Find the first detected person, or inspect an explicitly chosen source frame."""
from pathlib import Path
import cv2
from core.video.limits import MAX_VIDEO_FRAMES


def find_target_start(source, settings, cancelled, backend_factory):
    capture=cv2.VideoCapture(str(Path(source).resolve()))
    backend=None
    requested=getattr(settings,'target_frame',None)
    try:
        if cancelled():raise KeyboardInterrupt
        backend=backend_factory(settings)
        for index in range(MAX_VIDEO_FRAMES):
            if cancelled():raise KeyboardInterrupt
            ok,frame=capture.read()
            if not ok:break
            if requested is not None and index<requested:continue
            boxes=backend.detect(frame)
            if cancelled():raise KeyboardInterrupt
            if len(boxes) or requested is not None:return index,frame,boxes
        if requested is not None:
            raise ValueError('선택한 프레임이 영상에 없습니다. 원본 영상 위치를 다시 선택해 주세요.')
        raise ValueError('영상에서 인물 후보를 찾지 못했습니다. 영상 손상 판정이 아니며 인물이 보이는 구간을 확인해 주세요.')
    finally:
        capture.release()
        if backend is not None:backend.close()
