"""Offline limb handover to checked model observations, never ground truth."""
import copy
import numpy as np
from core.pose3d.part_reestimation import PARTS,AUXILIARY,editable_joints,key
from core.pose3d.manual_leg_geometry import fit_camera,project


def reconnect(packet,review,parts,support=lambda i,p:0.,cancelled=lambda:False):
    frames=packet['frames'];n=len(frames);rows=copy.deepcopy(parts['frames']);events=[]
    if len(rows)!=n or len(review['frames'])!=n:raise ValueError('Reconnection timeline differs.')
    if any(r['frame_index']!=i or frames[i]['frame_index']!=i or review['frames'][i]['frame_index']!=i for i,r in enumerate(rows)):
        raise ValueError('Reconnection frame order differs.')
    original=parts['frames'];window=max(2,min(5,round(packet['video']['fps']*.1)))
    for row in rows:row['reconnected_parts']=[]
    def changed(i,part):return any(c['part']==part for c in original[i]['changed_parts'])
    for part,(root,middle,end,children) in PARTS.items():
        for start in range(1,n):
            if cancelled():raise KeyboardInterrupt
            if not changed(start-1,part) or changed(start,part):continue
            event={'part':part,'start':start,'accepted':False};events.append(event)
            count=min(window,n-start)
            if count<2:event['reason']='insufficient_observations';continue
            indices=range(start,start+count)
            if any(key(review['frames'][i])!=key(review['frames'][start-1]) or original[i]['world_joints'] is None for i in indices):
                event['reason']='track_boundary_or_missing_body';continue
            if any(changed(i,part) or part in review['frames'][i].get('review_parts',[]) for i in indices):
                event['reason']='observations_still_under_review';continue
            previous=np.asarray(original[start-1]['world_joints'],float);proposals=[]
            try:
                for t,i in enumerate(indices):
                    q=np.asarray(original[i]['world_joints'],float);p=np.asarray(original[i]['image_joints'],float)
                    if q.shape!=(70,3) or p.shape!=(70,2) or not np.isfinite(q).all() or not np.isfinite(p).all():raise ValueError('invalid_pose')
                    scale=max(np.linalg.norm((q[5]+q[6]-q[9]-q[10])/2),1e-6)
                    local=q[[middle,end]]-q[root];prior=previous[[middle,end]]-previous[root]
                    if np.mean(np.linalg.norm(local-prior,axis=1))/scale>.45:raise ValueError('reappearance_position_conflict')
                    camera=fit_camera(q,p,packet['video']['width'],packet['video']['height'])
                    result=q.copy();alpha=(t+1)/count
                    for a,b in ((root,middle),(middle,end)):
                        u=previous[b]-previous[a];v=q[b]-q[a];lu=np.linalg.norm(u);lv=np.linalg.norm(v)
                        if min(lu,lv)<1e-6 or not .75<=lv/lu<=1.33:raise ValueError('bone_length_conflict')
                        u=u/lu;v=v/lv
                        if np.dot(u,v)<0:raise ValueError('opposing_bone_directions')
                        direction=(1-alpha)*u+alpha*v;direction/=np.linalg.norm(direction)
                        result[b]=result[a]+direction*lv
                    for child in children:result[child]=result[end]+q[child]-q[end]
                    for child,anchor in AUXILIARY.get(part,{}).items():result[child]=result[anchor]+q[child]-q[anchor]
                    editable=editable_joints(part);pixels=p.copy();pixels[editable]=project(result[editable],camera)
                    endpoints=pixels[[middle,end]]
                    if np.any(endpoints<0) or np.any(endpoints>=[packet['video']['width'],packet['video']['height']]):raise ValueError('outside_frame')
                    if support(i,p[[middle,end]])>.5 or support(i,endpoints)>.5:raise ValueError('mask_support_conflict')
                    if np.max(np.linalg.norm(endpoints-p[[middle,end]],axis=1))>20:raise ValueError('image_displacement_conflict')
                    proposals.append((i,result,pixels,alpha))
                # Commit the complete checked transition, never a partial rejected path.
                for i,q,p,alpha in proposals:
                    if alpha==1:continue
                    editable=editable_joints(part)
                    for field,value in (('world_joints',q),('image_joints',p)):
                        a=np.asarray(rows[i][field]);a[editable]=value[editable];rows[i][field]=a.tolist()
                    rows[i]['reconnected_parts'].append({'part':part,'observation_weight':alpha})
                    rows[i]['provenance']='checked_model_reconnection'
                event.update(accepted=True,end_exclusive=start+count,reason='checked_model_observations')
            except ValueError as error:event['reason']=str(error)
    return rows,{'events':events,'changed_frames':[r['frame_index'] for r in rows if r['reconnected_parts']],
        'limits':['model_observations_are_not_ground_truth','mask_inside_does_not_prove_anatomy',
                  'no_missing_body_fill','no_native_rotations_replaced','shared_clothing_errors_can_pass_checks']}
