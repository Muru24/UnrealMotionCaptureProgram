"""Isolated local SAM video inference; native MHR70 output, never MP33."""
import os
os.environ['WANDB_MODE']='disabled'
os.environ['HF_HUB_OFFLINE']='1'
os.environ['MOMENTUM_ENABLED']='0'
import json
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.validation/sam3d/source_cuda')]
CONNECTIONS=((5,6),(5,7),(7,62),(6,8),(8,41),(5,9),(6,10),(9,10),
             (9,11),(11,13),(10,12),(12,14),(13,15),(13,17),(14,18),(14,20))


def predict_target(estimator,frame,selected,target_id):
    import cv2
    import numpy as np
    if selected['roi'] is None or selected['tracking']['state']!='tracked':
        return None
    if selected['tracking']['track_id']!=target_id:
        raise RuntimeError('Selected target identity changed.')
    roi=np.asarray(selected['roi'],dtype=np.float32)
    h,w=frame.shape[:2]
    if roi.shape!=(4,) or not np.isfinite(roi).all() or min(roi)<0 or roi[2]>w or roi[3]>h or np.any(roi[2:]<=roi[:2]):
        raise RuntimeError('Invalid tracked ROI.')
    predictions=estimator.process_one_image(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB),
                                            bboxes=roi[None],inference_type='full')
    if len(predictions)!=1:raise RuntimeError('SAM returned no selected pose')
    prediction=predictions[0]
    points=np.asarray(prediction['pred_keypoints_2d'])
    world=np.asarray(prediction['pred_keypoints_3d'])
    if points.shape!=(70,2) or world.shape!=(70,3) or not np.isfinite(points).all() or not np.isfinite(world).all():
        raise RuntimeError('Invalid SAM coordinates')
    return prediction

from core.video.limits import MAX_VIDEO_FRAMES

def main(output):
    import cv2
    import numpy as np
    import torch
    torch.set_num_threads(min(8,os.cpu_count() or 4))
    from sam_3d_body import load_sam_3d_body, SAM3DBodyEstimator
    from sam_3d_body.metadata.mhr70 import mhr_names
    import sam_3d_body.build_models as builders
    request=json.loads((output/'sam-request.json').read_text(encoding='utf-8'))
    plan=json.loads((output/'sam-tracking.json').read_text(encoding='utf-8'))
    if plan.get('status')!='completed' or plan.get('target_id')!=1:
        raise RuntimeError('Finish target tracking before SAM inference.')
    if not torch.cuda.is_available():
        raise RuntimeError('SAM requires the installed CUDA GPU environment.')
    original=builders.load_state_dict
    def checked(module,state_dict,**kwargs):
        expected=module.state_dict()
        missing=sorted(set(expected)-set(state_dict))
        audit={'missing':missing,'unexpected':sorted(set(state_dict)-set(expected)),
               'wrong_shapes':[k for k in set(expected)&set(state_dict) if expected[k].shape!=state_dict[k].shape],
               'unapproved_missing':[k for k in missing if '.mhr.' not in k and not k.endswith('hand_pose_comps_ori')]}
        (output/'checkpoint-audit.json').write_text(json.dumps(audit,indent=2))
        if audit['wrong_shapes'] or audit['unapproved_missing'] or audit['unexpected']:
            raise RuntimeError('SAM checkpoint architecture mismatch')
        return original(module,state_dict,**kwargs)
    builders.load_state_dict=checked
    weights=ROOT/'models/sam3d_body_vith'
    with patch('torch.cuda.is_available',return_value=False):
        model,cfg=load_sam_3d_body(str(weights/'model.ckpt'),device='cpu',mhr_path=str(weights/'assets/mhr_model.pt'))
    model=model.to('cuda').eval()
    estimator=SAM3DBodyEstimator(model,cfg)
    metadata=request['video']
    capture=cv2.VideoCapture(request['source'])
    writer=cv2.VideoWriter(str(output/'overlay.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),
                           metadata['fps'],(metadata['width'],metadata['height']))
    if not capture.isOpened() or not writer.isOpened():
        capture.release(); writer.release()
        raise RuntimeError('Cannot open SAM input/output video')
    count=accepted=0
    started=perf_counter()
    status='failed'
    header={'version':2,'schema':'sam3d_mhr70','joint_names':mhr_names,
            'coordinates':'sam_native_pred_keypoints_3d','image_coordinates':'original_pixels_x_right_y_down',
            'root_motion':False,'fov':'official_default_not_calibrated','selection':plan['selection'],
            'target_id':plan['target_id'],'tracking_sidecar':'sam-tracking.json',
            'video':metadata,'inference_type':'full','frames':[]}
    try:
        with (output/'sam3d.json').open('x',encoding='utf-8') as stream:
            stream.write(json.dumps(header)[:-2])
            while True:
                ok,frame=capture.read()
                if not ok:break
                if count>=MAX_VIDEO_FRAMES:raise RuntimeError('Frame limit exceeded')
                if frame.shape[:2]!=(metadata['height'],metadata['width']):
                    raise RuntimeError('SAM video dimensions changed')
                if count>=len(plan['frames']) or plan['frames'][count]['frame_index']!=count:
                    raise RuntimeError('Tracking/video frame alignment differs')
                selected=plan['frames'][count]
                with torch.inference_mode():
                    prediction=predict_target(estimator,frame,selected,plan['target_id'])
                record={'frame_index':count,'timestamp':count/metadata['fps'],
                        'tracking_segment':selected.get('tracking_segment',0),
                        'roi':selected['roi'],'person_bbox':selected['person_bbox'],'tracking':selected['tracking'],
                        'outputs':None if prediction is None else {k:np.asarray(prediction[k]).tolist() for k in
                            ('pred_keypoints_2d','pred_keypoints_3d','pred_cam_t','body_pose_params','global_rot')}}
                if 'scene' in selected:record['scene']=selected['scene']
                stream.write((',' if count else '')+json.dumps(record,allow_nan=False))
                if prediction is not None:
                    accepted+=1;points=np.asarray(prediction['pred_keypoints_2d'])
                    for a,b in CONNECTIONS:
                        u,v=[tuple(np.clip(points[j],-10000,10000).round().astype(int)) for j in (a,b)]
                        visible,u,v=cv2.clipLine((0,0,frame.shape[1],frame.shape[0]),u,v)
                        if visible:cv2.line(frame,u,v,(0,240,0),2,cv2.LINE_AA)
                    for j in (7,8,41,62):
                        xy=tuple(np.clip(points[j],-10000,10000).round().astype(int))
                        cv2.circle(frame,xy,5,(0,140,255),-1)
                    x1,y1,x2,y2=map(int,selected['roi'])
                    cv2.rectangle(frame,(x1,y1),(x2,y2),(0,220,255),1)
                label=f'SAM | Target {plan["target_id"]} | '+('tracked ROI' if prediction is not None else
                    'WAITING FOR TARGET' if selected['tracking']['reason']=='before_target_start' else 'LOST - SAM skipped')
                if 'scene' in selected:
                    label+=f' | scene {selected["scene"]["index"]}'
                    if selected['scene']['cut']:label+=' | CUT'
                if selected.get('motion',{}).get('long_reidentified'):label+=' | REIDENTIFIED - CHECK TARGET'
                cv2.putText(frame,label,(15,30),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,220,255),1)
                writer.write(frame)
                count+=1
                (output/'frames-progress.txt').write_text(str(count))
            stream.write(']}')
        if not count or count!=len(plan['frames']):raise RuntimeError('Decoded and tracked frame counts differ')
        status='completed_with_warnings'
    finally:
        capture.release();writer.release()
        initial_frame=plan.get('initial_frame_index',0)
        report={'status':status,'backend':'SAM 3D Body ViT-H CUDA','frames_processed':count,
                'initial_frame_index':initial_frame,'frames_before_target_start':min(count,initial_frame),
                'scene_cuts':plan.get('scene_cuts',[]),
                'frames_with_target':accepted,'frames_without_target':count-accepted,
                'selection':plan['selection'],'target_id':plan['target_id'],'seconds':perf_counter()-started,
                'warnings':['SAM: 관절 정확도 미검증 · 수동 관절 미적용']+
                           (['scene_cuts_segmented_identity_not_verified'] if plan.get('scene_cuts') else [])+
                           (['target_starts_after_frame_zero'] if initial_frame else [])+
                           (['target_unavailable_in_some_frames'] if accepted<max(0,count-initial_frame) else [])+
                           (['target_reselection_required'] if any(f['tracking']['requires_reselection'] for f in plan['frames']) else [])}
        (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    main(Path(sys.argv[1]))
