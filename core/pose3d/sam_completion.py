"""MHR70 completion and review adapter. Raw SAM files remain model-native."""
import numpy as np
from core.pose3d.completion import complete

LEGS=((9,11,13),(10,12,14))
ARM_JOINTS=(5,6,7,8,41,62)
FOOT_PAIRS=((13,15),(13,16),(13,17),(14,18),(14,19),(14,20))
CONNECTIONS=((5,6),(5,7),(7,62),(6,8),(8,41),(5,9),(6,10),(9,10),
             (9,11),(11,13),(10,12),(12,14))+FOOT_PAIRS


def adapt(raw):
    if raw.get('schema')!='sam3d_mhr70' or raw.get('coordinates')!='sam_native_pred_keypoints_3d':
        raise ValueError('Expected native SAM MHR70 output.')
    names=raw['joint_names']
    required={9:'left-hip',10:'right-hip',11:'left-knee',12:'right-knee',
              13:'left-ankle',14:'right-ankle',17:'left-heel',20:'right-heel'}
    if len(names)!=70 or any(names[i]!=name for i,name in required.items()):
        raise ValueError('Unexpected SAM joint ordering.')
    frames=[];tracking=[]
    width,height=raw['video']['width'],raw['video']['height']
    for t,f in enumerate(raw['frames']):
        if f['frame_index']!=t:raise ValueError('SAM frame alignment differs.')
        info=f.get('tracking')
        tracked=info is None or info['state']=='tracked'
        if info is not None and tracked and info['track_id']!=raw.get('target_id',1):
            raise ValueError('SAM target identity changed.')
        if not tracked:
            frames.append({'frame_index':t,'timestamp':f['timestamp'],'person_bbox':None,
                           'landmarks':[{'x':None,'y':None,'z':None,'valid':False,'render_valid':False} for _ in range(70)]})
            tracking.append({'frame_index':t,'tracking':{'state':'lost'}})
            continue
        if f['outputs'] is None:raise ValueError('Tracked SAM frame has no pose output.')
        xyz=np.asarray(f['outputs']['pred_keypoints_3d'],dtype=float)
        image=np.asarray(f['outputs']['pred_keypoints_2d'],dtype=float)
        if xyz.shape!=(70,3) or image.shape!=(70,2):raise ValueError('SAM joint dimensions differ.')
        xyz=xyz-(xyz[9]+xyz[10])/2
        finite=np.isfinite(xyz).all(axis=1)
        in_frame=np.isfinite(image).all(axis=1)&(image[:,0]>=0)&(image[:,0]<width)&(image[:,1]>=0)&(image[:,1]<height)
        # A foot touching the frame edge may be truncated even if its center
        # projects just inside. This is a conservative heuristic, not visibility.
        mx,my=width*.02,height*.02
        in_frame[13:21]&=(image[13:21,0]>=mx)&(image[13:21,0]<width-mx)&(image[13:21,1]>=my)&(image[13:21,1]<height-my)
        eligible=bool(finite[[9,10]].all() and in_frame[[9,10]].any())
        landmarks=[]
        for j,p in enumerate(xyz):
            valid=bool(finite[j] and (in_frame[j] if 11<=j<=20 or j in ARM_JOINTS else True))
            landmarks.append(dict(zip(('x','y','z'),[float(v) if np.isfinite(v) else None for v in p]),
                                  valid=valid,render_valid=bool(finite[j]),
                                  image_xy=[float(v) if np.isfinite(v) else None for v in image[j]]))
        roi=f.get('roi',raw.get('roi'))
        if roi is None:raise ValueError('Tracked SAM frame has no ROI.')
        frames.append({'frame_index':t,'timestamp':f['timestamp'],'person_bbox':roi if eligible else None,'landmarks':landmarks})
        tracking.append({'frame_index':t,'tracking':{'state':'tracked' if eligible else 'lost'}})
    for original,frame in zip(raw['frames'],frames):
        frame['tracking_segment']=original.get('tracking_segment',0)
        if 'scene' in original:frame['scene']=dict(original['scene'])
    return {'frames':frames,'video':raw['video'],'joint_names':names,
            'coordinates':'sam_native_hip_relative_xyz'}, {'frames':tracking}


def complete_sam(raw,cancelled=lambda:False,*,temporal_repair=True):
    document,tracking=adapt(raw)
    result=complete(document,tracking,cancelled,chains=LEGS,leg_chains=LEGS,
                    foot_pairs=FOOT_PAIRS,allow_model_priors=True)
    from .joint_gaps import fill_arm_gaps
    fill_arm_gaps(document,result,cancelled)
    from .quality import review_pose
    result['quality_review']=review_pose(document,cancelled)
    from .temporal_guard import guard_temporal
    if temporal_repair:guard_temporal(document,result,cancelled)
    temporal_frames=result.get('temporal_guard',{}).get('frames',[{'bones':[]} for _ in document['frames']])
    for frame,review,temporal in zip(result['frames'],result['quality_review']['frames'],temporal_frames):
        frame['review_bones']=[list(b) for b in sorted({tuple(b) for b in review['bones']+temporal['bones']})]
    result['review_summary']=dict(result['quality_review']['summary'],
        review_frames=sum(bool(f['review_bones']) for f in result['frames']),
        original_review_frames=result['quality_review']['summary']['review_frames'],
        temporal_review_frames=result.get('temporal_guard',{}).get('review_frames',0),
        temporal_events=len(result.get('temporal_guard',{}).get('events',[])))
    for original,adapted,repaired in zip(raw['frames'],document['frames'],result['frames']):
        adapted['tracking_segment']=repaired['tracking_segment']=original.get('tracking_segment',0)
        if 'scene' in original:repaired['scene']=dict(original['scene'])
    result.update(schema='sam3d_mhr70_completion',selection=raw['selection'],
                  validity='finite_model_prediction; limbs also require image projection inside frame',
                  source_schema='sam3d_mhr70',origin='midpoint_of_model_hips_per_frame',
                  foot_edge_margin_fraction=.02,
                  observed_meaning='model prediction; for limbs, projection is inside frame, not measured visibility')
    result['limits']+=['in_frame_is_not_joint_accuracy_or_visibility','hidden_model_calibration_is_estimated',
                       'identity_tracking_not_ground_truth','lost_target_frames_not_completed',
                       'short_arm_gaps_only_no_hidden_arm_extrapolation','no_interpolation_across_tracking_segments']
    if temporal_repair:result['limits']+=['temporal_consensus_not_anatomical_truth','temporal_estimates_labeled_with_before_values']
    return document,result
