"""Conservative background similarity and camera-relative root observations, not SLAM."""
import math
import numpy as np


def background_step(previous,current,previous_box,current_box):
    import cv2
    h,w=previous.shape;mask=np.full((h,w),255,np.uint8)
    for box in (previous_box,current_box):
        if box is None:return None
        box=np.asarray(box,float)
        if box.shape!=(4,) or not np.isfinite(box).all():return None
        size=box[2:]-box[:2];a=np.floor(box[:2]-size*.12).astype(int);b=np.ceil(box[2:]+size*.12).astype(int)
        if np.any(size<=0):return None
        cv2.rectangle(mask,tuple(a),tuple(b),0,-1)
    points=cv2.goodFeaturesToTrack(previous,maxCorners=240,qualityLevel=.02,minDistance=8,mask=mask)
    if points is None or len(points)<16:return None
    after,status,_=cv2.calcOpticalFlowPyrLK(previous,current,points,None,winSize=(21,21),maxLevel=3)
    if after is None:return None
    back,reverse,_=cv2.calcOpticalFlowPyrLK(current,previous,after,None,winSize=(21,21),maxLevel=3)
    if back is None:return None
    good=status.ravel().astype(bool)&reverse.ravel().astype(bool)&(np.linalg.norm(back-points,axis=2).ravel()<.8)
    a=points[good,0];b=after[good,0]
    inside=np.isfinite(b).all(axis=1)&(b[:,0]>=0)&(b[:,0]<w)&(b[:,1]>=0)&(b[:,1]<h)
    a=a[inside];b=b[inside]
    if len(a)<16:return None
    transform,inliers=cv2.estimateAffinePartial2D(a,b,method=cv2.RANSAC,ransacReprojThreshold=1.2,maxIters=1000,confidence=.99)
    if transform is None or inliers is None:return None
    keep=inliers.ravel().astype(bool)
    if keep.sum()<16 or keep.mean()<.65:return None
    spread=np.ptp(a[keep],axis=0)
    if spread[0]<w*.18 or spread[1]<h*.18:return None
    error=np.linalg.norm((a[keep]@transform[:,:2].T+transform[:,2])-b[keep],axis=1)
    scale=math.sqrt(abs(np.linalg.det(transform[:,:2])));angle=math.atan2(transform[1,0],transform[0,0])
    if not np.isfinite(transform).all() or not .95<=scale<=1.05 or abs(angle)>math.radians(3) or np.median(error)>.65:return None
    if np.linalg.norm(transform[:,2])>max(w,h)*.12:return None
    if np.median(np.linalg.norm(b[keep]-a[keep],axis=1))<.02 and abs(scale-1)<.00005 and abs(angle)<.00003:
        transform=np.array([[1.,0.,0.],[0.,1.,0.]])
    result=np.eye(3);result[:2]=transform
    return result


def smooth_small_root_changes(values,fps):
    """Smooth millimeter-scale XY curvature without slowing linear translation."""
    result=values.copy();stride=max(1,round(fps/30))
    for i in range(stride,len(values)-stride):
        midpoint=(values[i-stride,:2]+values[i+stride,:2])*.5
        deviation=float(np.linalg.norm(midpoint-values[i,:2]))
        t=float(np.clip((deviation-.005)/.02,0,1));weight=.5*(1-t*t*(3-2*t))
        result[i,:2]=values[i,:2]*(1-weight)+midpoint*weight
    return result


def trajectory_hints(q,valid,feet,index,contacts,keys,video,observations,span_iterator):
    """Returns bounded root drive and airborne hypotheses with independent camera epochs."""
    n=len(q);drive=np.full((n,3),np.nan);air=np.zeros(n,bool);height=np.zeros(n);sliding=np.zeros((n,2),bool)
    if observations is None:return drive,air,height,sliding
    positions=np.asarray(observations['pelvis_camera_m'],float)
    foot_z=np.asarray(observations['feet_camera_z_m'],float);epochs=observations['epochs']
    foot_x=np.asarray(observations.get('feet_camera_x_m',np.full((n,4),np.nan)),float)
    if positions.shape!=(n,3) or foot_z.shape!=(n,4) or foot_x.shape!=(n,4) or len(epochs)!=n:raise ValueError('Invalid root observations.')
    observed=valid[:,index['pelvis']]&np.isfinite(positions).all(axis=1)&np.isfinite(foot_z).all(axis=1)
    root_keys=[(keys[i],epochs[i]) for i in range(n)];fps=float(video['fps'])
    for a,b in span_iterator(observed,root_keys):
        samples=positions[a:b].copy();fz=foot_z[a:b].copy();radius=max(1,round(.05*fps))
        for i in range(b-a):
            samples[i]=np.median(positions[max(a,a+i-radius):min(b,a+i+radius+1)],axis=0)
            fz[i]=np.median(foot_z[max(a,a+i-radius):min(b,a+i+radius+1)],axis=0)
        seed=contacts[a:b].all(axis=1)
        if seed.sum()<max(3,math.ceil(.1*fps)):continue
        floor=np.percentile(fz[seed],15,axis=0)
        grounded=seed&(np.max(fz-floor,axis=1)<.06)
        if grounded.sum()<3:continue
        baseline=np.median(samples[grounded],axis=0)
        drive[a:b]=smooth_small_root_changes(samples-baseline,fps)
        for side in range(2):
            fx=foot_x[a:b,[side,side+2]].mean(axis=1)
            if not np.isfinite(fx).all() or b-a<3:continue
            smoothed=np.array([np.median(fx[max(0,i-radius):min(b-a,i+radius+1)]) for i in range(b-a)])
            speed=np.abs(np.gradient(smoothed))*fps
            near=np.max(np.abs(fz[:,[side,side+2]]-floor[[side,side+2]]),axis=1)<.07
            sliding[a:b,side]=near&(speed>.6)
        # All four projected ankle/toe points must rise; one raised kicking leg is insufficient.
        leg_valid=valid[a:b,[j for side in feet for j in side]].all(axis=1)
        candidate=leg_valid&(np.min(fz-floor,axis=1)>.055)&(samples[:,2]-baseline[2]>.06)
        for c,d in span_iterator(candidate,root_keys[a:b]):
            if d-c<max(2,math.ceil(.06*fps)):continue
            air[a+c:a+d]=True
            # Ankle reference is above the floor by 7 cm; preserve the reference-rig scale.
            height[a+c:a+d]=samples[c:d,2]-float(np.mean(floor[:2]))+.07-q[a+c:a+d,index['pelvis'],2]
    return drive,air,height,sliding
