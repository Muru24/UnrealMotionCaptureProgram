"""Fresh context crops for requested limbs; frozen person and body attachments."""
from pathlib import Path
from uuid import uuid4
from collections import OrderedDict
import hashlib,json,cv2,numpy as np
from app.knee_job import load_context,digest
from app.completion_job import read
from app.fullbody_job import write
from app.joint_review_job import mask_evidence
from app.leg_reestimate_job import gpu_child
from core.pose3d.part_reestimation import make_plan,combine,PARTS,editable_joints
from core.pose3d.sam_completion import CONNECTIONS

def signatures(folder,source_hash,selection,review):
    return {'source_sha256':source_hash,'raw_sha256':digest(Path(folder)/'sam3d.json'),
        'selection_sha256':digest(Path(selection)/'selected-joints.json'),
        'review_sha256':digest(review),'fullbody_sha256':digest(Path(selection)/'fullbody-candidates.json'),'part_revision':1}

def latest_part_result(folder,source_hash,selection,review):
    expected=signatures(folder,source_hash,selection,review)
    for out in sorted(Path(folder).glob('parts_*'),key=lambda p:p.stat().st_mtime,reverse=True):
        try:
            report=read(out/'report.json')
            if report.get('status')=='completed_with_estimates' and all(report.get(k)==v for k,v in expected.items()) and all((out/name).is_file() for name in ('part-joints.json','part-overlay.mp4')):return out
        except (OSError,ValueError):pass
    return None

def mask_support(folder,packet,review,cancelled):
    evidence,manifest,tracking_hash=mask_evidence(folder,packet,cancelled)
    actual=hashlib.sha256(json.dumps(manifest).encode('utf-8')).hexdigest()
    if actual!=review['mask_manifest_sha256'] or tracking_hash!=review['tracking_sha256']:raise ValueError('Part mask evidence changed; run joint review again.')
    plan=read(folder/'sam-tracking.json') if tracking_hash else {'frames':[]};cache=OrderedDict()
    def support(i,points):
        if evidence.get(i,{}).get('status')!='available':return 0.
        if i not in cache:
            path=folder/plan['frames'][i]['mask']['file']
            image=cv2.imdecode(np.frombuffer(path.read_bytes(),np.uint8),cv2.IMREAD_GRAYSCALE)
            cache[i]=cv2.distanceTransform((image==0).astype(np.uint8),cv2.DIST_L2,3)
            while len(cache)>8:cache.popitem(last=False)
        distance=cache[i];h,w=distance.shape;values=[]
        for x,y in points:
            values.append(min(4.,float(distance[min(h-1,round(y)),min(w-1,round(x))])/evidence[i]['tolerance_pixels']) if 0<=x<w and 0<=y<h else 4.)
        return float(np.mean(values))
    return support,manifest

def render(source,path,packet,rows,cancelled,progress,titles=('SELECTED BASELINE','SELECTIVE PART ESTIMATES')):
    video=packet['video'];cap=cv2.VideoCapture(str(source));writer=None
    try:
        writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),video['fps'],(video['width']*2,video['height']))
        if not cap.isOpened() or not writer.isOpened():raise ValueError('Cannot open part comparison video.')
        for frame,row in zip(packet['frames'],rows):
            if cancelled():raise KeyboardInterrupt
            ok,image=cap.read()
            if not ok:raise ValueError('Part comparison video timeline differs.')
            before=frame['candidates'].get(frame['selected_candidate']);views=[]
            changed={j for c in row['changed_parts'] for j in editable_joints(c['part'])}
            if row.get('body_reference_hypothesis'):changed.update((5,6,9,10,67,68,69))
            for points,title,is_after in ((None if before is None else before['image_joints'],titles[0],False),(row['image_joints'],titles[1],True)):
                view=image.copy()
                if points is not None:
                    p=np.asarray(points)
                    for a,b in CONNECTIONS:
                        color=(0,160,255) if is_after and (a in changed or b in changed) else (210,170,70)
                        u,v=[tuple(np.clip(p[j],-10000,10000).round().astype(int)) for j in (a,b)]
                        visible,u,v=cv2.clipLine((0,0,video['width'],video['height']),u,v)
                        if visible:cv2.line(view,u,v,color,2,cv2.LINE_AA)
                cv2.putText(view,title,(12,28),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,180,255),1);views.append(view)
            writer.write(np.hstack(views));progress(row['frame_index']+1,len(rows))
    finally:
        cap.release()
        if writer is not None:writer.release()

def run_part_reestimation(folder,source,selection,review_path,cancelled=lambda:False,progress=lambda *a:None,phase=lambda *a:None):
    if cancelled():raise KeyboardInterrupt
    folder=Path(folder).resolve();selection=Path(selection);raw,source_hash,_=load_context(folder,source)
    packet=read(selection/'fullbody-candidates.json');review=read(review_path)
    expected=signatures(folder,source_hash,selection,review_path)
    if packet.get('source_sha256')!=source_hash or packet.get('raw_sha256')!=expected['raw_sha256'] or packet.get('selection_sha256')!=expected['selection_sha256'] or review.get('fullbody_sha256')!=expected['fullbody_sha256'] or review.get('source_sha256')!=source_hash or review.get('schema')!='joint_review_mhr70_v1':
        raise ValueError('Part source/full-body/review provenance differs.')
    if len(packet['frames'])!=len(raw['frames']):raise ValueError('Part full-body timeline differs.')
    plan=make_plan(packet,review,cancelled);support,manifest=mask_support(folder,packet,review,cancelled)
    out=folder/('parts_'+uuid4().hex[:8]);out.mkdir();infer=out/'inference';infer.mkdir();status='failed';details={}
    try:
        write(out/'plan.json',plan)
        fresh={}
        if plan['rois']:
            write(infer/'request.json',{'source':str(source),'start':0,'end_exclusive':len(raw['frames']),'frames':raw['frames'],'leg_rois':plan['rois']})
            phase(f"팔·다리 문맥 후보 추론 · {plan['inference_count']}회")
            gpu_child('leg_candidate_worker.py',infer,'progress.json',cancelled,progress)
            data=read(infer/'candidates.json')
            if data['joint_names']!=raw.get('joint_names') or [r['frame_index'] for r in data['frames']]!=[int(i) for i in plan['rois']]:raise ValueError('Part inference timeline/joints differ.')
            fresh={r['frame_index']:r['candidates'] for r in data['frames']}
            if any(set(fresh[int(i)])!=set(boxes) for i,boxes in plan['rois'].items()):raise ValueError('Incomplete part inference variants.')
        if cancelled():raise KeyboardInterrupt
        phase('부위별 몸통 고정·주변 프레임 경로 비교')
        rows,details=combine(packet,review,plan,fresh,support,cancelled)
        if signatures(folder,digest(source),selection,review_path)!=expected or any(h is not None and digest(Path(p))!=h for p,h in manifest):raise ValueError('Part inputs changed during inference.')
        render(source,out/'part-overlay.partial.mp4',packet,rows,cancelled,progress)
        if cancelled():raise KeyboardInterrupt
        if signatures(folder,digest(source),selection,review_path)!=expected:raise ValueError('Part inputs changed during preview.')
        (out/'part-overlay.partial.mp4').replace(out/'part-overlay.mp4')
        write(out/'part-joints.json',{'schema':'part_reestimated_mhr70_joints_v1',**expected,'video':raw['video'],
            'frames':rows,'details':details,'coordinates':packet['coordinates'],'inference_count':plan['inference_count']})
        status='completed_with_estimates'
    except KeyboardInterrupt:status='cancelled';raise
    finally:
        (out/'part-overlay.partial.mp4').unlink(missing_ok=True)
        report={'status':status,**expected,'inference_count':plan['inference_count'],
            'changed_frames':details.get('changed_frames',[]),'changed_part_frames':details.get('changed_part_frames',0),
            'frames_processed':len(packet['frames']),'no_native_rotations_replaced':True}
        write(out/'report.json',report)
    return out,report
