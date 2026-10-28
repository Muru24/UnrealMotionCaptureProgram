"""Hand ROI geometry and candidate association, independent of inference backend."""
import numpy as np


def hand_roi(points,chains,side,width,height):
    q=np.asarray(points,float)
    if q.shape!=(70,2):return None
    wrist=chains[side][0][0];elbow=7 if side=='left' else 8
    anchor=q[wrist]
    if not np.isfinite(anchor).all() or not (0<=anchor[0]<width and 0<=anchor[1]<height):return None
    ids=[chain[1] for chain in chains[side]];p=q[ids];p=p[np.isfinite(p).all(axis=1)]
    p=p[(np.linalg.norm(p-anchor,axis=1)<max(width,height)*.2)]
    center=(anchor+p.mean(axis=0))/2 if len(p) else anchor
    span=float(np.max(np.linalg.norm(p-anchor,axis=1))) if len(p) else 0.
    forearm=float(np.linalg.norm(anchor-q[elbow])) if np.isfinite(q[elbow]).all() else 0.
    size=min(max(width,height)*.5,max(96.,span*3.,forearm*.65))
    x0,y0=np.maximum(0,np.floor(center-size/2)).astype(int);x1,y1=np.minimum([width,height],np.ceil(center+size/2)).astype(int)
    if x1-x0<24 or y1-y0<24:return None
    return [int(x0),int(y0),int(x1),int(y1)]


def associate_hand(candidates,anchor,roi):
    """Use wrist proximity, not handedness probability as landmark confidence."""
    x0,y0,x1,y1=roi;scale=max(x1-x0,y1-y0);best=None;cost=float('inf')
    for candidate in candidates:
        q=np.asarray(candidate['image_joints'],float);world=np.asarray(candidate['world_joints'],float)
        if q.shape!=(21,2) or world.shape!=(21,3) or not np.isfinite(q).all() or not np.isfinite(world).all():continue
        distance=float(np.linalg.norm(q[0]-anchor))/scale
        palm=np.linalg.norm(q[9]-q[0]);width=np.linalg.norm(q[5]-q[17])
        if distance>.3 or palm<5 or width<3:continue
        if (q[:,0]<x0-.05*scale).any() or (q[:,0]>x1+.05*scale).any() or (q[:,1]<y0-.05*scale).any() or (q[:,1]>y1+.05*scale).any():continue
        if distance<cost:cost=distance;best={**candidate,'wrist_distance_roi_fraction':distance}
    return best


def insert_hand(points,chains,side,candidate):
    out=np.asarray(points,float).copy();out[chains[side][0][0]]=candidate['image_joints'][0]
    for f,chain in enumerate(chains[side]):
        for j,target in enumerate(chain[1:]):out[target]=candidate['image_joints'][1+f*4+j]
    return out
