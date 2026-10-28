"""GUI worker operations; no Tk calls from the processing thread."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import re
from uuid import uuid4

import cv2

from core.video.decoder import VideoInputError, inspect_video
from core.video.limits import validate_duration

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class JobSettings:
    stage: str = 'pose3d'
    single_person: bool = True
    target_index: int | None = None
    anchors: dict | None = None
    tracking_method: str = 'pose'
    target_frame: int | None = None

    def __post_init__(self):
        if self.tracking_method not in ('pose','sam2') or (self.tracking_method=='sam2' and self.stage!='sam3d'):
            raise ValueError('Unsupported target tracking method.')
        if self.stage not in ('pose2d', 'pose3d', 'sam3d'):
            raise ValueError('Unsupported processing mode.')
        if self.target_index is not None and (type(self.target_index) is not int or self.target_index < 0):
            raise ValueError('Target index must be a nonnegative integer.')
        if self.target_frame is not None and (type(self.target_frame) is not int or self.target_frame < 0
                or self.stage!='sam3d' or self.tracking_method!='sam2'):
            raise ValueError('Target frame requires a nonnegative SAM2 source frame.')


def parse_drop(tcl, data):
    # Windows paths with spaces/braces are a Tcl list, not shell arguments.
    paths = tcl.splitlist(data)
    if len(paths) != 1:
        raise ValueError('한 번에 MP4 영상 하나만 넣어 주세요.')
    return Path(paths[0])


def new_output(source, stage, directory=None):
    folder = Path(directory) if directory is not None else ROOT/'outputs'
    stem = re.sub(r'[^\w .-]', '_', Path(source).stem)[:60].strip(' .') or 'video'
    stamp = datetime.now(timezone(timedelta(hours=9))).strftime('%Y%m%d_%H%M%S')
    return folder/f'{stem}_{stage}_{stamp}_{uuid4().hex[:8]}'


def read_source(source):
    metadata = inspect_video(source)
    validate_duration(metadata)
    if max(metadata.width,metadata.height) > 1920 or metadata.width%2 or metadata.height%2:
        raise VideoInputError('가로·세로 최대 1920px, 짝수 해상도의 MP4를 사용해 주세요.')
    capture = cv2.VideoCapture()
    try:
        if not capture.open(str(Path(source).resolve()), cv2.CAP_FFMPEG,
                            [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                             cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000]):
            raise VideoInputError('Cannot open the selected video.')
        ok, frame = capture.read()
        if not ok:
            raise VideoInputError('Cannot decode the selected video.')
        return metadata, frame
    finally:
        capture.release()


def make_backend(settings):
    if settings.stage == 'sam3d':
        from core.pose2d.rtmpose_backend import RTMPoseBackend
        return RTMPoseBackend(ROOT/'models/pose2d', target_index=settings.target_index, detector_only=True,
                              association_pose=settings.tracking_method!='sam2')
    if settings.stage == 'pose3d':
        from core.pose3d.mediapipe_backend import MediaPipeBackend
        return MediaPipeBackend(ROOT/'models/pose3d', target_index=settings.target_index,
                                 max_people=1 if settings.single_person else 4)
    from core.pose2d.rtmpose_backend import RTMPoseBackend
    return RTMPoseBackend(ROOT/'models/pose2d', target_index=settings.target_index)


def inspect_candidates(source, settings, cancelled, backend_factory=None, *, include_frame_index=False):
    _, frame = read_source(source)
    if cancelled():
        raise KeyboardInterrupt
    if settings.tracking_method=='sam2':
        from app.target_start import find_target_start
        index,frame,boxes=find_target_start(source,settings,cancelled,backend_factory or make_backend)
        draw_candidates(frame,boxes)
        return (frame,len(boxes),index) if include_frame_index else (frame,len(boxes))
    backend = (backend_factory or make_backend)(settings)
    try:
        boxes = backend.detect(frame)
        if cancelled():
            raise KeyboardInterrupt
        draw_candidates(frame,boxes)
        return (frame,len(boxes),0) if include_frame_index else (frame,len(boxes))
    finally:
        backend.close()


def draw_candidates(frame,boxes):
    for i,box in enumerate(boxes):
        x1,y1,x2,y2=map(int,box)
        cv2.rectangle(frame,(x1,y1),(x2,y2),(0,220,255),2)
        cv2.putText(frame,f'TARGET {i}',(x1,max(25,y1-8)),
                    cv2.FONT_HERSHEY_SIMPLEX,.7,(0,220,255),2,cv2.LINE_AA)


def run_job(source, output, settings, cancelled, progress, backend_factory=None):
    if cancelled():
        raise KeyboardInterrupt
    if settings.stage == 'sam3d':
        from app.sam3d_job import run_sam3d
        return run_sam3d(source, output, settings, cancelled, progress,
                         backend_factory or make_backend)
    backend = (backend_factory or make_backend)(settings)
    try:
        if cancelled():
            raise KeyboardInterrupt
        if settings.stage == 'pose3d':
            from app.processing3d import process_pose3d
            result=process_pose3d(source, output, backend, progress=progress, cancelled=cancelled,
                                  anchors=settings.anchors)
        else:
            from app.processing import process_pose2d
            result=process_pose2d(source, output, backend, progress=progress, cancelled=cancelled)
        with (Path(output)/'gui-preview.json').open('x',encoding='utf-8') as stream:
            json.dump({'schema':'tracking_preview_v1','source':str(Path(source).resolve()),
                       'tracking':'overlay.mp4'},stream,ensure_ascii=False,indent=2)
        return result
    finally:
        backend.close()
