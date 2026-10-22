"""Confidence-gated COCO17 association; no claim of biometric identity."""
import numpy as np

WEIGHTS={'iou':.25,'center':.25,'skeleton':.30,'appearance':.20}
TORSO=(5,6,11,12)


def common_joints(first,second):
    if first is None or second is None:return None
    a,sa=first;b,sb=second
    mask=(sa>=.5)&(sb>=.5)&np.isfinite(sa)&np.isfinite(sb)&np.isfinite(a).all(axis=1)&np.isfinite(b).all(axis=1)
    for points in (a,b):
        torso=[j for j in TORSO if mask[j]]
        if len(torso)<3:return None
        scale=max(float(np.linalg.norm(np.ptp(points[torso],axis=0))),1.)
        for parent,child in ((5,7),(7,9),(6,8),(8,10),(11,13),(13,15),(12,14),(14,16)):
            if not mask[parent] or not .05*scale<=np.linalg.norm(points[child]-points[parent])<=2.5*scale:
                mask[child]=False
    if mask.sum()<6 or mask[list(TORSO)].sum()<3:return None
    return a,b,mask


def skeleton_similarity(first,second):
    common=common_joints(first,second)
    if common is None:return None
    a,b,mask=common
    torso=[j for j in TORSO if mask[j]]
    ca,cb=a[torso].mean(axis=0),b[torso].mean(axis=0)
    scale_a=np.linalg.norm(a[torso]-ca,axis=1).mean()
    scale_b=np.linalg.norm(b[torso]-cb,axis=1).mean()
    if min(scale_a,scale_b)<4:return None
    delta=np.linalg.norm((a[mask]-ca)/scale_a-(b[mask]-cb)/scale_b,axis=1)
    return float(np.exp(-np.median(delta)/.6))


def tracking_score(iou,distance,skeleton,appearance):
    components={'iou':float(np.clip(iou,0,1)),
                'center':float(np.clip(1-distance/.65,0,1)),
                'skeleton':skeleton,'appearance':float(np.clip(appearance,0,1))}
    weights={k:v for k,v in WEIGHTS.items() if components[k] is not None}
    total=sum(weights.values());weights={k:v/total for k,v in weights.items()}
    return sum(components[k]*v for k,v in weights.items()),components,weights


def collapse_same_skeleton(boxes,keypoints,enabled=True):
    """Merge only strongly coincident image-space joints of duplicate boxes."""
    if keypoints is None or not enabled:return boxes,keypoints,[]
    from .tracker import box_iou
    coords,scores=keypoints;kept=[];suppressed=[]
    for index in sorted(range(len(boxes)),key=lambda i:float(np.prod(boxes[i,2:]-boxes[i,:2])),reverse=True):
        duplicate=None
        for other in kept:
            if box_iou(boxes[index],boxes[other])<.25:continue
            common=common_joints((coords[index],scores[index]),(coords[other],scores[other]))
            if common is None:continue
            a,b,mask=common;scale=max(boxes[index,3]-boxes[index,1],boxes[other,3]-boxes[other,1],1)
            delta=np.linalg.norm(a[mask]-b[mask],axis=1)/scale
            if np.median(delta)<.04 and np.quantile(delta,.75)<.06:
                duplicate=other;break
        if duplicate is None:kept.append(index)
        else:suppressed.append({'raw_index':index,'kept_raw_index':duplicate,'reason':'coincident_body_keypoints'})
    kept.sort()
    return boxes[kept],(coords[kept],scores[kept]),suppressed
