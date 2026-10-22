"""Offline second pass on an existing raw output directory."""
import json
from pathlib import Path
from uuid import uuid4
import cv2
import numpy as np

from core.pose3d.completion import complete
from core.pose3d.interface import CONNECTIONS33


def local(path):
    path=Path(path)
    if str(path).startswith(('\\\\','//')) or '://' in str(path) or path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('Choose local regular output files.')
    return path


def read(path):
    path=local(path)
    if path.stat().st_size>96*1024*1024:raise ValueError('Completion input exceeds 96MiB.')
    return json.loads(path.read_text(encoding='utf-8'))


def render(raw, repaired, connections=CONNECTIONS33, scale=150):
    canvas=np.full((720,1280,3),24,np.uint8)
    raw_title='RAW SAM | includes hidden model guesses' if len(raw['landmarks'])==70 else 'RAW'
    for col,title in enumerate((raw_title,'COMPLETED | orange = inferred')):
        cv2.putText(canvas,title,(col*640+12,25),cv2.FONT_HERSHEY_SIMPLEX,.55,(240,240,240),1)
        for row,axis in enumerate((0,2)):
            origin=np.array([col*640+320,row*340+175])
            for a,b in connections:
                if col:
                    p,q=repaired['joints'][a],repaired['joints'][b]
                    u,v=p['xyz'],q['xyz']
                    inferred=p['source'] not in ('observed','length_constrained','offset_preserved') or q['source'] not in ('observed','length_constrained','offset_preserved')
                else:
                    p,q=raw['landmarks'][a],raw['landmarks'][b]
                    u=[p[k] for k in ('x','y','z')] if p.get('render_valid',p['valid']) else None
                    v=[q[k] for k in ('x','y','z')] if q.get('render_valid',q['valid']) else None
                    inferred=False
                if u is None or v is None:continue
                x=tuple(np.clip(origin+np.array([u[axis],u[1]])*scale,-10000,10000).astype(int))
                y=tuple(np.clip(origin+np.array([v[axis],v[1]])*scale,-10000,10000).astype(int))
                ok,x,y=cv2.clipLine((col*640,row*340+35,640,300),x,y)
                review=[a,b] in repaired.get('review_bones',[])
                if ok:cv2.line(canvas,x,y,(230,70,230) if review else (0,180,255) if inferred else (60,235,100),2,cv2.LINE_AA)
    if repaired.get('review_bones'):
        cv2.putText(canvas,'MAGENTA: review candidate (not confirmed error)',(380,50),cv2.FONT_HERSHEY_SIMPLEX,.5,(230,70,230),1)
    cv2.putText(canvas,f'Frame {raw["frame_index"]} | hip-relative | NO measured foot contact',
                (15,705),cv2.FONT_HERSHEY_SIMPLEX,.5,(230,230,230),1)
    if 'scene' in raw:
        label=f'SCENE {raw["scene"]["index"]}'
        if raw['scene']['cut']:label+=' | CUT - interpolation boundary'
        cv2.putText(canvas,label,(15,675),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,200,255),1)
    if len(raw['landmarks'])==70 and raw['person_bbox'] is None:
        cv2.putText(canvas,'TARGET LOST | NOT COMPLETED',(20,345),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,140,255),2)
    return canvas


def run_completion(source_dir, cancelled=lambda:False, progress=lambda *a:None):
    source_dir=local(source_dir)
    if cancelled():raise KeyboardInterrupt
    connections=CONNECTIONS33;scale=150
    if (source_dir/'sam3d.json').is_file():
        report=read(source_dir/'report.json')
        if report.get('status') not in ('completed','completed_with_warnings'):
            raise ValueError('Finish SAM extraction before completing feet.')
        from core.pose3d.sam_completion import complete_sam, CONNECTIONS
        raw,result=complete_sam(read(source_dir/'sam3d.json'),cancelled)
        if len(raw['frames'])!=report.get('frames_processed'):
            raise ValueError('Incomplete SAM timeline.')
        connections=CONNECTIONS
        extents=[max([abs(p[k]) for p in f['landmarks'] for k in ('x','y','z') if p[k] is not None]
                     +[abs(v) for p in result['frames'][i]['joints'] if p['xyz'] is not None for v in p['xyz']]+[.1])
                 for i,f in enumerate(raw['frames'])]
        scale=float(np.clip(130/max(float(np.quantile(extents,.95)),.1),40,400))
    else:
        raw=read(source_dir/'pose3d.json');tracking=read(source_dir/'tracking.json')
        if raw.get('schema')!='mediapipe33' or raw.get('coordinates')!='mediapipe_native_world_xyz':
            raise ValueError('Only native MediaPipe33 or SAM MHR70 outputs are supported.')
        if raw.get('status') not in ('completed','completed_with_warnings') or tracking.get('status') not in ('completed','completed_with_warnings'):
            raise ValueError('Finish first-pass extraction before completing motion.')
        result=complete(raw,tracking,cancelled)
    out=source_dir/('completion_'+uuid4().hex[:8]);out.mkdir(exist_ok=False)
    writer=None;status='failed';count=0
    try:
        writer=cv2.VideoWriter(str(out/'completion3d.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),raw['video']['fps'],(1280,720))
        if not writer.isOpened():raise ValueError('Cannot encode completion preview.')
        for a,b in zip(raw['frames'],result['frames']):
            if cancelled():raise KeyboardInterrupt
            writer.write(render(a,b,connections,scale));count+=1
            if count%15==0:progress(count,len(result['frames']))
        (out/'completion3d.json').write_text(json.dumps(result,allow_nan=False),encoding='utf-8')
        if 'quality_review' in result:
            navigation=dict(result['quality_review'])
            navigation['frames']=[{'frame_index':f['frame_index'],'bones':f['review_bones']} for f in result['frames']]
            navigation['summary']=result.get('review_summary',navigation['summary'])
            navigation['temporal_guard_events']=result.get('temporal_guard',{}).get('events',[])
            (out/'pose-quality.json').write_text(json.dumps(navigation,allow_nan=False),encoding='utf-8')
        status='completed_with_estimates'
    except KeyboardInterrupt:
        status='cancelled';raise
    finally:
        if writer is not None:writer.release()
        (out/'report.json').write_text(json.dumps({'status':status,'frames_written':count,
             'temporal_guard':{k:result['temporal_guard'][k] for k in ('repaired_joint_frames','review_frames','blocked')}
                              if 'temporal_guard' in result else None,
             'quality_review':result.get('review_summary',result.get('quality_review',{}).get('summary')),
             'counts':result['counts'],'limits':result['limits']},indent=2),encoding='utf-8')
    return out,result['counts']
