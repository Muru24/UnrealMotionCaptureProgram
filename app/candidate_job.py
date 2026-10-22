"""Four-hypothesis joint selection, independent of raw MHR rotations."""
from pathlib import Path
from uuid import uuid4
import json,subprocess,time,cv2,numpy as np
from app.knee_job import load_context,digest
from app.completion_job import read,render
from app.gui_jobs import ROOT
from core.pose3d.candidate_ranking import rank_candidates,BONES
from core.pose3d.sam_completion import CONNECTIONS
NAMES=('observed','stable','tight','stable-flip')

def latest_selection(folder,source_hash,inference_type='full'):
    folder=Path(folder);raw_hash=digest(folder/'sam3d.json')
    for out in sorted(folder.glob('candidates_*'),key=lambda p:p.stat().st_mtime,reverse=True):
        try:
            report=read(out/'report.json');data=read(out/'selected-joints.json')
            if report.get('candidate_inference_type','full')!=inference_type:continue
            if report.get('status')=='completed_with_estimates' and data.get('schema')=='candidate_joint_selection_not_mhr_animation' and data.get('source_sha256')==source_hash and data.get('raw_sha256')==raw_hash:return out
        except (OSError,ValueError,KeyError):pass
    return None

def choose(raw,variants,cancelled=lambda:False):
    frames=raw['frames'];samples=np.array([r['outputs']['pred_keypoints_3d'] for r in frames[:26] if r.get('outputs')])
    if not len(samples):raise ValueError('No reference poses in initial frames.')
    refs=np.median(np.stack([np.linalg.norm(samples[:,b]-samples[:,a],axis=-1) for a,b in BONES],axis=-1),axis=0)
    scale=float(np.median(np.linalg.norm((samples[:,5]+samples[:,6]-samples[:,9]-samples[:,10])/2,axis=-1)))
    pools=[];segments=[];rows=[]
    for i,r in enumerate(frames):
        if cancelled():raise KeyboardInterrupt
        prediction=r.get('outputs');v=variants.get(i,{})
        rows.append({'frame_index':i,'candidate':'raw','world_joints':None if prediction is None else prediction['pred_keypoints_3d'],
                     'image_joints':None if prediction is None else prediction['pred_keypoints_2d']})
        available=prediction is not None and r.get('person_bbox') is not None and all(k in v for k in ('observed','tight','stable-flip'))
        if not available:pools.append(None);segments.append(None);continue
        baseline={'world_joints':prediction['pred_keypoints_3d'],'image_joints':prediction['pred_keypoints_2d']}
        pools.append([v['observed'],baseline,v['tight'],v['stable-flip']]);segments.append((r.get('tracking_segment',0),r.get('scene',{}).get('index',0)))
    start=0;rankings=[]
    while start<len(frames):
        if pools[start] is None:start+=1;continue
        end=start+1
        while end<len(frames) and pools[end] is not None and segments[end]==segments[start]:end+=1
        xyz=np.array([[p['world_joints'] for p in group] for group in pools[start:end]])
        pixels=np.array([[p['image_joints'] for p in group] for group in pools[start:end]])
        diagonals=[np.linalg.norm(np.subtract(r['person_bbox'][2:],r['person_bbox'][:2])) for r in frames[start:end]]
        ranked=rank_candidates(xyz,pixels,refs,diagonals,scale)
        for t,k in enumerate(ranked['path'],start):
            rows[t].update(candidate=NAMES[k],world_joints=pools[t][k]['world_joints'],image_joints=pools[t][k]['image_joints'])
        rankings.append({'start':start,'end_exclusive':end,'ranking':ranked});start=end
    return rows,rankings

def save_selection(folder,source,raw,variants,cancelled=lambda:False,progress=lambda *a:None):
    rows,rankings=choose(raw,variants,cancelled);video=raw['video'];n=len(rows);folder=Path(folder)
    if not (folder/'candidates.json').exists():
        (folder/'candidates.json').write_text(json.dumps({'schema':'joint_candidates_only_not_mhr_animation',
            'joint_names':raw.get('joint_names'),'frames':[{'frame_index':i,'candidates':variants.get(i,{})} for i in range(n)]},allow_nan=False),encoding='utf-8')
    cap=cv2.VideoCapture(str(source));writer=None;status='failed';count=0
    try:
        writer=cv2.VideoWriter(str(folder/'candidate-overlay.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),video['fps'],(video['width']*2,video['height']))
        if not cap.isOpened() or not writer.isOpened():raise ValueError('Cannot open candidate comparison video.')
        for i,(old,row) in enumerate(zip(raw['frames'],rows)):
            if cancelled():raise KeyboardInterrupt
            ok,image=cap.read()
            if not ok:raise ValueError('Candidate source timeline mismatch.')
            pair=[]
            for points,title in ((None if old.get('outputs') is None else old['outputs']['pred_keypoints_2d'],'RAW SAM'),(row['image_joints'],'CANDIDATE '+row['candidate'])):
                view=image.copy()
                if points is not None:
                    p=np.asarray(points)
                    for a,b in CONNECTIONS:cv2.line(view,tuple(np.clip(p[a],-10000,10000).astype(int)),tuple(np.clip(p[b],-10000,10000).astype(int)),(50,230,100),2)
                cv2.putText(view,title,(12,30),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,200,255),2);pair.append(view)
            writer.write(np.concatenate(pair,axis=1));count+=1;progress(count,n)
        data={'schema':'candidate_joint_selection_not_mhr_animation','source_sha256':digest(source),
              'raw_sha256':digest(folder.parent/'sam3d.json'),'video':video,'frames':rows}
        (folder/'selected-joints.json').write_text(json.dumps(data,allow_nan=False),encoding='utf-8')
        (folder/'ranking.json').write_text(json.dumps(rankings,allow_nan=False),encoding='utf-8');status='completed_with_estimates'
    except KeyboardInterrupt:status='cancelled';raise
    finally:
        cap.release()
        if writer is not None:writer.release()
        report={'status':status,'frames_written':count,'selection_counts':{k:sum(r['candidate']==k for r in rows) for k in ('raw',)+NAMES},
                'limits':['joint_only_no_MHR_rotations','selection_is_not_accuracy_confidence','all_candidates_may_be_wrong']}
        (folder/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return folder,report

def run_candidates(folder,source,cancelled=lambda:False,progress=lambda *a:None,*,inference_type='full'):
    from app.sam3d_job import terminate_worker
    if inference_type not in ('full','body'):raise ValueError('Unsupported candidate inference type.')
    if cancelled():raise KeyboardInterrupt
    raw,source_hash,provenance=load_context(folder,source)
    if cancelled():raise KeyboardInterrupt
    folder=Path(folder);out=folder/('candidates_'+uuid4().hex[:8]);out.mkdir(exist_ok=False)
    request={'source':str(source),'source_sha256':source_hash,'start':0,'end_exclusive':len(raw['frames']),'frames':raw['frames'],'inference_type':inference_type}
    (out/'request.json').write_text(json.dumps(request),encoding='utf-8')
    python=ROOT/'.validation/sam3d/env/Scripts/python.exe'
    if not python.is_file():raise ValueError('Installed SAM GPU environment is missing.')
    with (out/'runtime.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen([str(python),'-u',str(ROOT/'app/candidate_worker.py'),str(out)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            while process.poll() is None:
                if cancelled():raise KeyboardInterrupt
                try:p=read(out/'progress.json');progress(p['done'],p['total'])
                except (OSError,ValueError):pass
                time.sleep(.15)
            if process.returncode:raise ValueError(f'후보 추론 실패: {out / "runtime.log"}')
        except BaseException:
            if process.poll() is None:terminate_worker(process)
            (out/'report.json').write_text(json.dumps({'status':'cancelled' if cancelled() else 'failed'}),encoding='utf-8');raise
    if digest(source)!=source_hash:raise ValueError('Source changed during inference.')
    data=read(out/'candidates.json')
    if data.get('inference_type','full')!=inference_type:raise ValueError('Candidate inference profile differs.')
    if data['joint_names']!=raw['joint_names'] or [r['frame_index'] for r in data['frames']]!=list(range(len(raw['frames']))):raise ValueError('Candidate timeline/joints differ.')
    result,report=save_selection(out,source,raw,{r['frame_index']:r['candidates'] for r in data['frames']},cancelled,progress)
    report['extraction_source_hash_verified']=provenance
    report['candidate_inference_type']=inference_type
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return result,report
