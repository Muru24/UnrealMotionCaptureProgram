"""Stage 1: prompted accessory masks and overlap review, never pose removal."""
from pathlib import Path
from uuid import uuid4
import argparse,copy,json
import cv2,numpy as np
from app.knee_job import load_context,digest
from app.completion_job import read
from app.fullbody_job import write
from app.leg_reestimate_job import gpu_child
from core.pose2d.internal_mask import validate_prompts,assess_region,joint_region_evidence
from core.pose3d.sam_completion import CONNECTIONS


def local_file(root,name):
    root=Path(root).resolve();path=(root/name).resolve()
    if not path.is_relative_to(root) or not path.is_file():raise ValueError('Invalid mask path.')
    return path


def load_mask(path,width,height):
    a=cv2.imdecode(np.frombuffer(Path(path).read_bytes(),np.uint8),cv2.IMREAD_GRAYSCALE)
    if a is None or a.shape!=(height,width):raise ValueError('Mask dimensions differ.')
    return a>0


def run_internal_masks(folder,source,config,cancelled=lambda:False,progress=lambda *a:None):
    folder=Path(folder).resolve();raw,source_hash,_=load_context(folder,source)
    video=raw['video'];w=video['width'];h=video['height']
    validate_prompts(config['objects'],w,h)
    start=config['start'];stop=config['end_exclusive'];seed=config['seed_frame']
    if not all(type(v) is int for v in (start,stop,seed)) or not 0<=start<=seed<stop<=len(raw['frames']) or stop-start>180:raise ValueError('Invalid mask interval.')
    tracking_path=folder/'sam-tracking.json';tracking=read(tracking_path);manifest=[];parents={};keys=[]
    for i in range(start,stop):
        if cancelled():raise KeyboardInterrupt
        row=tracking['frames'][i]
        if row['frame_index']!=i or row.get('roi') is None or row['tracking']['state']!='tracked':raise ValueError('Internal mask interval includes unobserved person.')
        if row['tracking'].get('track_id') is None:raise ValueError('Internal mask person identity unavailable.')
        keys.append((row['tracking']['track_id'],row.get('tracking_segment'),row.get('scene',{}).get('index'),raw['frames'][i].get('tracking_segment')))
        path=local_file(folder,row['mask']['file']);parents[i]=path;manifest.append((str(path),digest(path)))
    if len(set(keys))!=1:raise ValueError('Internal mask interval crosses person/scene boundary.')
    person=load_mask(parents[seed],w,h)
    for obj in config['objects']:
        for (x,y),label in zip(obj['points'],obj['labels']):
            if label and not person[min(h-1,round(y)),min(w-1,round(x))]:raise ValueError('Positive prompt is outside tracked person.')
    expected={'source_sha256':source_hash,'raw_sha256':digest(folder/'sam3d.json'),'tracking_sha256':digest(tracking_path)}
    out=folder/('internal_'+uuid4().hex[:8]);out.mkdir();status='failed';records=[];writer=None;cap=None
    try:
        request={**copy.deepcopy(config),'source':str(Path(source).resolve()),'video':video,
            'seed_origin':'operator_visual_experiment_not_automatic_semantic_detection',**expected}
        write(out/'request.json',request)
        gpu_child('internal_mask_worker.py',out,'progress.json',cancelled,progress)
        data=read(out/'regions.json')
        if [r['frame_index'] for r in data['frames']]!=list(range(start,stop)):raise ValueError('Internal mask timeline differs.')
        cap=cv2.VideoCapture(str(source));writer=cv2.VideoWriter(str(out/'internal-mask-overlay.partial.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),video['fps'],(w*2,h))
        if not cap.isOpened() or not writer.isOpened():raise ValueError('Cannot open internal mask preview.')
        for _ in range(start):
            if not cap.read()[0]:raise ValueError('Preview source differs.')
        previous={};colors=[(210,70,230),(20,210,245),(255,180,30),(100,230,80)]
        for r in data['frames']:
            if cancelled():raise KeyboardInterrupt
            i=r['frame_index'];ok,image=cap.read()
            if not ok:raise ValueError('Preview source differs.')
            person=load_mask(parents[i],w,h);regions={};review={};view=image.copy();names=[o['name'] for o in config['objects']]
            if set(r['objects'])!=set(names):raise ValueError('Internal region names differ.')
            union=np.zeros((h,w),np.uint8)
            for k,name in enumerate(names):
                obj=r['objects'][name];mask=load_mask(local_file(out,obj['file']),w,h)
                inside,info=assess_region(mask,person,obj['object_logit'],previous.get(name));previous[name]=inside
                p=Path('clipped')/name/f'{i:06d}.png';(out/p).parent.mkdir(parents=True,exist_ok=True)
                (out/p).write_bytes(cv2.imencode('.png',inside.astype(np.uint8)*255)[1].tobytes());info['file']=p.as_posix()
                regions[name]=(inside,info);review[name]=info;union+=inside.astype(np.uint8)
                color=np.empty_like(view);color[:]=colors[k];view[inside]=cv2.addWeighted(view,.55,color,.45,0)[inside]
                cv2.putText(view,f'{name}: {info["status"]}',(10,55+k*24),cv2.FONT_HERSHEY_SIMPLEX,.5,colors[k],1)
            points=raw['frames'][i].get('outputs',{}).get('pred_keypoints_2d')
            hits=joint_region_evidence(points,regions) if points is not None else []
            if points is not None:
                points=np.asarray(points);flagged={e['joint_index'] for e in hits}
                for a,b in CONNECTIONS:
                    u,v=[tuple(np.clip(points[j],-10000,10000).round().astype(int)) for j in (a,b)]
                    visible,u,v=cv2.clipLine((0,0,w,h),u,v)
                    if visible:cv2.line(view,u,v,(0,140,255) if a in flagged or b in flagged else (60,230,80),2)
            cv2.putText(view,f'{i} PROMPTED REGIONS / REVIEW ONLY',(10,28),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
            writer.write(np.hstack((image,view)));records.append({'frame_index':i,'timestamp':i/video['fps'],'regions':review,
                'overlapping_region_pixels':int((union>1).sum()),'joint_overlap_review':hits,'pose_modified':False})
            progress(i-start+1,stop-start)
        writer.release();writer=None;cap.release();cap=None
        if cancelled():raise KeyboardInterrupt
        if digest(source)!=source_hash or digest(folder/'sam3d.json')!=expected['raw_sha256'] or digest(tracking_path)!=expected['tracking_sha256'] or any(digest(p)!=sha for p,sha in manifest):raise ValueError('Internal mask inputs changed.')
        write(out/'internal-mask-review.json',{'schema':'prompted_internal_mask_review_v1',**expected,'person_mask_manifest':manifest,
            'start':start,'end_exclusive':stop,'seed_frame':seed,'frames':records,'diagnostic_only':True,
            'limits':['manually_seeded_regions_not_automatic_semantics','overlap_can_mean_occlusion_not_joint_error',
                      'SAM2_can_leak_to_skin_or_other_clothing','no_pose_candidates_removed_or_modified']})
        (out/'internal-mask-overlay.partial.mp4').replace(out/'internal-mask-overlay.mp4');status='completed_diagnostic'
    except KeyboardInterrupt:status='cancelled';raise
    finally:
        if cap is not None:cap.release()
        if writer is not None:writer.release()
        (out/'internal-mask-overlay.partial.mp4').unlink(missing_ok=True)
        write(out/'report.json',{'status':status,**expected,'frames_processed':len(records),'diagnostic_only':True,'pose_modified':False})
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');p.add_argument('source');p.add_argument('config');a=p.parse_args()
    print(run_internal_masks(a.folder,a.source,read(a.config)))
