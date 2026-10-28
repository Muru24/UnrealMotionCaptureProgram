"""Original hand crop beside the rendered prop-contact review, at source time."""
import sys,json,math
from pathlib import Path
import cv2
import numpy as np


def run(video,raw_path,renders,output):
    renders=Path(renders);output=Path(output);raw=json.loads(Path(raw_path).read_text(encoding='utf-8'));info=json.loads((renders/'render.json').read_text());grip=json.loads((renders.parent/'report.json').read_text(encoding='utf-8'));count=len(raw['frames']);fps=raw['video']['fps']
    if info['frames']!=count or abs(info['fps']-fps)>.002:raise ValueError('Grip preview timelines differ')
    if output.exists():raise FileExistsError(output)
    cap=cv2.VideoCapture(str(video));writer=cv2.VideoWriter(str(output),cv2.VideoWriter_fourcc(*'mp4v'),fps,(1280,680))
    if not cap.isOpened() or not writer.isOpened():raise ValueError('Preview codec unavailable')
    try:
        for i,row in enumerate(raw['frames']):
            ok,image=cap.read()
            if not ok:raise ValueError(f'Original frame {i} unavailable')
            panel=np.full((680,1280,3),(20,16,12),np.uint8);q=(row.get('outputs') or {}).get('pred_keypoints_2d')
            if q:
                wrists=np.asarray([q[41],q[62]],float)
                if np.isfinite(wrists).all():
                    center=wrists.mean(0);size=max(140,float(np.linalg.norm(wrists[0]-wrists[1]))*2+80);h,w=image.shape[:2];x0=max(0,round(center[0]-size/2));x1=min(w,round(center[0]+size/2));y0=max(0,round(center[1]-size/2));y1=min(h,round(center[1]+size/2))
                    if x1>x0 and y1>y0:
                        crop=image[y0:y1,x0:x1];scale=min(640/crop.shape[1],640/crop.shape[0]);small=cv2.resize(crop,(round(crop.shape[1]*scale),round(crop.shape[0]*scale)));y=40+(640-small.shape[0])//2;x=(640-small.shape[1])//2;panel[y:y+small.shape[0],x:x+small.shape[1]]=small
            extension=info.get('image_extension','png')
            if extension not in ('png','jpg'):raise ValueError('Invalid render format')
            model_path=renders/f'{i+1:05d}.{extension}';model=cv2.imdecode(np.frombuffer(model_path.read_bytes(),np.uint8),cv2.IMREAD_COLOR)
            if model is None:raise ValueError(f'Model frame {i} unavailable')
            panel[40:,640:]=cv2.resize(model,(640,640));connected=grip['frame_results'][i]['secondary_connected'];status='two-hand contact' if connected else 'right hand / left rejected'
            cv2.putText(panel,f'Original hands | {i/fps:.2f}s',(12,27),cv2.FONT_HERSHEY_SIMPLEX,.6,(235,235,235),1,cv2.LINE_AA);cv2.putText(panel,'Model grip | '+status,(652,27),cv2.FONT_HERSHEY_SIMPLEX,.6,(100,220,140) if connected else (60,160,250),1,cv2.LINE_AA);writer.write(panel)
    finally:cap.release();writer.release()
    verify=cv2.VideoCapture(str(output));frames=round(verify.get(cv2.CAP_PROP_FRAME_COUNT));verify.release();assert frames==count
    output.with_suffix('.json').write_text(json.dumps({'status':'completed','frames':count,'fps':fps,'scope':'visual comparison, estimated prop pose and approximate bone-capsule contact'},indent=2),encoding='utf-8');print('GRIP_VIDEO',count,flush=True)


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
