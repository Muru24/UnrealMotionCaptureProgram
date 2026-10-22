"""Keep person tracking fixed; compare independent 2D observations and temporal lift."""
from pathlib import Path
from uuid import uuid4
import argparse,cv2,numpy as np
from app.completion_job import read
from app.fullbody_job import write
from app.knee_job import load_context,digest
from app.leg_reestimate_job import gpu_child
from core.pose2d.rtmpose_backend import RTMPoseBackend
from core.pose3d.motionbert_adapter import coco_to_h36m,segments,normalize_clip,mhr_comparison_points,H36M_NAMES,H36M_BONES,COCO_TO_MHR


def render_shapes(raw,prediction,path,cancelled):
    models=[{},{}]
    for i,frame in enumerate(raw['frames']):
        points=frame.get('outputs',{}).get('pred_keypoints_3d')
        if points is not None:models[0][i]=mhr_comparison_points(points)
    models[1]={r['frame_index']:np.asarray(r['world_joints_normalized']) for r in prediction['frames']}
    scales=[]
    for frames in models:
        lengths=[np.linalg.norm(q[8]-q[0]) for q in frames.values()]
        scale=float(np.median(lengths)) if lengths else 0
        if scale<1e-6:raise ValueError('Degenerate 3D comparison scale.')
        scales.append(scale)
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),raw['video']['fps'],(1440,720))
    try:
        if not writer.isOpened():raise ValueError('Cannot create shape comparison.')
        for i in range(len(raw['frames'])):
            if cancelled():raise KeyboardInterrupt
            canvas=np.full((720,1440,3),22,np.uint8)
            for model,name,color in ((0,'SAM3D',(210,170,70)),(1,'MOTIONBERT',(0,180,255))):
                for view,axes in enumerate(((0,1),(2,1))):
                    offset=(model*2+view)*360
                    cv2.putText(canvas,f'{name} '+('XY' if view==0 else 'ZY'),(offset+8,25),cv2.FONT_HERSHEY_SIMPLEX,.55,color,1)
                    if i in models[model]:
                        q=models[model][i];points=(q-q[0])[:,axes]/scales[model]*105+[offset+180,300]
                        for a,b in H36M_BONES:
                            u,v=[tuple(np.clip(points[j],-10000,10000).round().astype(int)) for j in (a,b)];visible,u,v=cv2.clipLine((offset,40,360,650),u,v)
                            if visible:cv2.line(canvas,u,v,color,2,cv2.LINE_AA)
            cv2.putText(canvas,f'FRAME {i} | ROOT CENTERED / EACH MODEL MEDIAN TORSO SCALED | NOT METRIC / NOT IMAGE OVERLAY',(12,706),cv2.FONT_HERSHEY_SIMPLEX,.5,(220,220,220),1)
            writer.write(canvas)
    finally:writer.release()


def run_independent(folder,source,cancelled=lambda:False,progress=lambda *a:None):
    folder=Path(folder).resolve();raw,source_hash,_=load_context(folder,source);n=len(raw['frames']);video=raw['video'];w=video['width'];h=video['height'];root=Path(__file__).resolve().parents[1]
    watched=[Path(source),folder/'sam3d.json',root/'models/pose2d/manifest.json',root/'models/pose2d/rtmpose-m.onnx',root/'models/motionbert-lite/manifest.json']
    hashes={str(p):digest(p) for p in watched};out=folder/('independent_'+uuid4().hex[:8]);out.mkdir();backend=None;cap=None;writer=None;rows=[];status='failed';clip_list=[]
    try:
        backend=RTMPoseBackend(root/'models/pose2d');cap=cv2.VideoCapture(str(source))
        if not cap.isOpened():raise ValueError('Cannot reopen comparison source.')
        for i,frame in enumerate(raw['frames']):
            if cancelled():raise KeyboardInterrupt
            ok,image=cap.read()
            if not ok or image.shape[:2]!=(h,w):raise ValueError('Independent comparison timeline differs.')
            tracked=frame.get('tracking',{});row={'frame_index':i,'target_id':tracked.get('track_id'),
                'tracking_segment':frame.get('tracking_segment'),'scene_index':frame.get('scene',{}).get('index',0),
                'h36m_input':None,'coco_image_joints':None,'coco_scores':None}
            box=frame.get('roi')
            if box is not None and tracked.get('state')=='tracked':
                points,scores=backend.pose(image,bboxes=[box]);points=np.asarray(points);scores=np.asarray(scores)
                if points.shape!=(1,17,2) or scores.shape!=(1,17):raise ValueError('Independent pose schema differs.')
                converted=coco_to_h36m(points[0],scores[0],w,h)
                row.update(coco_image_joints=points[0].tolist(),coco_scores=scores[0].tolist(),h36m_input=converted.tolist())
            rows.append(row);progress(i+1,n)
        cap.release();cap=None;backend.close();backend=None
        clip_list=segments(rows)
        if not clip_list:raise ValueError('No valid independent pose segments.')
        write(out/'independent-2d.json',{'schema':'independent_coco17_h36m_adapter_v1','frames':rows,'video':video,
            'head_input':'COCO_eye_midpoint_proxy_half_model_score','scores_are_not_calibrated_visibility':True})
        requests=[]
        for clip in clip_list:
            normalized,parameters=normalize_clip([rows[i]['h36m_input'] for i in clip])
            requests.append({'indices':clip,'input':normalized.tolist(),'normalization':parameters})
        write(out/'motionbert-request.json',{'segments':requests,'video':video})
        hashes[str(out/'motionbert-request.json')]=digest(out/'motionbert-request.json')
        gpu_child('motionbert_worker.py',out,'motionbert-progress.json',cancelled,progress)
        prediction=read(out/'motionbert-joints.json');expected=[i for clip in clip_list for i in clip]
        if [r['frame_index'] for r in prediction['frames']]!=expected:raise ValueError('MotionBERT output timeline differs.')
        by_frame={r['frame_index']:r for r in prediction['frames']}
        cap=cv2.VideoCapture(str(source));writer=cv2.VideoWriter(str(out/'independent-comparison.partial.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),video['fps'],(w*3,h))
        if not cap.isOpened() or not writer.isOpened():raise ValueError('Cannot create independent comparison.')
        # COCO skeleton with explicit conversion of its limb slots to H36M slots.
        for i,row in enumerate(rows):
            if cancelled():raise KeyboardInterrupt
            ok,image=cap.read()
            if not ok:raise ValueError('Comparison video ended early.')
            raw_points=raw['frames'][i].get('outputs',{}).get('pred_keypoints_2d');raw_points=None if raw_points is None else np.asarray(raw_points)[COCO_TO_MHR]
            sam=None if raw_points is None else coco_to_h36m(raw_points,np.ones(17),w,h)[:,:2]*(min(w,h)/2)+np.array([w,h])/2
            rtm=None if row['h36m_input'] is None else np.asarray(row['h36m_input'])[:,:2]*(min(w,h)/2)+np.array([w,h])/2
            lifted=None if i not in by_frame else np.asarray(by_frame[i]['image_xy_proxy'])
            panels=[]
            for points,title,color in ((sam,'SAM3D / SAME TRACK',(210,170,70)),(rtm,'RTMPOSE / INDEPENDENT 2D',(60,220,80)),(lifted,'MOTIONBERT / XY PROXY NOT CALIBRATED',(0,180,255))):
                view=image.copy()
                if points is not None:
                    for a,b in H36M_BONES:
                        u,v=[tuple(np.clip(points[j],-10000,10000).round().astype(int)) for j in (a,b)];visible,u,v=cv2.clipLine((0,0,w,h),u,v)
                        edge_color=(150,150,150) if title.startswith('RTMPOSE') and min(row['h36m_input'][a][2],row['h36m_input'][b][2])<.3 else color
                        if visible:cv2.line(view,u,v,edge_color,2,cv2.LINE_AA)
                cv2.putText(view,f'{i} {title}',(8,28),cv2.FONT_HERSHEY_SIMPLEX,.44,color,1);panels.append(view)
            writer.write(np.hstack(panels));progress(i+1,n)
        writer.release();writer=None;cap.release();cap=None
        render_shapes(raw,prediction,out/'shape-comparison.partial.mp4',cancelled)
        if cancelled():raise KeyboardInterrupt
        if any(digest(p)!=sha for p,sha in hashes.items()):raise ValueError('Independent comparison inputs changed.')
        (out/'shape-comparison.partial.mp4').replace(out/'shape-comparison.mp4')
        (out/'independent-comparison.partial.mp4').replace(out/'independent-comparison.mp4');status='completed_independent_model_comparison'
    except KeyboardInterrupt:status='cancelled';raise
    finally:
        if cap is not None:cap.release()
        if writer is not None:writer.release()
        if backend is not None:backend.close()
        (out/'independent-comparison.partial.mp4').unlink(missing_ok=True)
        (out/'shape-comparison.partial.mp4').unlink(missing_ok=True)
        write(out/'report.json',{'status':status,'source_sha256':source_hash,'input_hashes':hashes,'frames_processed':len(rows),
            'clip_lengths':[len(c) for c in clip_list],'automatic_pipeline_modified':False,'tracking_modified':False,
            'native_MHR_rotations_modified':False,'joint_format':'H36M17_separate_from_MHR70',
            'limits':['independent_2D_can_also_follow_cloth','head_adapter_is_proxy','XY_proxy_is_not_camera_calibration','3D_units_are_not_meters',
                      'chunk_edges_may_be_discontinuous','model_score_is_not_verified_visibility']})
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');p.add_argument('source');a=p.parse_args();print(run_independent(a.folder,a.source))
