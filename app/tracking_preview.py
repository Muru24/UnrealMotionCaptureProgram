"""Separate original/tracking assets and timestamp-based companion decoding."""
import json
import math
from pathlib import Path
import cv2


def tracking_assets(folder, source=None):
    original=Path(source) if source else None
    tracking=None
    if folder:
        folder=Path(folder)
        tracking=folder/'overlay.mp4'
        if original is None:
            for name in ('sam-request.json','gui-preview.json'):
                metadata=folder/name
                try:
                    if metadata.stat().st_size>1024*1024:continue
                    value=json.loads(metadata.read_text(encoding='utf-8')).get('source')
                    if isinstance(value,str) and value and '://' not in value:
                        original=Path(value)
                        if not original.is_absolute():original=folder/original
                        break
                except (OSError,ValueError,AttributeError):pass
    return (original if original and original.is_file() else None,
            tracking if tracking and tracking.is_file() else None)


class CompanionVideo:
    def __init__(self,path,label='트래킹'):
        self.path=Path(path)
        self.capture=cv2.VideoCapture()
        if not self.capture.open(str(path),cv2.CAP_FFMPEG,
                [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,5000,cv2.CAP_PROP_READ_TIMEOUT_MSEC,5000]):
            self.close();raise ValueError(f'{label} 영상을 열 수 없습니다.')
        self.fps=self.capture.get(cv2.CAP_PROP_FPS)
        self.count=int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(self.fps) or self.fps<=0 or self.count<=0:
            self.close();raise ValueError(f'{label} 영상의 시간 정보를 읽을 수 없습니다.')
        self.last_index=None;self.last_frame=None

    def frame_at(self,seconds):
        # A short result must not freeze its last pose while the source continues.
        index=round(seconds*self.fps)
        if index<0 or index>=self.count:return None
        if index==self.last_index:return self.last_frame
        if int(self.capture.get(cv2.CAP_PROP_POS_FRAMES))!=index:
            self.capture.set(cv2.CAP_PROP_POS_FRAMES,index)
        ok,frame=self.capture.read()
        self.last_index=index;self.last_frame=frame if ok else None
        return self.last_frame

    def close(self):
        self.capture.release()
