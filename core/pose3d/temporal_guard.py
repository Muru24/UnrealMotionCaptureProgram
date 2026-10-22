"""Two-sided distal-joint repair, with whole-body turns left for review."""
from collections import Counter
import numpy as np

EDGES=((7,62),(8,41),(11,13),(12,14))
DEPENDENTS={62:tuple(range(42,62)),41:tuple(range(21,41)),13:(15,16,17),14:(18,19,20)}


def cosine(a,b):
    denominator=float(np.linalg.norm(a)*np.linalg.norm(b))
    return float(np.dot(a,b)/denominator) if denominator>1e-8 else -1.


def guard_temporal(document,result,cancelled=lambda:False):
    frames=document['frames'];n=len(frames);fps=document['video']['fps']
    xyz=np.full((n,70,3),np.nan);image=np.full((n,70,2),np.nan);valid=np.zeros((n,70),bool)
    for i,f in enumerate(frames):
        for j,p in enumerate(f['landmarks']):
            if p['valid']:
                xyz[i,j]=[p[k] for k in ('x','y','z')];valid[i,j]=True
            if 'image_xy' in p:image[i,j]=p['image_xy']
    eligible=np.array([f['person_bbox'] is not None for f in frames])
    segments=np.array([f.get('tracking_segment',0) for f in frames])
    shoulder=xyz[:,6]-xyz[:,5];vertical=(xyz[:,5]+xyz[:,6]-xyz[:,9]-xyz[:,10])/2
    hip=(image[:,9]+image[:,10])/2
    torso=np.linalg.norm(vertical,axis=1)
    image_torso=np.linalg.norm((image[:,5]+image[:,6])/2-hip,axis=1)
    events=[];blocked=Counter();used=set();review=[set() for _ in frames]
    for i in range(1,n):
        if eligible[i-1:i+1].all() and segments[i]==segments[i-1] and np.isfinite(shoulder[i-1:i+1]).all():
            if cosine(shoulder[i-1],shoulder[i])<-.34:
                events.append(dict(start=i,end_exclusive=i+1,reason='abrupt_body_axis_change',action='review_only'))
                review[i].add((5,6))
    for parent,child in EDGES:
        vectors=xyz[:,child]-xyz[:,parent];pixels=image[:,child]-image[:,parent]
        for width in (1,2):
            if width/fps>.1:continue
            for start in range(2,n-width-1):
                if cancelled():raise KeyboardInterrupt
                end=start+width;window=slice(start-2,end+2)
                if not eligible[window].all() or not (segments[window]==segments[start]).all():continue
                if not valid[window,parent].all() or not valid[window,child].all():continue
                u,v=vectors[start-1],vectors[end]
                if cosine(u,v)<.94:continue
                # Candidates depart from both agreeing endpoints, not ordinary motion.
                if not all(cosine(vectors[k],u)<.6 and cosine(vectors[k],v)<.6 for k in range(start,end)):continue
                if any((k,child) in used for k in range(start,end)):continue
                reason=None
                lengths=np.linalg.norm(vectors[window],axis=1)
                if not np.isfinite(lengths).all() or np.min(lengths)<.02 or np.max(lengths)>1.5:reason='invalid_length'
                elif max(np.linalg.norm(u),np.linalg.norm(v))/min(np.linalg.norm(u),np.linalg.norm(v))>1.18:reason='endpoint_length_disagreement'
                elif cosine(vectors[start-2],u)<.96 or cosine(v,vectors[end+1])<.96:reason='unstable_endpoints'
                elif not np.isfinite(image[window][:,[parent,child,5,6,9,10]]).all():reason='missing_projection_evidence'
                elif not np.isfinite(xyz[window][:,[5,6,9,10]]).all():reason='missing_body_reference'
                else:
                    for axes in (shoulder,vertical):
                        if cosine(axes[start-1],axes[end])<.95 or any(cosine(axes[k-1],axes[k])<.85 for k in range(start-1,end+1)):
                            reason='body_turn_or_pose_flip';break
                if reason is None:
                    expected_length=(np.linalg.norm(u)+np.linalg.norm(v))/2
                    if not all(not .65<=np.linalg.norm(vectors[k])/expected_length<=1.35 for k in range(start,end)):
                        reason='no_length_outlier_evidence'
                if reason is None:
                    for k in range(start,end):
                        attached=DEPENDENTS[child]
                        observed=[j for j in attached if valid[k,j]]
                        if any(np.linalg.norm(xyz[k,j]-xyz[k,child])>.3 for j in observed):
                            reason='inconsistent_attached_group';break
                if reason is None:
                    if cosine(pixels[start-1],pixels[end])<.9 or not all(cosine(pixels[k],pixels[start-1])<.7 and cosine(pixels[k],pixels[end])<.7 for k in range(start,end)):
                        reason='projection_does_not_confirm'
                if reason is None:
                    for k in range(start,end):
                        alpha=(k-start+1)/(width+1)
                        expected=(1-alpha)*xyz[start-1,parent]+alpha*xyz[end,parent]
                        expected_image=(1-alpha)*(image[start-1,parent]-hip[start-1])+alpha*(image[end,parent]-hip[end])
                        if (np.linalg.norm(xyz[k,parent]-expected)>.12*torso[k]
                            or np.linalg.norm(image[k,parent]-hip[k]-expected_image)>.15*image_torso[k]):
                            reason='parent_motion';break
                if reason is None:
                    for k in range(start-2,end+2):
                        if any(result['frames'][k]['joints'][j]['source'] not in ('observed','length_constrained') for j in (parent,child)):
                            reason='untrusted_completion_source';break
                action='review_only' if reason else 'interpolated'
                event=dict(start=start,end_exclusive=end,parent=parent,joint=child,
                           reason=reason or 'two_sided_3d_and_projection_consensus',action=action)
                events.append(event)
                for k in range(start,end):review[k].add((parent,child))
                if reason:blocked[reason]+=1;continue
                for k in range(start,end):
                    alpha=(k-start+1)/(width+1)
                    direction=(1-alpha)*u/np.linalg.norm(u)+alpha*v/np.linalg.norm(v)
                    direction/=np.linalg.norm(direction)
                    length=(1-alpha)*np.linalg.norm(u)+alpha*np.linalg.norm(v)
                    joint=result['frames'][k]['joints'][child]
                    old=np.array(joint['xyz']);replacement=np.array(result['frames'][k]['joints'][parent]['xyz'])+direction*length
                    joint.update(xyz=replacement.tolist(),before_temporal_source=joint['source'],
                                 source='temporal_interpolated',suspect=True,before_temporal=old.tolist())
                    for dependent in DEPENDENTS[child]:
                        attached=result['frames'][k]['joints'][dependent]
                        if attached['xyz'] is not None:
                            previous=list(attached['xyz'])
                            attached.update(xyz=(np.array(previous)+replacement-old).tolist(),
                                            before_temporal_source=attached['source'],source='temporal_parent_offset',
                                            before_temporal=previous,suspect=True)
                    used.add((k,child))
    result['temporal_guard']={'version':1,'meaning':'heuristic_consensus_not_anatomical_truth',
        'max_gap_seconds':.1,'max_frames':2,'events':events,'blocked':dict(blocked),
        'repaired_joint_frames':len(used),'review_frames':sum(bool(r) for r in review),
        'frames':[{'frame_index':i,'bones':[list(b) for b in sorted(r)]} for i,r in enumerate(review)],
        'limits':['persistent_wrong_pose_not_repaired','whole_body_turns_review_only',
                  'fast_real_reversal_with_length_error_can_still_be_modified',
                  'same_segment_only','no_visibility_ground_truth','attached_fingers_and_feet_translated_not_reestimated']}
    result['counts']=dict(Counter(j['source'] for f in result['frames'] for j in f['joints']))
