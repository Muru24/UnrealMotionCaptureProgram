"""Fresh shoe tracking and leg-focused inference on the current selected timeline."""
from pathlib import Path
from uuid import uuid4
import json,subprocess,time,cv2,numpy as np
from app.completion_job import read
from app.knee_job import load_context,digest
from app.gui_jobs import ROOT
from core.pose3d.shoe_evidence import regions_at,shoe_support
from core.pose3d.leg_estimation import propose
from core.pose3d.manual_leg_path import local_legs,select_path
from core.pose3d.sam_completion import CONNECTIONS

def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def latest_leg_result(folder,source_hash,selection):
    if selection is None:return None
    expected=digest(Path(selection)/'selected-joints.json')
    for out in sorted(Path(folder).glob('leg_reestimate_*'),key=lambda p:p.stat().st_mtime,reverse=True):
        try:
            report=read(out/'report.json')
            if report.get('status')=='completed_with_estimates' and report.get('source_sha256')==source_hash and report.get('selection_sha256')==expected and (out/'leg-overlay.mp4').is_file():return out/'leg-overlay.mp4'
        except (OSError,ValueError):pass
    return None

def seed_shoes(frame,video):
    p=np.asarray(frame['image_joints'],float);w,h=video['width'],video['height']
    if p.shape!=(70,2) or not np.isfinite(p).all():raise ValueError('초기 발 좌표를 확인할 수 없습니다.')
    if np.linalg.norm(p[13]-p[14])<20:raise ValueError('첫 프레임의 두 발이 겹칩니다. 발이 보이는 영상부터 시작해 주세요.')
    boots=[]
    for obj,(k,a,tips) in enumerate(((11,13,[15,16,17]),(12,14,[18,19,20])),2):
        # Automatic model-derived seed: not a shoe detector or verified identity.
        points=np.vstack((p[[a]+tips],p[a]+.3*(p[k]-p[a])))
        padding=max(8.,h*.012);lo=points.min(0)-padding;hi=points.max(0)+padding
        if not (0<=p[a,0]<w and 0<=p[a,1]<h):raise ValueError('첫 프레임에서 발목이 화면 밖입니다.')
        box=np.clip(np.r_[lo,hi],[0,0,0,0],[w,h,w,h])
        if np.any(box[2:]-box[:2]<8) or (box[2]-box[0])*(box[3]-box[1])>w*h*.15:raise ValueError('초기 발 영역이 불명확합니다.')
        boots.append({'id':obj,'joint':a,'box':box.tolist()})
    return boots

def leg_rois(points,masks,bbox,w,h):
    if not masks:return {}
    ys,xs=np.nonzero(np.logical_or.reduce(masks));p=np.asarray(points);body=p[[5,6,9,10]]
    low=np.minimum(body.min(0),[xs.min(),ys.min()]);high=np.maximum(body.max(0),[xs.max(),ys.max()]);span=np.maximum(high-low,[w*.14,h*.117])
    hip=p[[9,10]];lo=np.minimum(hip.min(0),[xs.min(),ys.min()]);hi=np.maximum(hip.max(0),[xs.max(),ys.max()]);size=np.maximum(hi-lo,[w*.14,h*.117])
    boxes={'body-shoe':[low[0]-.2*span[0],bbox[1]-20,high[0]+.2*span[0],high[1]+20],
           'leg-focus':[lo[0]-.25*size[0],lo[1]-.35*size[1],hi[0]+.25*size[0],hi[1]+20]}
    return {name:np.clip(box,[0,0,0,0],[w,h,w,h]).tolist() for name,box in boxes.items()}

def gpu_child(script,out,progress_file,cancelled,progress):
    from app.sam3d_job import terminate_worker
    python=ROOT/'.validation/sam3d/env/Scripts/python.exe'
    if cancelled():raise KeyboardInterrupt
    with (out/(script+'.log')).open('w',encoding='utf-8') as log:
        process=subprocess.Popen([str(python),'-u',str(ROOT/'app'/script),str(out)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            while process.poll() is None:
                if cancelled():raise KeyboardInterrupt
                try:
                    status=read(out/progress_file);progress(status['done'],status.get('total',status['done']))
                except (OSError,ValueError,KeyError):pass
                time.sleep(.15)
            if process.returncode:raise ValueError(f'부위 재추정 단계 실패: {out / (script+".log")}')
        finally:
            if process.poll() is None:terminate_worker(process)

def combine(raw,selected,boot,records,fresh,cancelled=lambda:False):
    frames=raw['frames'];initial=np.array([r['world_joints'] for r in selected[:26] if r['world_joints'] is not None])
    if not len(initial):raise ValueError('초기 본 길이 자료가 없습니다.')
    lengths={a:np.median(np.stack([np.linalg.norm(initial[:,k]-initial[:,h],axis=-1),np.linalg.norm(initial[:,a]-initial[:,k],axis=-1)],axis=-1),axis=0) for h,k,a in ((9,11,13),(10,12,14))}
    pools=[];unary=[];segments=[];events=[]
    first_segment=(frames[0].get('tracking_segment',0),frames[0].get('scene',{}).get('index',0))
    for i,(r,s) in enumerate(zip(frames,selected)):
        if cancelled():raise KeyboardInterrupt
        if s['world_joints'] is None or r.get('person_bbox') is None:pools.append(None);unary.append(None);segments.append(None);continue
        q=np.asarray(s['world_joints']);p=np.asarray(s['image_joints']);segment=(r.get('tracking_segment',0),r.get('scene',{}).get('index',0))
        # Shoes seeded in scene0 are not evidence after a cut/reidentification.
        masks=regions_at(boot,records,i) if segment==first_segment else []
        options=[{'world_joints':q,'image_joints':p,'variant':'baseline','legs':[],'cost':0.}]
        if shoe_support(masks,p[[13,14]])['disagrees']:
            for name,c in fresh.get(i,{}).items():
                try:proposals,failures=propose(q,p,c['world_joints'],c['image_joints'],masks,lengths,raw['video']['width'],raw['video']['height'])
                except ValueError as error:proposals=[];failures=[{'reason':str(error)}]
                events.append({'frame':i,'variant':name,'feasible':len(proposals),'failures':failures})
                for proposal in proposals:proposal['variant']=name;options.append(proposal)
        pools.append(options);segments.append(segment)
        unary.append([1.2*shoe_support(masks,o['image_joints'][[13,14]])['disagrees']+.08*o['cost']+.03*(o['variant']!='baseline') for o in options])
    path=[0]*len(frames);start=0
    while start<len(frames):
        if pools[start] is None:start+=1;continue
        end=start+1
        while end<len(frames) and pools[end] is not None and segments[end]==segments[start]:end+=1
        try:path[start:end]=select_path([[local_legs(o['world_joints']) for o in pool] for pool in pools[start:end]],unary[start:end])
        except ValueError:events.append({'frame':start,'reason':'degenerate_body_reference; baseline preserved'})
        start=end
    output=[];changed=[];before=after=0
    for i,s in enumerate(selected):
        if pools[i] is None:output.append(dict(s,variant='unavailable',legs=[]));continue
        o=pools[i][path[i]];masks=regions_at(boot,records,i) if segments[i]==first_segment else []
        b=shoe_support(masks,np.asarray(s['image_joints'])[[13,14]]);a=shoe_support(masks,o['image_joints'][[13,14]])
        before+=b['disagrees'];after+=a['disagrees']
        fixed=[j for j in range(70) if j not in range(11,21)]
        np.testing.assert_array_equal(o['world_joints'][fixed],np.asarray(s['world_joints'])[fixed])
        if o['variant']!='baseline':changed.append(i)
        output.append({'frame_index':i,'world_joints':o['world_joints'].tolist(),'image_joints':o['image_joints'].tolist(),'variant':o['variant'],'legs':o['legs'],'before_evidence':b,'after_evidence':a})
    return output,{'changed_frames':changed,'shoe_disagreement_before':before,'shoe_disagreement_after':after,'events':events}

def run_leg_reestimation(folder,source,selection,cancelled=lambda:False,progress=lambda *a:None,phase=lambda *a:None):
    if cancelled():raise KeyboardInterrupt
    raw,source_hash,provenance=load_context(folder,source);folder=Path(folder)
    if selection is None:raise ValueError('먼저 후보 자동 선택을 실행해 주세요.')
    data=read(Path(selection)/'selected-joints.json');selection_report=read(Path(selection)/'report.json')
    if data.get('schema')!='candidate_joint_selection_not_mhr_animation' or selection_report.get('status')!='completed_with_estimates' or data.get('source_sha256')!=source_hash or data.get('raw_sha256')!=digest(folder/'sam3d.json'):
        raise ValueError('후보 선택 결과가 현재 원본과 다릅니다.')
    selected=data['frames'];n=len(raw['frames']);video=raw['video']
    selection_hash=digest(Path(selection)/'selected-joints.json')
    if len(selected)!=n or any(r['frame_index']!=i for i,r in enumerate(selected)):raise ValueError('후보 프레임이 맞지 않습니다.')
    if selected[0]['world_joints'] is None or raw['frames'][0].get('person_bbox') is None:raise ValueError('첫 프레임에서 대상의 발이 보여야 합니다.')
    boots=seed_shoes(selected[0],video)
    out=folder/('leg_reestimate_'+uuid4().hex[:8]);out.mkdir(exist_ok=False);shoe=out/'shoes';shoe.mkdir();infer=out/'inference';infer.mkdir()
    status='failed';rows=[];details={};writer=cap=None;written=0;inferred=0
    try:
        write(shoe/'sam2-request.json',{'source':str(source),'initial_box':raw['frames'][0]['person_bbox'],'target_index':0,'video':dict(video,frame_count=n),'boots':boots})
        phase('신발 영역 새 추적');gpu_child('shoe_worker.py',shoe,'sam2-progress.json',cancelled,progress)
        records=read(shoe/'boot-records.json')
        if len(records)!=n:raise ValueError('신발 추적 프레임 수가 맞지 않습니다.')
        first=(raw['frames'][0].get('tracking_segment',0),raw['frames'][0].get('scene',{}).get('index',0));rois={}
        for i,(r,s) in enumerate(zip(raw['frames'],selected)):
            if cancelled():raise KeyboardInterrupt
            if (r.get('tracking_segment',0),r.get('scene',{}).get('index',0))!=first or s['image_joints'] is None or r.get('person_bbox') is None:continue
            boxes=leg_rois(s['image_joints'],regions_at(shoe,records,i),r['person_bbox'],video['width'],video['height'])
            if boxes:rois[str(i)]=boxes
        if not rois:raise ValueError('추정에 사용할 신발 관측이 없습니다. shoes/boots-preview.mp4를 확인하세요.')
        write(infer/'request.json',{'source':str(source),'start':0,'end_exclusive':n,'frames':raw['frames'],'leg_rois':rois})
        phase('하체 후보 새 추론');gpu_child('leg_candidate_worker.py',infer,'progress.json',cancelled,progress)
        fresh_data=read(infer/'candidates.json')
        if fresh_data['joint_names']!=raw['joint_names'] or [r['frame_index'] for r in fresh_data['frames']]!=[int(k) for k in rois]:raise ValueError('하체 추론 프레임/관절 이름이 다릅니다.')
        if digest(source)!=source_hash or digest(Path(selection)/'selected-joints.json')!=selection_hash or digest(folder/'sam3d.json')!=data['raw_sha256']:
            raise ValueError('처리 중 원본 또는 입력 추정 결과가 변경되었습니다.')
        fresh={r['frame_index']:r['candidates'] for r in fresh_data['frames']}
        inferred=len(fresh)*2
        phase('다리 결합·비교 영상 저장');rows,details=combine(raw,selected,shoe,records,fresh,cancelled)
        cap=cv2.VideoCapture(str(source));writer=cv2.VideoWriter(str(out/'leg-overlay.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),video['fps'],(video['width']*2,video['height']))
        if not cap.isOpened() or not writer.isOpened():raise ValueError('다리 비교 영상을 열 수 없습니다.')
        for i,(baseline,result) in enumerate(zip(selected,rows)):
            if cancelled():raise KeyboardInterrupt
            ok,image=cap.read()
            if not ok or image.shape[:2]!=(video['height'],video['width']):raise ValueError('원본 영상 프레임 불일치입니다.')
            pair=[];modified=[] if result['world_joints'] is None else np.flatnonzero(np.any(np.asarray(result['world_joints'])!=np.asarray(baseline['world_joints']),axis=1))
            for side,r in enumerate((baseline,result)):
                frame=image.copy()
                if r['image_joints'] is not None:
                    p=np.asarray(r['image_joints'])
                    for a,b in CONNECTIONS:
                        color=(0,160,255) if side and (a in modified or b in modified) else (30,230,70)
                        cv2.line(frame,tuple(np.clip(p[a],-10000,10000).astype(int)),tuple(np.clip(p[b],-10000,10000).astype(int)),color,2)
                cv2.putText(frame,f'{i} '+('SELECTED BASELINE' if not side else 'FRESH LEG / '+r['variant']),(12,30),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),2);pair.append(frame)
            writer.write(np.concatenate(pair,axis=1));written+=1;progress(i+1,n)
        write(out/'leg-joints.json',{'schema':'leg_reestimation_joint_hypotheses_not_animation','video':video,'source_sha256':source_hash,'frames':rows})
        status='completed_with_estimates'
    except KeyboardInterrupt:status='cancelled';raise
    finally:
        if cap is not None:cap.release()
        if writer is not None:writer.release()
        report={'status':status,'frames_processed':len(rows),'frames_written':written,'fresh_model_poses':inferred,'source_sha256':source_hash,'extraction_source_hash_verified':provenance,'selection':str(selection),
                'selection_sha256':selection_hash,
                'automatic_shoe_seeds':boots,'shoe_seed_identity_verified':False,**details,
                'limits':['automatic_model_foot_seeds_can_be_wrong','shoe_masks_not_identity_ground_truth','unreachable_fixed_hip_constraints_remain','hidden_legs_not_observed','joint_only_no_MHR_rotations','isolated_corrections_can_jump']}
        write(out/'report.json',report)
    return out,report
