"""CUDA candidate inference. Outputs joints, never converted MHR rotations."""
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['WANDB_MODE']='disabled'
os.environ['MOMENTUM_ENABLED']='0'
from pathlib import Path
import sys
import json
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.validation/sam3d/source_cuda')]


def main(output):
    import numpy as np
    import cv2
    import torch
    from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
    from sam_3d_body.metadata.mhr70 import mhr_names
    import sam_3d_body.build_models as builders
    from core.pose3d.candidate_geometry import restore_flip,flip_roi
    torch.set_num_threads(min(8,os.cpu_count() or 4))
    request=json.loads((output/'request.json').read_text(encoding='utf-8'))
    inference_type=request.get('inference_type','full')
    if inference_type not in ('full','body'):raise ValueError('Unsupported candidate inference type.')
    original=builders.load_state_dict
    def checked(module,state_dict,**kwargs):
        expected=module.state_dict();missing=sorted(set(expected)-set(state_dict))
        audit={'missing':missing,'unexpected':sorted(set(state_dict)-set(expected)),
               'wrong_shapes':[k for k in set(expected)&set(state_dict) if expected[k].shape!=state_dict[k].shape],
               'unapproved_missing':[k for k in missing if '.mhr.' not in k and not k.endswith('hand_pose_comps_ori')]}
        (output/'checkpoint-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
        if audit['unexpected'] or audit['wrong_shapes'] or audit['unapproved_missing']:raise RuntimeError('Checkpoint mismatch.')
        return original(module,state_dict,**kwargs)
    builders.load_state_dict=checked
    weights=ROOT/'models/sam3d_body_vith'
    with patch('torch.cuda.is_available',return_value=False):
        model,cfg=load_sam_3d_body(str(weights/'model.ckpt'),device='cpu',mhr_path=str(weights/'assets/mhr_model.pt'))
    estimator=SAM3DBodyEstimator(model.to('cuda').eval(),cfg)
    capture=cv2.VideoCapture(request['source']);records=[];index=0
    try:
        while True:
            ok,frame=capture.read()
            if not ok:break
            if index>=request['end_exclusive']:break
            if index>=request['start']:
                plan=request['frames'][index];w=frame.shape[1]
                if plan.get('roi') is None or plan.get('person_bbox') is None or plan.get('tracking',{}).get('state')!='tracked':
                    records.append({'frame_index':index,'candidates':{}});index+=1;continue
                bbox=np.array(plan['person_bbox'],float)
                size=bbox[2:]-bbox[:2];tight=np.r_[bbox[:2]-size*.05,bbox[2:]+size*.05]
                tight=np.clip(tight,[0,0,0,0],[w,frame.shape[0],w,frame.shape[0]])
                candidates={}
                observed=np.r_[bbox[:2]-size*[.25,.15],bbox[2:]+size*[.25,.15]]
                observed=np.clip(observed,[0,0,0,0],[w,frame.shape[0],w,frame.shape[0]])
                for name,image,roi in [('observed',frame,observed.tolist()),('tight',frame,tight.tolist()),
                                       ('stable-flip',cv2.flip(frame,1),flip_roi(plan['roi'],w))]:
                    with torch.inference_mode():
                        predictions=estimator.process_one_image(cv2.cvtColor(image,cv2.COLOR_BGR2RGB),
                                                              bboxes=np.asarray([roi],dtype=np.float32),inference_type=inference_type)
                    if len(predictions)!=1:raise RuntimeError('Expected one pose candidate.')
                    prediction=predictions[0]
                    p=np.asarray(prediction['pred_keypoints_2d']);q=np.asarray(prediction['pred_keypoints_3d'])
                    if p.shape!=(70,2) or q.shape!=(70,3) or not np.isfinite(p).all() or not np.isfinite(q).all():raise RuntimeError('Invalid candidate joints.')
                    original_p=p.copy();original_q=q.copy()
                    if name=='stable-flip':p,q=restore_flip(p,q,mhr_names,w)
                    candidates[name]={'image_joints':p.tolist(),'world_joints':q.tolist(),'input_roi':roi,
                        'raw_augmented_image_joints':original_p.tolist(),'raw_augmented_world_joints':original_q.tolist()}
                records.append({'frame_index':index,'candidates':candidates})
                (output/'progress.json').write_text(json.dumps({'done':len(records),'total':request['end_exclusive']-request['start']}),encoding='utf-8')
            index+=1
    finally:capture.release()
    if len(records)!=request['end_exclusive']-request['start']:raise RuntimeError('Incomplete window.')
    result={'schema':'joint_candidates_only_not_mhr_animation','joint_names':mhr_names,'frames':records,'inference_type':inference_type,
            'coordinates':'original_image_pixels_and_camera_relative_joint_positions',
            'limits':['no_body_pose_or_global_rotation_conversion','raw_MHR_rotations_not_replaced']}
    (output/'candidates.json').write_text(json.dumps(result,allow_nan=False),encoding='utf-8')


if __name__=='__main__':main(Path(sys.argv[1]).resolve())
