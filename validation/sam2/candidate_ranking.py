"""Experimental consensus/continuity ranking; not an accuracy confidence score."""
import numpy as np
JOINTS=(5,6,7,8,41,62,9,10,11,12,13,14)
BONES=((5,7),(7,62),(6,8),(8,41),(9,11),(11,13),(10,12),(12,14))


def rank_candidates(world,image,reference_lengths,target_diagonals,torso_scale,switch_penalty=.03,extra_transition_cost=None,allowed_candidates=None):
    # Arrays are [time, candidate, joint, coordinate]. All candidates already
    # share image orientation and anatomical joint labels.
    xyz=np.asarray(world,float);pixels=np.asarray(image,float)
    n,c,j,d=xyz.shape
    if j!=70 or d!=3 or pixels.shape!=(n,c,70,2) or not np.isfinite(xyz).all() or not np.isfinite(pixels).all():raise ValueError('Invalid candidates.')
    if not np.isfinite(torso_scale) or torso_scale<=0:raise ValueError('Invalid common scale.')
    if np.shape(reference_lengths)!=(len(BONES),) or np.any(np.asarray(reference_lengths)<=0):raise ValueError('Invalid length references.')
    diagonals=np.asarray(target_diagonals,float)
    if diagonals.shape!=(n,) or not np.isfinite(diagonals).all() or np.any(diagonals<=0):raise ValueError('Invalid target scale.')
    root=(xyz[:,:,9]+xyz[:,:,10])/2
    relative=xyz-root[:,:,None,:]
    lengths=np.stack([np.linalg.norm(xyz[:,:,b]-xyz[:,:,a],axis=-1) for a,b in BONES],axis=-1)
    length_cost=np.mean(np.abs(np.log(np.maximum(lengths,1e-6)/np.asarray(reference_lengths))),axis=-1)
    consensus=np.median(pixels[:,:,JOINTS],axis=1)
    image_cost=np.mean(np.linalg.norm(pixels[:,:,JOINTS]-consensus[:,None],axis=-1),axis=-1)/diagonals[:,None]
    unary=.4*length_cost+.2*image_cost
    if allowed_candidates is not None:
        allowed=np.asarray(allowed_candidates,bool)
        if allowed.shape!=(n,c) or not allowed.any(axis=1).all():raise ValueError('Invalid candidate restrictions.')
        unary=np.where(allowed,unary,1e6)
    transitions=np.zeros((n,c,c))
    for t in range(1,n):
        for before in range(c):
            for after in range(c):
                motion=np.mean(np.linalg.norm(relative[t,after,JOINTS]-relative[t-1,before,JOINTS],axis=-1))/torso_scale
                transitions[t,before,after]=.4*min(float(motion),3)+switch_penalty*(before!=after)
    if extra_transition_cost is not None:
        extra=np.asarray(extra_transition_cost,float)
        if extra.shape!=(n,c,c) or not np.isfinite(extra).all() or np.any(extra<0):raise ValueError('Invalid observation transition costs.')
        transitions+=extra
    cost=unary[0].copy();back=np.zeros((n,c),int)
    for t in range(1,n):
        options=cost[:,None]+transitions[t]
        back[t]=np.argmin(options,axis=0)
        cost=unary[t]+np.min(options,axis=0)
    path=np.zeros(n,int);path[-1]=np.argmin(cost)
    for t in range(n-1,0,-1):path[t-1]=back[t,path[t]]
    fixed=[float(unary[:,k].sum()+transitions[1:,k,k].sum()) for k in range(c)]
    return {'path':path.tolist(),'path_cost':float(cost[path[-1]]),'fixed_sequence_costs':fixed,
            'length_cost':length_cost.tolist(),'consensus_cost':image_cost.tolist(),'unary':unary.tolist(),
            'limits':['not_ground_truth_or_probability','consensus_can_agree_on_wrong_pose',
                      'continuity_can_favor_wrong_smooth_motion','all_costs_use_model_predictions']}
