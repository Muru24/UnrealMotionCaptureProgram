"""Child-local adapter for native positive point tokens; upstream files unchanged."""
from unittest.mock import patch
import inspect
import numpy as np


def compatible_decoder(decoder):
    supports_full_output='full_output' in inspect.signature(decoder).parameters
    def call(*args,**kwargs):
        if not supports_full_output and 'full_output' in kwargs:
            value=kwargs.pop('full_output')
            if value is not None:raise ValueError('Unsupported nonempty native full_output state.')
        return decoder(*args,**kwargs)
    return call


def validate_hints(hints):
    if not 1<=len(hints)<=2:raise ValueError('Expected one or two native body point hints.')
    joints=set()
    for hint in hints:
        j=hint['mhr_joint_index'];p=np.asarray(hint['image_position'],float)
        if type(j) is not int or j not in (5,6,7,8,9,10,11,12,13,14,41,62) or j in joints or p.shape!=(2,) or not np.isfinite(p).all():raise ValueError('Invalid native point hint.')
        joints.add(j)


def predict_guided_body(estimator,image,roi,hints):
    import cv2,torch
    validate_hints(hints);model=estimator.model;original=model.forward_pose_branch
    if len(hints)>int(model.cfg.MODEL.PROMPT_ENCODER.MAX_NUM_CLICKS):raise ValueError('Too many native point prompts.')
    def guided(batch):
        output=original(batch);previous=[]
        for hint in hints:
            point=torch.zeros((1,70,2),device=output['image_embeddings'].device,dtype=output['image_embeddings'].dtype)
            joint=hint['mhr_joint_index'];point[0,joint]=torch.tensor(hint['image_position'],device=point.device,dtype=point.dtype)
            cropped=model._full_to_crop(batch,point)[0,joint]+.5
            if torch.any(cropped<0) or torch.any(cropped>1):raise ValueError('Independent hint lies outside model crop.')
            token=torch.cat((cropped,torch.tensor([float(model.prompt_keypoints[joint])],device=point.device,dtype=point.dtype))).view(1,1,3)
            with patch.object(model,'_get_keypoint_prompt',lambda *args,**kwargs:token),patch.object(model,'forward_decoder',compatible_decoder(model.forward_decoder)):
                output,used=model._one_prompt_iter(batch,output,previous,None)
            previous.append(used)
        return output
    # Body mode avoids mixing unrefined hand detection tokens with refined body state.
    with patch.object(model,'forward_pose_branch',guided):
        return estimator.process_one_image(cv2.cvtColor(image,cv2.COLOR_BGR2RGB),bboxes=np.asarray([roi],np.float32),inference_type='body')
