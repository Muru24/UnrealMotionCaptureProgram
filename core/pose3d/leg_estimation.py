"""Shoe-supported model knee hypotheses attached to a frozen upper body."""
import itertools,numpy as np
from core.pose3d.manual_leg_geometry import fit_camera,body_basis,anchor_in_mask,project,solve_leg
from core.pose3d.shoe_evidence import mask_distance

def propose(base_world,base_image,leg_world,leg_image,masks,lengths,width=720,height=1280):
    q=np.asarray(base_world,float);p=np.asarray(base_image,float);cq=np.asarray(leg_world,float);cp=np.asarray(leg_image,float)
    camera=fit_camera(q,p,width,height);basis=body_basis(q);candidate_basis=body_basis(cq);proposals=[]
    if not masks:return [],[{'reason':'no_shoe_observation'}]
    failures=[]
    for assignment in itertools.permutations((13,14),len(masks)):
        result=q.copy();legs=[];cost=0.;reason=None
        for mask,a in zip(masks,assignment):
            h,k=(9,11) if a==13 else (10,12)
            # An alternative model ankle must itself be supported by the shoe.
            if mask_distance(mask,cp[a])>25:reason='alternative_ankle_outside_shoe';break
            target=anchor_in_mask(mask,p[h],.40307589404735333)
            rk=q[h]+basis@((cq[k]-cq[h])@candidate_basis)
            ra=q[h]+basis@((cq[a]-cq[h])@candidate_basis)
            fit=solve_leg(q[h],q[k],q[a],target,camera,*lengths[a],rk,ra,knee_target=cp[k])
            if fit is None:reason='unreachable_shoe_ray_with_fixed_hip_and_lengths';break
            if fit['knee_error_pixels']>20:reason='knee_projection_residual_over20_pixels';break
            result[k]=fit['knee'];result[a]=fit['ankle'];tips=[15,16,17] if a==13 else [18,19,20]
            result[tips]+=result[a]-q[a];cost+=fit['cost']
            legs.append({'hip':h,'knee':k,'ankle':a,'knee_error_pixels':fit['knee_error_pixels'],'ankle_error_pixels':fit['projection_error'],
                         'knee_source':'alternative_model_not_independent_observation','shoe_target':target.tolist()})
        if reason:failures.append({'assignment':list(assignment),'reason':reason});continue
        modified=np.flatnonzero(np.any(result!=q,axis=1));xy=p.copy();xy[modified]=project(result[modified],camera)
        fixed=[j for j in range(70) if j not in range(11,21)];np.testing.assert_array_equal(result[fixed],q[fixed])
        proposals.append({'world_joints':result,'image_joints':xy,'legs':legs,'cost':float(cost),'assignment':list(assignment)})
    return proposals,failures
