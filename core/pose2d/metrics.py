"""Continuity diagnostics, never an automatic identity ground-truth score."""
import numpy as np


def tracking_metrics(plan,fps):
    gaps=[];box_jumps=[];body_jumps=[];reviews=[];start=None;previous=None
    for row in plan['frames']:
        index=row['frame_index'];box=row['person_bbox'];motion=row.get('motion',{})
        if row['roi'] is None:
            if start is None:start=index
            continue
        if start is not None:
            gaps.append({'start':start,'end_exclusive':index,'frames':index-start,'seconds':(index-start)/fps,'reconnected':True});start=None
        if previous is not None:
            old_box=np.asarray(previous['person_bbox']);new_box=np.asarray(box)
            scale=max(float(np.linalg.norm(old_box[2:]-old_box[:2])),1.)
            elapsed=index-previous['frame_index']
            distance=float(np.linalg.norm((new_box[:2]+new_box[2:]-old_box[:2]-old_box[2:])/2))
            box_event={'frame_index':index,'previous_frame':previous['frame_index'],'pixels':distance,
                       'normalized_per_frame':distance/scale/elapsed,'normalized_total':distance/scale,'gap_frames':elapsed-1}
            if box_event['normalized_per_frame']>.15 or (elapsed>1 and distance/scale>.35):box_jumps.append(box_event)
            p=previous.get('motion',{});kind=motion.get('observation_kind');oldkind=p.get('observation_kind')
            body=motion.get('observed_center');oldbody=p.get('observed_center')
            if kind in ('hip','shoulder_with_hip_offset') and oldkind in ('hip','shoulder_with_hip_offset') and body is not None and oldbody is not None:
                d=float(np.linalg.norm(np.asarray(body)-oldbody))
                if d/scale/elapsed>.15 or (elapsed>1 and d/scale>.35):body_jumps.append({**box_event,'pixels':d,'normalized_per_frame':d/scale/elapsed,'normalized_total':d/scale})
            reasons=[]
            if motion.get('long_reidentified'):reasons.append('long_gap_reidentification')
            if elapsed>1 and any(r['people_detected']>1 for r in plan['frames'][max(0,index-5):index+1]):reasons.append('reconnected_near_multiple_candidates')
            scores=[s for s in row.get('association_scores',[]) if 'components' in s and not s.get('rejected')]
            if scores:
                best=max(scores,key=lambda s:s['score'])
                if best['components']['appearance']<.65 and (elapsed>1 or box_event['normalized_per_frame']>.15):reasons.append('appearance_change_with_gap_or_jump')
                if best.get('appearance_gate_relaxed_by_body_motion'):reasons.append('appearance_change_accepted_with_motion_support')
            if row['people_detected']>1 and box_event['normalized_per_frame']>.15:reasons.append('center_jump_near_multiple_candidates')
            if reasons:reviews.append({'frame_index':index,'reasons':reasons,'manual_identity_review':'pending'})
        previous=row
    if start is not None:
        n=len(plan['frames']);gaps.append({'start':start,'end_exclusive':n,'frames':n-start,'seconds':(n-start)/fps,'reconnected':False})
    return {'version':1,'gap_count':len(gaps),'missing_frames':sum(g['frames'] for g in gaps),
            'body_measurement_frames':sum(r['roi'] is not None and r.get('motion',{}).get('observation_kind') in ('hip','shoulder_with_hip_offset') for r in plan['frames']),
            'box_fallback_frames':sum(r['roi'] is not None and r.get('motion',{}).get('observation_kind')=='box_fallback' for r in plan['frames']),
            'mean_gap_seconds':float(np.mean([g['seconds'] for g in gaps])) if gaps else 0.,
            'max_gap_seconds':max((g['seconds'] for g in gaps),default=0.),'gaps':gaps,
            'box_jump_events':box_jumps,'body_jump_events':body_jumps,'identity_review_events':reviews,
            'confirmed_identity_switches':None,'identity_ground_truth_available':False,
            'jump_threshold_normalized_per_frame':.15,
            'limits':['motion_jump_is_not_necessarily_an_error','no_flags_does_not_prove_no_identity_switch',
                      'body_jump_excludes_box_fallback','initial_and_terminal_gaps_are_included',
                      'not_joint_motion_accuracy','jump_threshold_is_a_review_heuristic']+
                     (['sam2_has_no_per_frame_person_count','sam2_has_no_skeleton_body_measurement',
                       'mask_visibility_does_not_verify_identity'] if plan.get('selection')=='sam2_video_mask' else [])}
