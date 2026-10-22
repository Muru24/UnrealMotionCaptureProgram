"""Offline, explicitly uncertain two-sided occlusion hypotheses; no new observation."""
import copy,cv2,numpy as np
from core.pose3d.manual_leg_geometry import body_basis,fit_camera,project
from core.pose3d.part_reestimation import PARTS,AUXILIARY,editable_joints,key


def direction(a,b,t):
    a=np.array(a,float,copy=True);b=np.array(b,float,copy=True)
    if not np.isfinite(a).all() or not np.isfinite(b).all() or min(np.linalg.norm(a),np.linalg.norm(b))<1e-6:raise ValueError('invalid_bone_direction')
    a/=np.linalg.norm(a);b/=np.linalg.norm(b)
    dot=float(np.clip(a@b,-1,1))
    if dot<-.95:raise ValueError('ambiguous_opposite_directions')
    theta=np.arccos(dot)
    value=(1-t)*a+t*b if theta<1e-5 else (np.sin((1-t)*theta)*a+np.sin(t*theta)*b)/np.sin(theta)
    return value/np.linalg.norm(value)


def rotation(a,b,t):
    vector=cv2.Rodrigues(a.T@b)[0];return a@cv2.Rodrigues(vector*t)[0]


def generate(packet,review,baseline,start,stop,body_context=False,max_gap_seconds=.6,cancelled=lambda:False):
    rows=copy.deepcopy(baseline['frames']);n=len(rows);fps=packet['video']['fps'];events=[]
    if not np.isfinite(fps) or fps<=0 or not 0<max_gap_seconds<=2.5:raise ValueError('Invalid temporal limits.')
    if len(review['frames'])!=n or len(packet['frames'])!=n or not 0<=start<stop<=n:raise ValueError('Temporal timeline differs.')
    if any(r['frame_index']!=i or review['frames'][i]['frame_index']!=i for i,r in enumerate(rows)):raise ValueError('Temporal frame order differs.')
    original=[None if r['world_joints'] is None else np.asarray(r['world_joints'],float) for r in rows]
    def valid(i,part):
        if original[i] is None or part in review['frames'][i].get('review_parts',[]) or 'torso' in review['frames'][i].get('review_parts',[]):return False
        q=original[i];p=np.asarray(baseline['frames'][i]['image_joints'])
        if q.shape!=(70,3) or p.shape!=(70,2) or not np.isfinite(q).all() or not np.isfinite(p).all():return False
        indices=[5,6,9,10,69] if part=='torso' else list(PARTS[part][:3])
        if np.any(p[indices]<0) or np.any(p[indices]>=[packet['video']['width'],packet['video']['height']]):return False
        try:body_basis(q)
        except ValueError:return False
        return True
    def brackets(i,part):
        limit=round(fps*max_gap_seconds);lo=i-1;hi=i+1;k=key(review['frames'][i])
        while lo>=0 and i-lo<=limit and key(review['frames'][lo])==k and original[lo] is not None:
            if valid(lo,part):break
            lo-=1
        while hi<n and hi-i<=limit and key(review['frames'][hi])==k and original[hi] is not None:
            if valid(hi,part):break
            hi+=1
        if lo<0 or hi>=n or key(review['frames'][lo])!=k or key(review['frames'][hi])!=k or not valid(lo,part) or not valid(hi,part) or hi-lo>limit:raise ValueError('no_bounded_two_sided_references')
        return lo,hi,(i-lo)/(hi-lo)
    for i in range(start,stop):
        if cancelled():raise KeyboardInterrupt
        if original[i] is None:continue
        q=original[i].copy();base=q.copy();changed=[];body_replaced=False
        try:camera=fit_camera(q,baseline['frames'][i]['image_joints'],packet['video']['width'],packet['video']['height'])
        except ValueError:events.append({'frame_index':i,'rejected':'camera_fit_failed'});continue
        if body_context and 'torso' in review['frames'][i].get('review_parts',[]):
            try:
                a,b,t=brackets(i,'torso');qa,qb=original[a],original[b];ba,bb=body_basis(qa),body_basis(qb);basis=rotation(ba,bb,t)
                root=(q[9]+q[10])/2;ra=(qa[9]+qa[10])/2;rb=(qb[9]+qb[10])/2
                torso=[5,6,9,10,67,68,69]
                local=(1-t)*((qa[torso]-ra)@ba)+t*((qb[torso]-rb)@bb)
                replacement=root+local@basis.T
                pixels=project(replacement,camera)
                scale=max(np.linalg.norm((q[5]+q[6]-q[9]-q[10])/2),1e-6)
                if np.max(np.linalg.norm(replacement-q[torso],axis=1))>scale*.25:raise ValueError('body_reference_displacement_too_large')
                if np.any(pixels<0) or np.any(pixels>=[packet['video']['width'],packet['video']['height']]):raise ValueError('body_reference_outside_image')
                old=q.copy();q[torso]=replacement
                for part,(root_joint,_,_,_) in PARTS.items():q[editable_joints(part)]+=q[root_joint]-old[root_joint]
                q[:5]+=q[69]-old[69];body_replaced=True
                events.append({'frame_index':i,'part':'torso','references':[a,b],'reference_span_seconds':(b-a)/fps,'hypothesis_only':True})
            except ValueError as error:events.append({'frame_index':i,'part':'torso','rejected':str(error)})
        for part,(root,middle,end,children) in PARTS.items():
            if part not in review['frames'][i].get('review_parts',[]):continue
            try:
                a,b,t=brackets(i,part);qa,qb=original[a],original[b];ba,bb=body_basis(qa),body_basis(qb);basis=body_basis(q)
                result=q.copy()
                for parent,child in ((root,middle),(middle,end)):
                    u=(qa[child]-qa[parent])@ba;v=(qb[child]-qb[parent])@bb;la,lb=np.linalg.norm(u),np.linalg.norm(v)
                    if min(la,lb)<1e-6 or not .65<=lb/la<=1.55:raise ValueError('reference_length_conflict')
                    result[child]=result[parent]+(direction(u,v,t)@basis.T)*((1-t)*la+t*lb)
                for child,anchor in [(j,end) for j in children]+list(AUXILIARY.get(part,{}).items()):
                    result[child]=result[anchor]+((1-t)*((qa[child]-qa[anchor])@ba)+t*((qb[child]-qb[anchor])@bb))@basis.T
                points=project(result[[middle,end]],camera)
                if np.any(points<0) or np.any(points>=[packet['video']['width'],packet['video']['height']]):raise ValueError('hypothesis_outside_image')
                observed=np.asarray(baseline['frames'][i]['image_joints'])[[middle,end]]
                bbox=packet['frames'][i]['person_bbox'];diagonal=np.linalg.norm(np.subtract(bbox[2:],bbox[:2]))
                if np.max(np.linalg.norm(points-observed,axis=1))>max(20.,diagonal*.12):raise ValueError('unsupported_image_displacement')
                q[editable_joints(part)]=result[editable_joints(part)];changed.append({'part':part,'variant':'two_sided_local_directions'})
                events.append({'frame_index':i,'part':part,'references':[a,b],'reference_span_seconds':(b-a)/fps,'hypothesis_only':True})
            except ValueError as error:events.append({'frame_index':i,'part':part,'rejected':str(error)})
        if changed or body_replaced:
            editable=set(j for item in changed for j in editable_joints(item['part']))
            if body_replaced:editable=set(range(70))
            indices=sorted(editable);p=np.asarray(rows[i]['image_joints']).copy();p[indices]=project(q[indices],camera)
            rows[i].update(world_joints=q.tolist(),image_joints=p.tolist(),changed_parts=changed,
                body_reference_hypothesis=body_replaced,provenance='unobserved_temporal_hypothesis_not_measurement')
    return rows,{'events':events,'changed_frames':[i for i in range(n) if rows[i]['world_joints']!=baseline['frames'][i]['world_joints']],
        'limits':['unflagged_references_are_not_verified_visible_anatomy','long_gaps_can_erase_true_actions',
                  'camera_relative_body_rotation_may_be_wrong','two_references_do_not_resolve_full_turn_winding',
                  'no_automatic_promotion_or_native_rotation_changes']}
