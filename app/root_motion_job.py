"""Bounded CPU video analysis for exact-source, background-compensated root evidence."""
from pathlib import Path
import json,math
import cv2,numpy as np
from app.knee_job import digest
from core.motion.root_motion import background_step


def root_observations(motion,data,pixels,cancelled=lambda:False):
    if pixels is None:return None,{'status':'unavailable','reason':'no_exact_pose_packet'}
    folder=Path(motion).parent.parent;raw_path=folder/'sam3d.json';request_path=folder/'sam-request.json'
    if not raw_path.is_file() or not request_path.is_file() or raw_path.is_symlink() or request_path.is_symlink():
        return None,{'status':'unavailable','reason':'missing_source_provenance'}
    if digest(raw_path)!=data.get('raw_sha256'):return None,{'status':'unavailable','reason':'raw_hash_differs'}
    request=json.loads(request_path.read_text(encoding='utf-8'));source=Path(request['source'])
    if not source.is_file() or source.is_symlink():return None,{'status':'unavailable','reason':'source_video_missing'}
    expected=data.get('source_sha256')
    if not expected or digest(source)!=expected:return None,{'status':'unavailable','reason':'source_video_hash_differs'}
    raw=json.loads(raw_path.read_text(encoding='utf-8'));frames=data['frames'];n=len(frames)
    if len(raw['frames'])!=n:raise ValueError('Root source timeline differs.')
    w,h=int(data['video']['width']),int(data['video']['height'])
    if not 0<n<=18000 or not 2<=w<=1920 or not 2<=h<=1920:raise ValueError('Invalid root analysis bounds.')
    ratio=min(1.,480/max(w,h))
    size=(max(2,round(w*ratio)),max(2,round(h*ratio)));sx=size[0]/w;sy=size[1]/h
    scaled=np.diag([sx,sy,1.]);focal=math.hypot(w,h)
    pelvis=np.full((n,3),np.nan);feet_z=np.full((n,4),np.nan);feet_x=np.full((n,4),np.nan);epochs=np.full(n,-1,int)
    cap=cv2.VideoCapture();previous=None;previous_box=None;last=None;cumulative=np.eye(3);epoch=-1;rejected=0
    if not cap.open(str(source),cv2.CAP_FFMPEG,[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,5000,cv2.CAP_PROP_READ_TIMEOUT_MSEC,5000]):
        return None,{'status':'unavailable','reason':'video_decoder_unavailable'}
    try:
        for i,row in enumerate(frames):
            if cancelled():raise KeyboardInterrupt
            ok,image=cap.read()
            if not ok:raise ValueError('Root video timeline differs.')
            entry=raw['frames'][i]
            if entry['frame_index']!=i:raise ValueError('Root source frame order differs.')
            outputs=entry.get('outputs') or {};camera=np.asarray(outputs.get('pred_cam_t',[]),float)
            points=np.asarray(pixels[i],float);box=entry.get('person_bbox');key=(row.get('tracking_segment',0),row.get('scene_index',0))
            inside=points.shape==(5,2) and np.isfinite(points).all() and (points[:,0]>=0).all() and (points[:,0]<w).all() and (points[:,1]>=0).all() and (points[:,1]<h).all()
            if row['positions'][1] is None or camera.shape!=(3,) or not np.isfinite(camera).all() or camera[2]<=.2 or not inside or box is None:
                previous=None;last=None;continue
            small=cv2.cvtColor(cv2.resize(image,size),cv2.COLOR_BGR2GRAY)
            box=np.asarray(box,float)*[sx,sy,sx,sy]
            if previous is None or last!=key:
                epoch+=1;cumulative=np.eye(3)
            else:
                step=background_step(previous,small,previous_box,box)
                if step is None:
                    rejected+=1;previous=None;last=None;continue
                cumulative=step@cumulative
            previous=small;previous_box=box;last=key
            zoom=math.sqrt(abs(np.linalg.det(cumulative[:2,:2])))
            if not .5<=zoom<=2 or np.linalg.norm(cumulative[:2,2])>max(size)*.75:
                rejected+=1;previous=None;last=None;continue
            transform=np.linalg.inv(scaled)@np.linalg.inv(cumulative)@scaled
            reference=(np.c_[points,np.ones(5)]@transform.T)[:,:2]
            depth=float(camera[2])*zoom
            metric=(reference-[w/2,h/2])*depth/focal
            pelvis[i]=[metric[4,0],depth,-metric[4,1]]
            feet_z[i]=-metric[:4,1];feet_x[i]=metric[:4,0];epochs[i]=epoch
    finally:cap.release()
    if cancelled():raise KeyboardInterrupt
    if digest(source)!=expected or digest(raw_path)!=data['raw_sha256']:raise ValueError('Root evidence changed during analysis.')
    count=int(np.isfinite(pelvis).all(axis=1).sum())
    return {'pelvis_camera_m':pelvis,'feet_camera_z_m':feet_z,'feet_camera_x_m':feet_x,'epochs':epochs.tolist()}, {
        'status':'estimated','valid_frames':count,'frames':n,'camera_rejected_frames':rejected,'camera_epochs':epoch+1,
        'source_sha256':expected,'raw_sha256':data['raw_sha256'],'camera_model':'background_2d_similarity_not_3d_slam',
        'depth':'native_sam_camera_translation_zoom_compensated','scale':'reference_humanoid_not_measured_person_height'}
