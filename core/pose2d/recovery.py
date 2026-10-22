"""Bounded regional person re-detection; all results still pass the tracker."""
import numpy as np
from .tracker import box_iou


def recover_candidates(frame,tracker,backend,boxes,keypoints):
    diagnostic={'attempted':False,'added':0}
    if (not hasattr(backend,'detect_region') or tracker.motion is None or tracker.box is None or
            tracker.latched or tracker.gap_ambiguous or tracker.missing>tracker.max_missing):
        return boxes,keypoints,diagnostic
    if len(boxes) and tracker.missing==0:return boxes,keypoints,diagnostic
    motion=tracker.motion
    predicted=motion.x[:2]+motion.x[2:]*motion.dt-motion.box_offset
    uncertainty=np.sqrt(np.maximum(np.diag(motion.P)[:2],0))
    half=(tracker.box[2:]-tracker.box[:2])*.65+2*uncertainty
    h,w=frame.shape[:2]
    region=np.r_[np.floor(predicted-half),np.ceil(predicted+half)]
    region[[0,2]]=region[[0,2]].clip(0,w)
    region[[1,3]]=region[[1,3]].clip(0,h)
    region=region.astype(int)
    size=region[2:]-region[:2]
    if min(size)<32 or np.prod(size)>=w*h*.9:return boxes,keypoints,diagnostic
    found,pose=backend.detect_region(frame,region)
    diagnostic.update(attempted=True,region=region.tolist(),detected=len(found))
    # Never replace a full-frame detection with an alternate crop hypothesis.
    kept=[]
    for i,box in enumerate(found):
        if any(box_iou(box,other)>.5 for other in boxes):continue
        kept.append(i)
    diagnostic['added']=len(kept)
    if not kept:return boxes,keypoints,diagnostic
    if keypoints is None:
        if len(boxes):return boxes,keypoints,dict(diagnostic,added=0,reason='no_full_frame_keypoints')
        keypoints=(np.empty((0,17,2)),np.empty((0,17)))
    return (np.concatenate((boxes,found[kept])),
            tuple(np.concatenate((a,b[kept])) for a,b in zip(keypoints,pose)),diagnostic)
