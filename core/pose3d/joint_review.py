"""Segment-local joint diagnostics, never ground truth or a pose correction."""
from collections import Counter
import numpy as np
from core.pose3d.fullbody_candidates import LIMB_BONES

REPAIR_PARTS={'left_arm':(5,7,62),'right_arm':(6,8,41),
              'left_leg':(9,11,13,15,16,17),'right_leg':(10,12,14,18,19,20),
              'torso':(5,6,9,10,69)}
PAIRS=((5,6),(7,8),(62,41),(9,10),(11,12),(13,14))
DEFAULTS={'length_min_ratio':.65,'length_max_ratio':1.55,'bilateral_ratio':1.8,
          'temporal_residual_torso':.30,'disagreement_torso':.35,'disagreement_image_diagonal':.08,
          'swap_improvement_ratio':.55,'swap_min_distance_torso':.20,
          'temporal_radius_seconds':.067,'context_seconds':.15}

def review_joints(packet,mask_evidence=None,cancelled=lambda:False):
    if packet.get('schema')!='fullbody_hypotheses_mhr70_v1':raise ValueError('Expected full-body hypotheses.')
    frames=packet['frames'];fps=float(packet['video']['fps']);n=len(frames)
    if not np.isfinite(fps) or fps<=0:raise ValueError('Invalid joint review fps.')
    if any(r['frame_index']!=i for i,r in enumerate(frames)):raise ValueError('Joint review timeline differs.')
    radius=max(1,round(fps*DEFAULTS['temporal_radius_seconds']));context=max(1,round(fps*DEFAULTS['context_seconds']))
    selected=[r['candidates'].get(r['selected_candidate']) if r['status']=='model_estimates' else None for r in frames]
    rows=[{'frame_index':i,'target_id':r['target_id'],'tracking_segment':r['tracking_segment'],
           'scene_index':r['scene_index'],'status':'unavailable' if selected[i] is None else 'model_estimate_unverified',
           'pose_track_start':None,'joints':[],'review_parts':[]} for i,r in enumerate(frames)]
    groups=[];start=0
    while start<n:
        if selected[start] is None:start+=1;continue
        key=tuple(frames[start][k] for k in ('target_id','tracking_segment','scene_index'));end=start+1
        while end<n and selected[end] is not None and tuple(frames[end][k] for k in ('target_id','tracking_segment','scene_index'))==key:end+=1
        groups.append((start,end));start=end
    references=[]
    for start,end in groups:
        if cancelled():raise KeyboardInterrupt
        world=np.array([c['world_joints'] for c in selected[start:end]],float)
        pixels=np.array([c['image_joints'] for c in selected[start:end]],float)
        if world.shape!=(end-start,70,3) or pixels.shape!=(end-start,70,2) or not np.isfinite(world).all() or not np.isfinite(pixels).all():raise ValueError('Invalid selected review joints.')
        roots=(world[:,9]+world[:,10])/2;relative=world-roots[:,None,:]
        torso=np.linalg.norm((world[:,5]+world[:,6])/2-roots,axis=1)
        lengths=np.stack([np.linalg.norm(world[:,b]-world[:,a],axis=1) for a,b in LIMB_BONES],axis=1)
        ref=np.median(lengths,axis=0);scale=max(float(np.median(torso)),1e-6)
        references.append({'start':start,'end_exclusive':end,'median_limb_lengths':ref.tolist(),
                           'median_torso_scale':scale,'source':'segment_model_median_not_anatomical_truth'})
        for t in range(end-start):
            if cancelled():raise KeyboardInterrupt
            i=start+t;frame=frames[i];pose=selected[i];reasons=[set() for _ in range(70)];metrics=[{} for _ in range(70)]
            rows[i]['pose_track_start']=start
            for j in range(70):
                metrics[j]['backward_velocity_torso_per_second']=None if t==0 else ((relative[t,j]-relative[t-1,j])*fps/scale).tolist()
                metrics[j]['forward_velocity_torso_per_second']=None if t+1==end-start else ((relative[t+1,j]-relative[t,j])*fps/scale).tolist()
            def flag(joints,reason):
                for j in joints:reasons[j].add(reason)
            if torso[t]<1e-6:flag(REPAIR_PARTS['torso'],'body_reference_degenerate')
            for k,(a,b) in enumerate(LIMB_BONES):
                ratio=float(lengths[t,k]/max(ref[k],1e-6))
                for j in (a,b):metrics[j].setdefault('bone_length_ratios',[]).append(ratio)
                if lengths[t,k]<1e-6 or ref[k]<1e-6:flag((a,b),'degenerate_bone')
                elif not DEFAULTS['length_min_ratio']<=ratio<=DEFAULTS['length_max_ratio']:flag((a,b),'bone_length_change')
            for left,right in ((0,2),(1,3),(4,6),(5,7)):
                ratio=max(lengths[t,left],lengths[t,right])/max(min(lengths[t,left],lengths[t,right]),1e-6)
                if ratio>DEFAULTS['bilateral_ratio']:flag(LIMB_BONES[left]+LIMB_BONES[right],'bilateral_length_mismatch')
            temporal_available=t>=radius and t+radius<end-start
            if temporal_available:
                expected=(relative[t-radius]+relative[t+radius])/2
                residual=np.linalg.norm(relative[t]-expected,axis=1)/scale
                for j,value in enumerate(residual):
                    metrics[j]['bidirectional_residual_torso']=float(value)
                    if value>DEFAULTS['temporal_residual_torso']:flag((j,),'temporal_inconsistency')
                for a,b in PAIRS:
                    direct=np.linalg.norm(relative[t,a]-expected[a])+np.linalg.norm(relative[t,b]-expected[b])
                    swapped=np.linalg.norm(relative[t,a]-expected[b])+np.linalg.norm(relative[t,b]-expected[a])
                    if direct/scale>DEFAULTS['swap_min_distance_torso'] and swapped<direct*DEFAULTS['swap_improvement_ratio']:flag((a,b),'left_right_swap_suspected')
            candidates=list(frame['candidates'].values());diagonal=max(float(np.linalg.norm(np.subtract(frame['person_bbox'][2:],frame['person_bbox'][:2]))),1.)
            if len(candidates)>1:
                q=np.asarray([c['world_joints'] for c in candidates],float);q-=((q[:,9]+q[:,10])/2)[:,None,:]
                p=np.asarray([c['image_joints'] for c in candidates],float)
                # Median distance prevents one poor augmentation from vetoing every joint.
                spread=np.median(np.linalg.norm(q-relative[t],axis=2),axis=0)/scale
                image_spread=np.median(np.linalg.norm(p-pixels[t],axis=2),axis=0)/diagonal
                for j in range(70):
                    metrics[j].update(candidate_disagreement_torso=float(spread[j]),candidate_disagreement_image=float(image_spread[j]))
                    if spread[j]>DEFAULTS['disagreement_torso'] or image_spread[j]>DEFAULTS['disagreement_image_diagonal']:flag((j,),'candidate_disagreement')
            evidence=(mask_evidence or {}).get(i)
            for j in range(70):
                inside=bool(pose['joint_inside_frame'][j]);distance=None
                if not inside:flag((j,),'outside_frame')
                if evidence and evidence.get('status')=='available' and inside:
                    distance=evidence['distances'][j]
                    if distance is not None and distance>evidence['tolerance_pixels']:flag((j,),'outside_person_mask')
                trajectory=f"{rows[i]['target_id']}:{rows[i]['tracking_segment']}:{rows[i]['scene_index']}:{start}:{j}"
                rows[i]['joints'].append({'joint_index':j,'trajectory_id':trajectory,'image_position':pixels[t,j].tolist(),
                    'world_position':world[t,j].tolist(),'root_relative_position':relative[t,j].tolist(),
                    'state':'outside_frame' if not inside else 'review' if reasons[j] else 'model_estimate_unverified',
                    'reasons':sorted(reasons[j]),'temporal_context_available':temporal_available,
                    'mask_evidence_status':evidence.get('status','unknown') if evidence else 'unknown',
                    'mask_distance_pixels':distance,'metrics':metrics[j]})
            rows[i]['review_parts']=[name for name,joints in REPAIR_PARTS.items() if any(reasons[j] for j in joints)]
            if any(reasons):rows[i]['status']='review'
    requests=[]
    for start,end in groups:
        for part in REPAIR_PARTS:
            i=start
            while i<end:
                if part not in rows[i]['review_parts']:i+=1;continue
                a=i;i+=1
                while i<end and part in rows[i]['review_parts']:i+=1
                requests.append({'part':part,'start':a,'end_exclusive':i,'context_start':max(start,a-context),
                    'context_end_exclusive':min(end,i+context),'target_id':rows[a]['target_id'],
                    'tracking_segment':rows[a]['tracking_segment'],'scene_index':rows[a]['scene_index'],
                    'pose_track_start':start,
                    'joint_indices':list(REPAIR_PARTS[part]),'action':'review_body_reference' if part=='torso' else 'review_then_reestimate',
                    'reasons':sorted({r for row in rows[a:i] for j in REPAIR_PARTS[part] for r in row['joints'][j]['reasons']})})
    counts=Counter(r for row in rows for joint in row['joints'] for r in joint['reasons'])
    return {'schema':'joint_review_mhr70_v1','review_revision':2,'video':packet['video'],'frames':rows,
        'thresholds':dict(DEFAULTS),'references':references,'repair_requests':requests,
        'input_stage':'selected_fullbody_before_legacy_leg_reestimation',
        'summary':{'frames':n,'review_frames':sum(r['status']=='review' for r in rows),
            'unavailable_frames':sum(r['status']=='unavailable' for r in rows),'repair_requests':len(requests),
            'reason_counts':dict(counts)},
        'limits':['review_flags_are_not_error_ground_truth','smooth_systematic_cloth_errors_can_be_missed',
                  'rapid_real_motion_can_trigger_review','model_median_can_be_wrong',
                  'mask_support_does_not_prove_anatomical_joint_location','no_pose_replacement_or_interpolation']}
