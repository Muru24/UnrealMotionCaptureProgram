"""Manual knee/ankle constraints on existing SAM joints; raw MHR stays intact."""
from pathlib import Path
from uuid import uuid4
import hashlib,json,cv2,numpy as np
from app.completion_job import read,local,render
from core.pose3d.guidance import validate_anchors
from core.pose3d.manual_leg_geometry import fit_camera,project,solve_leg
from core.pose3d.manual_leg_path import local_legs,select_path
from core.pose3d.sam_completion import CONNECTIONS

NAMES={11:'left_knee',12:'right_knee',13:'left_ankle',14:'right_ankle'}

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def load_context(folder,source):
    folder=local(folder);source=local(source).resolve()
    request=read(folder/'sam-request.json');raw=read(folder/'sam3d.json');report=read(folder/'report.json')
    if report.get('status') not in ('completed','completed_with_warnings') or raw.get('schema')!='sam3d_mhr70':raise ValueError('완료된 SAM3D 결과를 선택하세요.')
    if Path(request['source']).resolve()!=source:raise ValueError('선택한 원본과 SAM 결과의 원본 경로가 다릅니다.')
    if len(raw['frames'])!=report.get('frames_processed') or any(r['frame_index']!=i for i,r in enumerate(raw['frames'])):raise ValueError('불완전한 SAM 프레임입니다.')
    current=digest(source)
    if request.get('source_sha256') and current!=request['source_sha256']:raise ValueError('추출 이후 원본 영상이 변경되었습니다.')
    return raw,current,bool(request.get('source_sha256'))

def target_at(anchors,index,name,segments):
    if name in anchors.get(index,{}):return np.array(anchors[index][name]),'manual'
    keys=sorted(i for i,p in anchors.items() if name in p)
    for a,b in zip(keys[:-1],keys[1:]):
        if a<index<b and b-a<=16 and all(s is not None and s==segments[a] for s in segments[a:b+1]):
            t=(index-a)/(b-a);return (1-t)*np.array(anchors[a][name])+t*np.array(anchors[b][name]),'interpolated'
    return None,'unknown'

def run_knee_correction(folder,source,anchors,cancelled=lambda:False,progress=lambda *a:None,*,selection=None):
    raw,source_hash,provenance=load_context(folder,source);video=raw['video'];frames=raw['frames'];n=len(frames)
    if selection is not None:
        from copy import deepcopy
        selected=read(Path(selection)/'selected-joints.json');selected_report=read(Path(selection)/'report.json')
        if selected_report.get('status')!='completed_with_estimates' or selected.get('schema')!='candidate_joint_selection_not_mhr_animation' or selected.get('source_sha256')!=source_hash or selected.get('raw_sha256')!=digest(Path(folder)/'sam3d.json') or len(selected['frames'])!=n:
            raise ValueError('후보 결과의 원본/프레임이 다릅니다.')
        raw=deepcopy(raw);frames=raw['frames']
        for i,(r,s) in enumerate(zip(frames,selected['frames'])):
            if s['frame_index']!=i:raise ValueError('후보 프레임 순서가 다릅니다.')
            if r.get('outputs') is not None:
                r['outputs']={'pred_keypoints_3d':s['world_joints'],'pred_keypoints_2d':s['image_joints']}
    anchors=validate_anchors(anchors,video['width'],video['height'],n)
    if not any(any(k in NAMES.values() for k in p) for p in anchors.values()):raise ValueError('무릎 또는 발목을 지정하세요.')
    if any(k not in NAMES.values() for p in anchors.values() for k in p):raise ValueError('이 보정은 무릎·발목만 지원합니다.')
    segments=[None if not r.get('outputs') or r.get('person_bbox') is None else (r.get('tracking_segment',0),r.get('scene',{}).get('index',0)) for r in frames]
    sizes={}
    for h,k,a in ((9,11,13),(10,12,14)):
        samples=[]
        for r in frames[:26]:
            if r.get('outputs'):
                q=np.array(r['outputs']['pred_keypoints_3d']);samples.append([np.linalg.norm(q[k]-q[h]),np.linalg.norm(q[a]-q[k])])
        if not samples:raise ValueError('초기 구간에 본 길이 참조가 없습니다.')
        sizes[a]=np.median(samples,axis=0)
    pools=[];unaries=[];cameras=[];issues=[]
    for i,r in enumerate(frames):
        if cancelled():raise KeyboardInterrupt
        if segments[i] is None:pools.append(None);unaries.append(None);cameras.append(None);continue
        q=np.array(r['outputs']['pred_keypoints_3d']);p=np.array(r['outputs']['pred_keypoints_2d'])
        try:cam=fit_camera(q,p,video['width'],video['height']);local_legs(q)
        except ValueError as e:
            pools.append(None);unaries.append(None);cameras.append(None);issues.append({'frame':i,'reason':str(e)});continue
        cameras.append(cam);options=[q.copy()];hyp=q.copy();changed=False
        for h,k,a in ((9,11,13),(10,12,14)):
            kt,kind=target_at(anchors,i,NAMES[k],segments);at,akind=target_at(anchors,i,NAMES[a],segments)
            if kt is None and at is None:continue
            # No shoe detector here: absent ankle input retains model ankle projection.
            target=p[a] if at is None else at
            fit=solve_leg(q[h],q[k],q[a],target,cam,*sizes[a],q[k],q[a],knee_target=kt)
            if fit is None or (kt is not None and fit['knee_error_pixels']>20):
                issues.append({'frame':i,'joint':k,'reason':'no_feasible_joint_constraints'});continue
            hyp[k]=fit['knee'];hyp[a]=fit['ankle'];tips=[15,16,17] if a==13 else [18,19,20]
            hyp[tips]+=hyp[a]-q[a];changed=True
        if changed:options.append(hyp)
        scores=[]
        for candidate in options:
            xy=project(candidate,cam);cost=0.
            for joint,name in NAMES.items():
                target,kind=target_at(anchors,i,name,segments)
                if target is not None:cost+=(2 if kind=='manual' else .5)*min(20.,float(np.linalg.norm(xy[joint]-target))/10.)
            scores.append(cost+.03*bool(np.any(candidate!=q)))
        pools.append(options);unaries.append(scores)
        progress(i+1,n*2)
    chosen=[0]*n;start=0
    while start<n:
        if pools[start] is None:start+=1;continue
        end=start+1
        while end<n and pools[end] is not None and segments[end]==segments[start]:end+=1
        path=select_path([[local_legs(q) for q in pool] for pool in pools[start:end]],unaries[start:end]);chosen[start:end]=path;start=end
    out=Path(folder)/('knee_'+uuid4().hex[:8]);out.mkdir(exist_ok=False)
    cap=cv2.VideoCapture(str(source));overlay=native=None;status='failed';rows=[];report_anchors=[]
    try:
        overlay=cv2.VideoWriter(str(out/'knee-overlay.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),video['fps'],(video['width']*2,video['height']))
        native=cv2.VideoWriter(str(out/'knee3d.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),video['fps'],(1280,720))
        if not cap.isOpened() or not overlay.isOpened() or not native.isOpened():raise ValueError('보정 미리보기를 열 수 없습니다.')
        for i,r in enumerate(frames):
            if cancelled():raise KeyboardInterrupt
            ok,image=cap.read()
            if not ok or image.shape[:2]!=(video['height'],video['width']):raise ValueError('원본 프레임/해상도 불일치입니다.')
            row={'frame_index':i,'modified_joints':[],'world_joints':None,'image_joints':None};left=image.copy();right=image.copy()
            if r.get('outputs'):
                old=np.array(r['outputs']['pred_keypoints_3d']);p=np.array(r['outputs']['pred_keypoints_2d']);q=old if pools[i] is None else pools[i][chosen[i]]
                modified=np.flatnonzero(np.any(q!=old,axis=1));xy=p.copy()
                if len(modified):xy[modified]=project(q[modified],cameras[i])
                np.testing.assert_array_equal(old[[j for j in range(70) if j not in range(11,21)]],q[[j for j in range(70) if j not in range(11,21)]])
                row.update(world_joints=q.tolist(),image_joints=xy.tolist(),modified_joints=modified.tolist())
                for img,points in ((left,p),(right,xy)):
                    for a,b in CONNECTIONS:
                        color=(0,160,255) if img is right and (a in modified or b in modified) else (50,230,100)
                        cv2.line(img,tuple(np.clip(points[a],-10000,10000).astype(int)),tuple(np.clip(points[b],-10000,10000).astype(int)),color,2)
                hip=(old[9]+old[10])/2;extent=max(np.abs(old-hip).max(),np.abs(q-hip).max(),.1);scale=min(350,125/extent)
                native.write(render({'frame_index':i,'person_bbox':r.get('person_bbox'),'landmarks':[dict(zip(('x','y','z'),v),valid=True) for v in old-hip]},
                    {'joints':[{'xyz':v.tolist(),'source':'manual_inferred' if j in modified else 'observed'} for j,v in enumerate(q-hip)]},CONNECTIONS,scale))
            else:native.write(np.zeros((720,1280,3),np.uint8))
            for joint,name in NAMES.items():
                target,kind=target_at(anchors,i,name,segments)
                if target is not None:
                    cv2.drawMarker(right,tuple(np.round(target).astype(int)),(255,0,255) if kind=='manual' else (255,220,0),cv2.MARKER_CROSS,22,2)
                    if kind=='manual':
                        error=None if row['image_joints'] is None else float(np.linalg.norm(np.array(row['image_joints'][joint])-target))
                        report_anchors.append({'frame':i,'joint':name,'error_pixels':error,'status':'unresolved' if error is None or error>20 else ('fitted_hypothesis' if joint in row['modified_joints'] else 'baseline_already_near')})
            cv2.putText(left,'RAW SAM' if selection is None else 'CANDIDATE BASELINE',(12,30),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),2)
            cv2.putText(right,'MANUAL LEG HYPOTHESIS | depth unverified',(12,30),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,200,255),1)
            overlay.write(np.concatenate((left,right),axis=1));rows.append(row);progress(n+i+1,n*2)
        (out/'knee-joints.json').write_text(json.dumps({'schema':'manual_leg_joint_hypotheses_not_animation','video':video,'frames':rows},allow_nan=False),encoding='utf-8')
        status='completed_with_estimates'
    except KeyboardInterrupt:status='cancelled';raise
    finally:
        cap.release()
        for writer in (overlay,native):
            if writer is not None:writer.release()
        info={'status':status,'frames_written':len(rows),'source_sha256':source_hash,'extraction_source_hash_verified':provenance,
              'candidate_selection_input':None if selection is None else str(selection),
              'anchors':anchors,'anchor_results':report_anchors,'issues':issues,'raw_preserved':True,
              'limits':['joint_only_no_MHR_rotation_conversion','no_shoe_mask_observation_in_this_path','unanchored_ankle_uses_raw_model_projection','depth_and_foot_rotation_unverified','legacy_extractions_without_source_hash_not_cryptographically_verified']}
        (out/'report.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    return out,info
