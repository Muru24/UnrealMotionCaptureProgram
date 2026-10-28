"""Compose synchronized original/tracking/rendered-model frames for app playback."""
import sys,json,math
from pathlib import Path
import cv2
import numpy as np


def fit(image,w=512,h=600):
    scale=min(w/image.shape[1],h/image.shape[0]);small=cv2.resize(image,(max(1,round(image.shape[1]*scale)),max(1,round(image.shape[0]*scale))))
    result=np.full((h,w,3),(20,16,12),np.uint8);y=(h-small.shape[0])//2;x=(w-small.shape[1])//2;result[y:y+small.shape[0],x:x+small.shape[1]]=small;return result


def run(source,tracking,frames,output):
    frames=Path(frames);output=Path(output);info=json.loads((frames/'render.json').read_text());fps=float(info['fps']);n=int(info['frames'])
    if n<1 or not math.isfinite(fps) or fps<1:raise ValueError('Invalid render timeline')
    if output.exists():raise FileExistsError(output)
    model_output=output.with_name('model-preview.mp4')
    if model_output.exists() or model_output.with_suffix('.json').exists():raise FileExistsError(model_output)
    captures=[cv2.VideoCapture(str(p)) for p in (source,tracking)];writer=None;model_writer=None;model_size=None
    try:
        if not all(cap.isOpened() for cap in captures):raise ValueError('Source or tracking video unavailable')
        if any(abs(cap.get(cv2.CAP_PROP_FPS)-fps)>.02 for cap in captures):raise ValueError('Preview frame rates differ')
        writer=cv2.VideoWriter(str(output),cv2.VideoWriter_fourcc(*'mp4v'),fps,(1536,640))
        if not writer.isOpened():raise RuntimeError('Video encoder unavailable')
        for i in range(n):
            images=[]
            for cap in captures:
                ok,image=cap.read()
                if not ok:raise ValueError(f'Missing video frame {i}')
                images.append(image)
            extension=info.get('image_extension','png')
            if extension not in ('png','jpg'):raise ValueError('Invalid render format')
            model_path=frames/f'{i+1:05d}.{extension}'
            if not model_path.is_file():raise ValueError(f'Missing model frame {i}')
            model=cv2.imdecode(np.fromfile(model_path,dtype=np.uint8),cv2.IMREAD_COLOR)
            if model is None:raise ValueError(f'Missing model frame {i}')
            if model_writer is None:
                model_size=(model.shape[1],model.shape[0])
                model_writer=cv2.VideoWriter(str(model_output),cv2.VideoWriter_fourcc(*'mp4v'),fps,model_size)
                if not model_writer.isOpened():raise RuntimeError('Model-only encoder unavailable')
            if (model.shape[1],model.shape[0])!=model_size:raise ValueError('Model render dimensions differ')
            model_writer.write(model)
            panels=[]
            for image,title in zip(images+[model],['Original video','Body tracking','Applied model']):
                panel=np.full((640,512,3),(20,16,12),np.uint8);panel[40:]=fit(image);cv2.putText(panel,f'{title} | {i/fps:.2f}s',(12,27),cv2.FONT_HERSHEY_SIMPLEX,.55,(230,230,230),1,cv2.LINE_AA);panels.append(panel)
            writer.write(np.concatenate(panels,axis=1))
    finally:
        for cap in captures:cap.release()
        if writer is not None:writer.release()
        if model_writer is not None:model_writer.release()
    verify=cv2.VideoCapture(str(output));count=round(verify.get(cv2.CAP_PROP_FRAME_COUNT));verify.release()
    if count!=n:raise ValueError('Encoded frame count differs')
    verify=cv2.VideoCapture(str(model_output));model_count=round(verify.get(cv2.CAP_PROP_FRAME_COUNT));verify.release()
    if model_count!=n:raise ValueError('Model-only frame count differs')
    model_output.with_suffix('.json').write_text(json.dumps({'schema':'model_preview_v1','status':'completed',
        'source':str(Path(source).resolve()),'tracking':str(Path(tracking).resolve()),'frames':n,'fps':fps,
        'model_frames':str(frames.resolve()),'silent':True},ensure_ascii=False,indent=2),encoding='utf-8')
    output.with_suffix('.json').write_text(json.dumps({'status':'completed','source':str(source),'tracking':str(tracking),'model_frames':str(frames),'frames':n,'fps':fps,'panels':['original','tracking','model'],'silent':True},ensure_ascii=False,indent=2),encoding='utf-8')
    print('MODEL_COMPARISON',n,str(output))


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
