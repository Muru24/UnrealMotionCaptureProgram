"""Sequence-level leg hypotheses in a frozen body coordinate system."""
import numpy as np
from validation.sam2.shoe_leg_geometry import body_basis


def interpolate_references(world, trusted):
    """Interpolate only between supported anchors; no extrapolated certainty."""
    world=np.asarray(world,float);trusted=np.asarray(trusted,bool)
    if trusted.shape!=(len(world),2):raise ValueError('Invalid trust shape.')
    local=np.zeros((len(world),2,2,3));references=np.full_like(local,np.nan)
    for t,q in enumerate(world):
        basis=body_basis(q)
        for leg,(hip,knee,ankle) in enumerate(((9,11,13),(10,12,14))):
            local[t,leg]=(q[[knee,ankle]]-q[hip])@basis
    for leg in range(2):
        anchors=np.flatnonzero(trusted[:,leg])
        for left,right in zip(anchors[:-1],anchors[1:]):
            # Long unsupported gaps remain unknown.
            if right-left>16:continue
            for t in range(left,right+1):
                alpha=(t-left)/max(1,right-left)
                references[t,leg]=(1-alpha)*local[left,leg]+alpha*local[right,leg]
    return references


def select_path(pools,unary):
    """Variable-size DP, penalizing named-leg displacement and bend change."""
    if not pools or len(pools)!=len(unary):raise ValueError('Invalid pools.')
    costs=np.asarray(unary[0],float);parents=[]
    if not len(costs) or not np.isfinite(costs).all():raise ValueError('Invalid costs.')
    for t in range(1,len(pools)):
        previous=np.asarray(pools[t-1]);current=np.asarray(pools[t])
        # Arrays are hip-relative body-local [two legs,knee/ankle,xyz].
        delta=current[:,None]-previous[None,:]
        movement=np.mean(np.linalg.norm(delta,axis=-1),axis=(-1,-2))
        def bend(x):
            v=x[:,:,1];v=v/np.maximum(np.linalg.norm(v,axis=-1,keepdims=True),1e-8)
            k=x[:,:,0];b=k-v*np.sum(k*v,axis=-1,keepdims=True)
            return b/np.maximum(np.linalg.norm(b,axis=-1,keepdims=True),1e-8)
        a=bend(current);b=bend(previous)
        angle=np.mean(1-np.clip(np.sum(a[:,None]*b[None,:],axis=-1),-1,1),axis=-1)
        transition=4*movement+.3*angle
        total=transition+costs[None,:];back=np.argmin(total,axis=1)
        u=np.asarray(unary[t],float)
        if u.shape!=(len(current),) or not np.isfinite(u).all():raise ValueError('Invalid costs.')
        costs=u+total[np.arange(len(current)),back];parents.append(back)
    path=[int(np.argmin(costs))]
    for back in reversed(parents):path.append(int(back[path[-1]]))
    return list(reversed(path))


def local_legs(q):
    basis=body_basis(q)
    return np.array([(q[[k,a]]-q[h])@basis for h,k,a in ((9,11,13),(10,12,14))])
