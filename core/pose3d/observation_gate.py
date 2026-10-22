"""Independent 2D observations are conditional hints, not measured truth."""
import numpy as np
from core.pose3d.motionbert_adapter import COCO_TO_MHR


def gate_observations(raw,independent,visual_support=lambda i,p:None,cancelled=lambda:False):
    frames=raw['frames'];rows=independent['frames'];n=len(frames);fps=raw['video']['fps'];events=[];selected={}
    if len(rows)!=n or fps<=0:raise ValueError('Observation timeline differs.')
    if any(row['frame_index']!=i or frames[i]['frame_index']!=i for i,row in enumerate(rows)):raise ValueError('Observation frame order differs.')
    def key(i):
        r=frames[i];return (r.get('tracking',{}).get('track_id'),r.get('tracking_segment'),r.get('scene',{}).get('index',0))
    for i in range(n):
        if cancelled():raise KeyboardInterrupt
        if rows[i].get('coco_image_joints') is None:continue
        points=np.asarray(rows[i]['coco_image_joints'],float);scores=np.asarray(rows[i]['coco_scores'],float)
        original=frames[i].get('outputs',{}).get('pred_keypoints_2d');bbox=frames[i].get('person_bbox')
        if points.shape!=(17,2) or scores.shape!=(17,) or not np.isfinite(points).all() or not np.isfinite(scores).all():raise ValueError('Invalid independent observation.')
        if original is None or bbox is None:continue
        original=np.asarray(original,float)
        if original.shape!=(70,2) or not np.isfinite(original).all():raise ValueError('Invalid raw model observation.')
        diag=max(float(np.linalg.norm(np.subtract(bbox[2:],bbox[:2]))),1.);options=[]
        for j in range(5,17):
            reasons=[];confidence=float(scores[j]);mhr=COCO_TO_MHR[j];residual=float(np.linalg.norm(points[j]-original[mhr]))
            independent_key=(rows[i].get('target_id'),rows[i].get('tracking_segment'),rows[i].get('scene_index'))
            if independent_key!=key(i):reasons.append('independent_target_or_scene_differs')
            if any(v is None for v in key(i)) or frames[i].get('roi') is None:reasons.append('target_or_roi_unavailable')
            if i==0 or i+1==n:reasons.append('two_sided_context_missing')
            elif any(key(t)!=key(i) or frames[t].get('tracking',{}).get('state')!='tracked' or rows[t].get('coco_image_joints') is None for t in (i-1,i,i+1)):
                reasons.append('tracking_boundary_or_missing_observation')
            else:
                local=np.array([rows[t]['coco_image_joints'][j] for t in (i-1,i,i+1)],float)
                confidence=min(float(rows[t]['coco_scores'][j]) for t in (i-1,i,i+1))
                if np.max(np.linalg.norm(np.diff(local,axis=0),axis=1))*fps/diag>3:reasons.append('image_velocity_conflict')
                if np.linalg.norm(local[1]-(local[0]+local[2])/2)/diag>.04:reasons.append('bidirectional_image_residual')
            if confidence<.55:reasons.append('independent_score_below_threshold')
            if residual<8:reasons.append('no_material_correction_needed')
            if residual>max(20.,diag*.12):reasons.append('model_disagreement_too_large')
            w=raw['video']['width'];h=raw['video']['height']
            if np.any(points[j]<0) or np.any(points[j]>=[w,h]):reasons.append('outside_image')
            visual=visual_support(i,points[j])
            if visual is None:reasons.append('person_pixel_evidence_missing')
            else:reasons.extend(visual)
            entry={'frame_index':i,'coco_joint_index':j,'mhr_joint_index':mhr,'image_position':points[j].tolist(),
                'minimum_three_frame_score':confidence,'sam3d_disagreement_pixels':residual,'reasons':reasons,
                'state':'eligible_unverified_hint' if not reasons else 'held','accuracy_verified':False}
            events.append(entry)
            if not reasons:options.append(entry)
        options.sort(key=lambda e:(-e['minimum_three_frame_score'],-e['sam3d_disagreement_pixels'],e['mhr_joint_index']))
        if options:selected[i]=options[:2]
    return {'frames':selected,'events':events,'limits':['model_score_and_agreement_do_not_prove_anatomy',
        'no_interpolated_or_MotionBERT_XY_positions_as_observations','no_threshold_lowering_for_hard_frames']}


def assess_refinement(control,guided,hints):
    bones=((5,7),(7,62),(6,8),(8,41),(9,11),(11,13),(10,12),(12,14))
    before=np.asarray(control['image_joints'],float);after=np.asarray(guided['image_joints'],float)
    q0=np.asarray(control['world_joints'],float);q1=np.asarray(guided['world_joints'],float)
    if before.shape!=(70,2) or after.shape!=(70,2) or q0.shape!=(70,3) or q1.shape!=(70,3) or not all(np.isfinite(x).all() for x in (before,after,q0,q1)):raise ValueError('Invalid guided model candidate.')
    if not 1<=len(hints)<=2:raise ValueError('Invalid guidance hint count.')
    indices=[h['mhr_joint_index'] for h in hints];targets=np.asarray([h['image_position'] for h in hints])
    if targets.shape!=(len(hints),2) or not np.isfinite(targets).all() or any(type(j) is not int or j not in (5,6,7,8,9,10,11,12,13,14,41,62) for j in indices):raise ValueError('Invalid guidance target.')
    e0=np.linalg.norm(before[indices]-targets,axis=1);e1=np.linalg.norm(after[indices]-targets,axis=1);reasons=[]
    if np.mean(e0)-np.mean(e1)<2 or np.mean(e1)>np.mean(e0)*.7 or np.any(e1>20) or np.any(e1>e0+1):reasons.append('hint_reprojection_not_sufficiently_improved')
    l0=np.array([np.linalg.norm(q0[a]-q0[b]) for a,b in bones]);l1=np.array([np.linalg.norm(q1[a]-q1[b]) for a,b in bones])
    if np.any(l0<1e-6) or np.any(l1/np.maximum(l0,1e-6)<.7) or np.any(l1/np.maximum(l0,1e-6)>1.4):reasons.append('guided_bone_length_conflict')
    torso=max(np.linalg.norm((q0[5]+q0[6]-q0[9]-q0[10])/2),1e-6)
    local0=q0-(q0[9]+q0[10])/2;local1=q1-(q1[9]+q1[10])/2
    if np.max(np.linalg.norm(local1[[5,6,9,10]]-local0[[5,6,9,10]],axis=1))>torso*.4:reasons.append('guided_body_reference_displacement')
    return {'accepted_as_model_hypothesis':not reasons,'reasons':reasons,'before_hint_residual_pixels':e0.tolist(),
        'after_hint_residual_pixels':e1.tolist(),'anatomical_accuracy_verified':False}
