"""Discover model-only previews and migrate explicitly described legacy triptychs."""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from uuid import uuid4
import cv2


@dataclass(frozen=True)
class ModelPreview:
    path: Path
    source: Path | None
    tracking: Path | None
    legacy: bool


def metadata(path):
    sidecar=Path(path).with_suffix('.json')
    try:
        if sidecar.is_symlink() or sidecar.stat().st_size>1024*1024:return None
        data=json.loads(sidecar.read_text(encoding='utf-8'))
        if not isinstance(data,dict) or data.get('status')!='completed':return None
        if data.get('schema')!='model_preview_v1' and data.get('panels')!=['original','tracking','model']:return None
        return data
    except (OSError,ValueError):return None


def local_path(value,parent):
    if not isinstance(value,str) or not value or '://' in value:return None
    p=Path(value)
    return p if p.is_absolute() else parent/p


def describe(path):
    path=Path(path)
    if not path.is_file() or path.is_symlink():return None
    data=metadata(path)
    if data is None:return None
    return ModelPreview(path,local_path(data.get('source'),path.parent),
                        local_path(data.get('tracking'),path.parent),data.get('schema')!='model_preview_v1')


def discover_models(root):
    from app.result_library import list_results,list_previews
    found=[]
    for row in list_results(root):
        for path in list_previews(root,row['path']):
            if path.name=='model-comparison.mp4' or path.name.startswith('model-preview'):
                item=describe(path)
                if item:found.append((row['path'],item))
    # Prefer a separated video over its legacy comparison in the same variant.
    found.sort(key=lambda pair:(pair[1].legacy,-pair[1].path.stat().st_mtime_ns))
    unique={}
    for folder,item in found:unique.setdefault(item.path.parent,(folder,item))
    return sorted(unique.values(),key=lambda pair:pair[1].path.stat().st_mtime_ns,reverse=True)


def model_asset(folder,selected):
    item=describe(selected) if selected else None
    if item:return item
    if not folder:return None
    folder=Path(folder)
    candidates=[*folder.glob('model-preview*.mp4'),folder/'model-comparison.mp4']
    if folder.is_dir():
        from app.result_library import list_previews
        candidates.extend(p for p in list_previews(folder.parent,folder) if p.name=='model-comparison.mp4' or p.name.startswith('model-preview'))
    candidates=sorted((p for p in candidates if p.is_file()),key=lambda p:p.stat().st_mtime_ns,reverse=True)
    for path in candidates:
        item=describe(path)
        if item:return item
    return None


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def encode_model_frames(source,tracking,frames,output,cancelled=lambda:False):
    import numpy as np
    frames=Path(frames);output=Path(output)
    info=json.loads((frames/'render.json').read_text(encoding='utf-8'));count=int(info['frames']);fps=float(info['fps'])
    extension=info.get('image_extension','png')
    if extension not in ('png','jpg'):raise ValueError('Invalid preview image extension')
    if count<1 or not math.isfinite(fps) or fps<=0:raise ValueError('Invalid model timeline')
    if output.exists() or output.with_suffix('.json').exists():raise FileExistsError(output)
    temp=output.with_name('.encode-'+uuid4().hex+'.mp4');writer=None
    try:
        size=None
        for i in range(count):
            if cancelled():raise KeyboardInterrupt
            frame=cv2.imdecode(np.fromfile(frames/f'{i+1:05d}.{extension}',dtype=np.uint8),cv2.IMREAD_COLOR)
            if frame is None:raise ValueError('Missing model render')
            if writer is None:
                size=(frame.shape[1],frame.shape[0]);writer=cv2.VideoWriter(str(temp),cv2.VideoWriter_fourcc(*'mp4v'),fps,size)
                if not writer.isOpened():raise RuntimeError('Model encoder unavailable')
            if (frame.shape[1],frame.shape[0])!=size:raise ValueError('Model dimensions differ')
            writer.write(frame)
        writer.release();writer=None
        cap=cv2.VideoCapture(str(temp));valid=cap.isOpened() and round(cap.get(cv2.CAP_PROP_FRAME_COUNT))==count;cap.release()
        if not valid:raise ValueError('Encoded model frame count differs')
        if cancelled():raise KeyboardInterrupt
        temp.rename(output)
        output.with_suffix('.json').write_text(json.dumps({'schema':'model_preview_v1','status':'completed',
            'source':str(Path(source).resolve()),'tracking':str(Path(tracking).resolve()),'fps':fps,'frames':count},ensure_ascii=False,indent=2),encoding='utf-8')
        return output
    finally:
        if writer is not None:writer.release()
        temp.unlink(missing_ok=True)


def cleanup_model_frames(frames,video):
    """Discard only numbered, generated frames after the final MP4 is verified."""
    frames,video=Path(frames),Path(video)
    if frames.is_symlink() or frames.resolve().parent!=video.resolve().parent or frames.name!='frames':return 0
    try:
        info=json.loads((frames/'render.json').read_text(encoding='utf-8'));meta=metadata(video)
        count=int(info['frames']);extension=info.get('image_extension','png')
        if extension not in ('png','jpg') or not meta or meta.get('frames')!=count:return 0
        cap=cv2.VideoCapture(str(video));valid=cap.isOpened() and round(cap.get(cv2.CAP_PROP_FRAME_COUNT))==count;cap.release()
        paths=[frames/f'{i+1:05d}.{extension}' for i in range(count)]
        if not valid or not all(p.is_file() and not p.is_symlink() for p in paths):return 0
        size=sum(p.stat().st_size for p in paths)
        for p in paths:p.unlink()
        return size
    except (OSError,ValueError,KeyError,TypeError):return 0


def prepare_model_preview(path,cancelled=lambda:False,progress=lambda *args:None):
    item=describe(path)
    if item is None:raise ValueError('모델 전용 영상 또는 모델 합본 메타데이터가 필요합니다.')
    if not item.legacy:return item.path
    if cancelled():raise KeyboardInterrupt
    source_hash=digest(item.path);data=metadata(item.path)
    signature=hashlib.sha256((source_hash+json.dumps(data,sort_keys=True)).encode()).hexdigest()[:12]
    output=item.path.with_name(f'model-preview-{signature}.mp4')
    prior=metadata(output)
    if prior and prior.get('legacy_sha256')==source_hash and output.is_file() and prior.get('video_sha256')==digest(output):return output
    if output.exists() or output.with_suffix('.json').exists():raise ValueError('기존 모델 미리보기와 이름이 충돌합니다.')
    temporary=output.with_name(f'.model-preview-{uuid4().hex}.mp4')
    capture=cv2.VideoCapture(str(item.path));writer=None
    try:
        width=round(capture.get(cv2.CAP_PROP_FRAME_WIDTH));height=round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps=capture.get(cv2.CAP_PROP_FPS);count=round(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        # This is the documented output of compose_model_preview, not guessed
        # cropping of arbitrary two/three-panel videos or hand close-ups.
        if not capture.isOpened() or (width,height)!=(1536,640) or count!=data.get('frames') or not math.isfinite(fps) or fps<=0 or abs(fps-float(data['fps']))>.02:
            raise ValueError('지원되는 3패널 모델 합본 형식이 아닙니다.')
        writer=cv2.VideoWriter(str(temporary),cv2.VideoWriter_fourcc(*'mp4v'),fps,(512,600))
        if not writer.isOpened():raise RuntimeError('모델 미리보기 인코더를 열 수 없습니다.')
        for index in range(count):
            if cancelled():raise KeyboardInterrupt
            ok,frame=capture.read()
            if not ok:raise ValueError(f'모델 합본의 {index}프레임을 읽을 수 없습니다.')
            writer.write(frame[40:640,1024:1536])
            progress(index+1,count)
        writer.release();writer=None;capture.release()
        verify=cv2.VideoCapture(str(temporary))
        valid=verify.isOpened() and round(verify.get(cv2.CAP_PROP_FRAME_COUNT))==count
        verify.release()
        if not valid:raise ValueError('분리한 모델 영상의 프레임 수가 다릅니다.')
        if cancelled():raise KeyboardInterrupt
        if digest(item.path)!=source_hash:raise ValueError('분리 중 원본 합본이 변경되었습니다.')
        temporary.rename(output)
        report={'schema':'model_preview_v1','status':'completed','source':str(item.source) if item.source else None,
                'tracking':str(item.tracking) if item.tracking else None,'frames':count,'fps':fps,
                'legacy_source':str(item.path),'legacy_sha256':source_hash,'video_sha256':digest(output)}
        with output.with_suffix('.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
        return output
    finally:
        capture.release()
        if writer is not None:writer.release()
        temporary.unlink(missing_ok=True)
