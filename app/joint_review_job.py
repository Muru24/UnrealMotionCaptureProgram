"""Read-only joint inspection and segment-bounded repair requests."""
from pathlib import Path
import hashlib,json,cv2,numpy as np
from app.knee_job import digest
from app.completion_job import read
from app.fullbody_job import write
from core.pose3d.joint_review import review_joints
from core.pose3d.sam_completion import CONNECTIONS

def mask_evidence(folder,packet,cancelled):
    folder=Path(folder).resolve();tracking=folder/'sam-tracking.json';evidence={};manifest=[]
    if not tracking.is_file():return evidence,manifest,None
    tracking_hash=digest(tracking);plan=read(tracking);frames=plan['frames']
    if len(frames)!=len(packet['frames']) or any(r['frame_index']!=i for i,r in enumerate(frames)):
        raise ValueError('Joint mask evidence timeline differs.')
    width,height=packet['video']['width'],packet['video']['height']
    for i,(track,row) in enumerate(zip(frames,packet['frames'])):
        if cancelled():raise KeyboardInterrupt
        pose=row['candidates'].get(row['selected_candidate']);evidence[i]={'status':'unknown'}
        if pose is None or track.get('tracking',{}).get('state')!='tracked' or track.get('tracking',{}).get('track_id')!=row['target_id']:continue
        name=track.get('mask',{}).get('file')
        if not name:continue
        path=folder/name
        if Path(name).is_absolute() or not path.resolve().is_relative_to(folder) or path.is_symlink():
            evidence[i]={'status':'invalid_mask_path'};continue
        try:
            data=path.read_bytes();file_hash=hashlib.sha256(data).hexdigest()
            manifest.append((str(path),file_hash));mask=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_GRAYSCALE)
        except OSError:evidence[i]={'status':'missing_mask'};manifest.append((str(path),None));continue
        if mask is None or mask.shape!=(height,width):evidence[i]={'status':'invalid_mask_dimensions'};continue
        area=np.count_nonzero(mask)
        if not 0<area<width*height*.85:evidence[i]={'status':'uninformative_mask'};continue
        distance=cv2.distanceTransform((mask==0).astype(np.uint8),cv2.DIST_L2,3)
        values=[]
        for point in pose['image_joints']:
            x,y=map(float,point)
            values.append(float(distance[min(height-1,round(y)),min(width-1,round(x))]) if 0<=x<width and 0<=y<height else None)
        diagonal=float(np.linalg.norm(np.subtract(row['person_bbox'][2:],row['person_bbox'][:2])))
        evidence[i]={'status':'available','distances':values,'tolerance_pixels':max(3.,min(16.,diagonal*.015))}
    return evidence,manifest,tracking_hash

def render_review(source,path,report,cancelled,progress):
    video=report['video'];cap=cv2.VideoCapture(str(source));writer=None
    try:
        writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),video['fps'],(video['width'],video['height']))
        if not cap.isOpened() or not writer.isOpened():raise ValueError('Cannot open joint review preview.')
        for row in report['frames']:
            if cancelled():raise KeyboardInterrupt
            ok,image=cap.read()
            if not ok:raise ValueError('Joint review video timeline differs.')
            joints=row['joints']
            if joints:
                xy=lambda j:tuple(np.clip(joints[j]['image_position'],-10000,10000).round().astype(int))
                for a,b in CONNECTIONS:
                    color=(0,140,255) if joints[a]['reasons'] or joints[b]['reasons'] else (210,170,70)
                    visible,u,v=cv2.clipLine((0,0,video['width'],video['height']),xy(a),xy(b))
                    if visible:cv2.line(image,u,v,color,2,cv2.LINE_AA)
                for j in (5,6,7,8,9,10,11,12,13,14,41,62,69):
                    if joints[j]['reasons']:cv2.circle(image,xy(j),5,(0,80,255),-1)
            text='JOINT REVIEW - NOT CORRECTED | '+(','.join(row['review_parts']) if row['review_parts'] else row['status'])
            cv2.putText(image,text,(12,28),cv2.FONT_HERSHEY_SIMPLEX,.48,(0,180,255),1)
            writer.write(image);progress(row['frame_index']+1,len(report['frames']))
    finally:
        cap.release()
        if writer is not None:writer.release()

def ensure_joint_review(folder,source,packet_path,source_hash,cancelled=lambda:False,progress=lambda *a:None):
    if cancelled():raise KeyboardInterrupt
    folder=Path(folder);packet_path=Path(packet_path);selection=packet_path.parent;path=selection/'joint-review.json'
    if digest(source)!=source_hash:raise ValueError('Joint review source changed.')
    packet=read(packet_path)
    if packet.get('source_sha256')!=source_hash or packet.get('raw_sha256')!=digest(folder/'sam3d.json'):
        raise ValueError('Joint review source/full-body input differs.')
    evidence,manifest,tracking_hash=mask_evidence(folder,packet,cancelled)
    hashes={'source_sha256':source_hash,'fullbody_sha256':digest(packet_path),'tracking_sha256':tracking_hash,
            'mask_manifest_sha256':hashlib.sha256(json.dumps(manifest).encode('utf-8')).hexdigest()}
    try:
        old=read(path)
        if isinstance(old,dict) and old.get('schema')=='joint_review_mhr70_v1' and old.get('review_revision')==2 and all(old.get(k)==v for k,v in hashes.items()) and all((selection/name).is_file() for name in ('joint-review.mp4','joint-repair-requests.json')):return path,'reused'
    except (OSError,ValueError):pass
    report=review_joints(packet,evidence,cancelled);report.update(hashes)
    report['summary']['mask_available_frames']=sum(e.get('status')=='available' for e in evidence.values())
    temporary=selection/'joint-review.partial.mp4'
    try:
        render_review(source,temporary,report,cancelled,progress)
        if cancelled():raise KeyboardInterrupt
        if digest(source)!=source_hash or digest(packet_path)!=hashes['fullbody_sha256'] or (tracking_hash and digest(folder/'sam-tracking.json')!=tracking_hash) or any(h is not None and digest(Path(p))!=h for p,h in manifest):
            raise ValueError('Joint review inputs changed during export.')
    except BaseException:
        temporary.unlink(missing_ok=True);raise
    temporary.replace(selection/'joint-review.mp4')
    write(selection/'joint-repair-requests.json',{'schema':'joint_repair_requests_v1','input_stage':report['input_stage'],
        **hashes,'requests':report['repair_requests'],'limits':['review_requests_not_confirmed_joint_errors','no_reestimation_executed_by_review_stage']})
    write(path,report)
    return path,'computed'
