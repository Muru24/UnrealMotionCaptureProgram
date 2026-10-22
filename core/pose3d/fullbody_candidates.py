"""Full MHR70 hypothesis handoff. Derived axes are not measured spine bones."""
import numpy as np

PARTS={'torso':[5,6,9,10,69],'head':[0,1,2,3,4,69],
       'left_arm':[5,7,62],'right_arm':[6,8,41],
       'left_leg':[9,11,13],'right_leg':[10,12,14],
       'left_foot':[13,15,16,17],'right_foot':[14,18,19,20],
       'left_hand':list(range(42,63)),'right_hand':list(range(21,42))}
HYPOTHESES=('observed','stable','tight','stable-flip')
LIMB_BONES=((5,7),(7,62),(6,8),(8,41),(9,11),(11,13),(10,12),(12,14))

def describe(candidate,width,height):
    world=np.asarray(candidate['world_joints'],dtype=float);image=np.asarray(candidate['image_joints'],dtype=float)
    if world.shape!=(70,3) or image.shape!=(70,2) or not np.isfinite(world).all() or not np.isfinite(image).all():
        raise ValueError('Invalid MHR70 full-body hypothesis.')
    def references(points):
        pelvis=(points[9]+points[10])/2;shoulders=(points[5]+points[6])/2
        return {'pelvis_center':pelvis.tolist(),'shoulder_center':shoulders.tolist(),'neck':points[69].tolist(),
                'spine_axis_proxy':[pelvis.tolist(),shoulders.tolist()],
                'torso_axis_length':float(np.linalg.norm(shoulders-pelvis)),
                'degenerate_torso_axis':bool(np.linalg.norm(shoulders-pelvis)<1e-6)}
    inside=(image[:,0]>=0)&(image[:,0]<width)&(image[:,1]>=0)&(image[:,1]<height)
    return {'world_joints':world.tolist(),'image_joints':image.tolist(),
            'references_world':references(world),'references_image':references(image),
            'joint_inside_frame':inside.tolist(),'visibility':None,'accuracy_confidence':None,
            'limb_lengths_world':[float(np.linalg.norm(world[b]-world[a])) for a,b in LIMB_BONES],
            'provenance':'SAM3D_model_estimate','input_roi':candidate.get('input_roi')}

def build_packet(raw,variants,selected,cancelled=lambda:False):
    frames=raw['frames'];video=raw['video']
    if len(selected)!=len(frames):raise ValueError('Full-body selection timeline differs.')
    rows=[]
    for i,(frame,choice) in enumerate(zip(frames,selected)):
        if cancelled():raise KeyboardInterrupt
        if frame['frame_index']!=i or choice['frame_index']!=i:raise ValueError('Full-body frame order differs.')
        tracking=frame.get('tracking',{});prediction=frame.get('outputs')
        available=(prediction is not None and frame.get('person_bbox') is not None and
                   tracking.get('track_id',raw.get('target_id',1))==raw.get('target_id',1) and
                   tracking.get('state','tracked')=='tracked' and not frame.get('motion',{}).get('prediction_only') and
                   ('roi' not in frame or frame['roi'] is not None))
        row={'frame_index':i,'timestamp':i/video['fps'],'target_id':tracking.get('track_id',raw.get('target_id',1)),
             'tracking_segment':frame.get('tracking_segment',0),'scene_index':frame.get('scene',{}).get('index',0),
             'person_bbox':frame.get('person_bbox'),'roi':frame.get('roi'),
             'status':'model_estimates' if available else 'target_unavailable',
             'selected_candidate':None,'selected_pose_status':'unavailable','candidates':{},'unavailable_candidates':{}}
        if available:
            baseline={'world_joints':prediction['pred_keypoints_3d'],'image_joints':prediction['pred_keypoints_2d'],'input_roi':frame.get('roi')}
            for name in HYPOTHESES:
                candidate=baseline if name=='stable' else variants.get(i,{}).get(name)
                if candidate is None:row['unavailable_candidates'][name]='candidate_not_generated';continue
                try:
                    row['candidates'][name]=describe(candidate,video['width'],video['height'])
                    row['candidates'][name].update(input_transform='horizontal_flip' if name=='stable-flip' else 'none',
                        input_roi_coordinates='flipped_image_pixels' if name=='stable-flip' else 'original_image_pixels',
                        output_joint_coordinates='original_image_and_restored_camera_axes')
                except (ValueError,TypeError,KeyError):row['unavailable_candidates'][name]='invalid_joint_array'
            chosen='stable' if choice['candidate']=='raw' else choice['candidate']
            if chosen in row['candidates']:
                candidate=row['candidates'][chosen]
                if np.array_equal(np.asarray(choice['world_joints']),candidate['world_joints']) and np.array_equal(np.asarray(choice['image_joints']),candidate['image_joints']):
                    row['selected_candidate']=chosen;row['selected_pose_status']='matched_candidate'
                else:row['selected_pose_status']='selected_pose_not_in_pool'
            if not row['candidates']:row['status']='no_valid_candidates'
        rows.append(row)
    return {'schema':'fullbody_hypotheses_mhr70_v1','exporter_revision':1,'video':video,'joint_layout':'MHR70',
            'joint_names':raw.get('joint_names'),'parts':PARTS,'limb_bones':LIMB_BONES,
            'expected_candidates':HYPOTHESES,'frames':rows,
            'coordinates':{'image':'original_pixels','world':'SAM3D_camera_relative_not_UE_world'},
            'limits':['spine_axis_is_derived_not_native_spine_joints','all_candidates_can_be_wrong',
                      'inside_frame_does_not_mean_visible','no_joint_accuracy_confidence',
                      'no_tracking_reassignment_or_temporal_interpolation','no_MHR_rotation_or_skeleton_format_changes']}
