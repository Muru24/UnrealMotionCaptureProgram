"""CPU preview of existing SAM hand projections; no inference or bone changes."""
from pathlib import Path
from uuid import uuid4
import json,math
import cv2,numpy as np
from app.knee_job import load_context,digest


def hand_chains(names):
    if len(names)!=70 or len(set(names))!=70:raise ValueError('Expected named MHR70 joints.')
    index={n:i for i,n in enumerate(names)};result={}
    for side in ('left','right'):
        try:
            result[side]=[[index[side+'-wrist']]+[index[f'{side}-{finger}-{joint}'] for joint in ('third-joint','second-joint','first-joint','tip')] for finger in ('thumb','index','middle','ring','pinky')]
        except KeyError as exc:raise ValueError('Missing hand joint names.') from exc
    return result


def draw_hands(image,points,chains):
    h,w=image.shape[:2];canvas=image.copy();panels=[];counts={}
    for side,color in [('left',(90,220,70)),('right',(60,140,255))]:
        panel=np.full((360,360,3),(20,16,12),np.uint8)
        ids=sorted({i for chain in chains[side] for i in chain})
        p=points[ids] if points is not None else np.full((21,2),np.nan)
        visible=np.isfinite(p).all(axis=1)&(p[:,0]>=0)&(p[:,0]<w)&(p[:,1]>=0)&(p[:,1]<h)
        counts[side]=int(visible.sum());valid_points=p[visible]
        usable=len(valid_points)>=4 and np.max(np.ptp(valid_points,axis=0))>=4
        if usable:
            for chain in chains[side]:
                for a,b in zip(chain,chain[1:]):
                    pair=points[[a,b]]
                    if np.isfinite(pair).all() and (pair[:,0]>=0).all() and (pair[:,0]<w).all() and (pair[:,1]>=0).all() and (pair[:,1]<h).all():
                        cv2.line(canvas,tuple(np.rint(pair[0]).astype(int)),tuple(np.rint(pair[1]).astype(int)),color,1,cv2.LINE_AA)
            for pt in valid_points:cv2.circle(canvas,tuple(np.rint(pt).astype(int)),2,color,-1,cv2.LINE_AA)
            lo=valid_points.min(axis=0);hi=valid_points.max(axis=0);center=(lo+hi)/2
            size=min(max(w,h),max(80.,float(max(hi-lo))*1.7));x0=max(0,int(center[0]-size/2));y0=max(0,int(center[1]-size/2));x1=min(w,int(center[0]+size/2));y1=min(h,int(center[1]+size/2))
            crop=image[y0:y1,x0:x1];ratio=min(360/crop.shape[1],320/crop.shape[0]);crop=cv2.resize(crop,(max(1,round(crop.shape[1]*ratio)),max(1,round(crop.shape[0]*ratio))))
            x=(360-crop.shape[1])//2;y=35+(320-crop.shape[0])//2;panel[y:y+crop.shape[0],x:x+crop.shape[1]]=crop
            projected=(points-[x0,y0])*ratio+[x,y]
            for chain in chains[side]:
                for a,b in zip(chain,chain[1:]):
                    pair=projected[[a,b]]
                    if np.isfinite(pair).all() and (pair>=0).all() and (pair<360).all():
                        cv2.line(panel,tuple(np.rint(pair[0]).astype(int)),tuple(np.rint(pair[1]).astype(int)),color,1,cv2.LINE_AA)
            for pt in projected[ids]:
                if np.isfinite(pt).all() and (pt>=0).all() and (pt<360).all():cv2.circle(panel,tuple(np.rint(pt).astype(int)),2,color,-1,cv2.LINE_AA)
        else:cv2.putText(panel,'No usable projection',(20,180),cv2.FONT_HERSHEY_SIMPLEX,.65,(160,160,160),1,cv2.LINE_AA)
        cv2.putText(panel,f'{side.upper()} hand - model estimate',(10,24),cv2.FONT_HERSHEY_SIMPLEX,.55,color,1,cv2.LINE_AA);panels.append(panel)
    width=max(2,round(w*720/h)//2*2);canvas=cv2.resize(canvas,(width,720));cv2.putText(canvas,'SAM projected joints - NOT verified tracking',(8,24),cv2.FONT_HERSHEY_SIMPLEX,.45,(255,255,255),1,cv2.LINE_AA)
    return np.concatenate((canvas,np.concatenate(panels,axis=0)),axis=1),counts


def generate_hand_preview(folder,cancelled=lambda:False,progress=lambda *a:None):
    if cancelled():raise KeyboardInterrupt
    folder=Path(folder).resolve();request=json.loads((folder/'sam-request.json').read_text(encoding='utf-8'));source=Path(request['source'])
    raw,source_hash,_=load_context(folder,source);chains=hand_chains(raw.get('joint_names',[]));raw_hash=digest(folder/'sam3d.json')
    fps=float(raw['video']['fps']);frames=raw['frames']
    if not math.isfinite(fps) or not 1<=fps<=240 or not 0<len(frames)<=18000:raise ValueError('Invalid hand preview timeline.')
    out=folder/('hands_'+uuid4().hex[:8]);out.mkdir();path=out/'hand-preview.mp4';cap=cv2.VideoCapture(str(source));writer=None;report={'status':'running','source_sha256':source_hash,'raw_sha256':raw_hash,'model_projections_not_ground_truth':True,'frames':[]}
    try:
        if not cap.isOpened():raise ValueError('Cannot decode original video.')
        for i,row in enumerate(frames):
            if cancelled():raise KeyboardInterrupt
            ok,image=cap.read()
            if not ok:raise ValueError('Hand preview video timeline differs.')
            points=(row.get('outputs') or {}).get('pred_keypoints_2d');points=None if points is None else np.asarray(points,float)
            if points is not None and (points.shape!=(70,2) or np.isinf(points).any()):raise ValueError('Invalid projected hand coordinates.')
            rendered,counts=draw_hands(image,points,chains)
            cv2.putText(rendered,f'Frame {i} / {i/fps:.3f}s',(8,48),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1,cv2.LINE_AA)
            if writer is None:
                writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),fps,(rendered.shape[1],720))
                if not writer.isOpened():raise RuntimeError('Hand preview encoder unavailable.')
            writer.write(rendered);report['frames'].append({'frame_index':i,'in_frame_projected_joints':counts});progress(i+1,len(frames))
        if cancelled():raise KeyboardInterrupt
        if digest(source)!=source_hash or digest(folder/'sam3d.json')!=raw_hash:raise ValueError('Hand preview inputs changed.')
        report['status']='completed'
    except KeyboardInterrupt:report['status']='cancelled';raise
    except Exception:report['status']='failed';raise
    finally:
        cap.release()
        if writer is not None:writer.release()
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return path
