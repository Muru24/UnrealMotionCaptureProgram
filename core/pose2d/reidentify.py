"""Conservative HSV/pose reference matching, not learned biometric ReID."""
import numpy as np
from .association import common_joints,skeleton_similarity
from .tracker import appearance,appearance_distance,box_iou


class TargetReferences:
    def __init__(self):
        self.gallery=[];self.pending=None;self.hits=0

    def remember(self,frame,box,pose):
        if common_joints(pose,pose) is None:return
        descriptor=appearance(frame,box)
        if self.gallery:
            last=self.gallery[-1]
            similarity=skeleton_similarity(last[2],pose)
            if appearance_distance(last[1],descriptor)<.05 and similarity is not None and similarity>.95:return
        self.gallery.append((box.copy(),descriptor,tuple(v.copy() for v in pose)))
        if len(self.gallery)>8:self.gallery.pop(1)

    def clear_pending(self):self.pending=None;self.hits=0

    def consider(self,frame,boxes,keypoints,last_box):
        diagnostics=[];candidates=[]
        if keypoints is None or not self.gallery:
            self.clear_pending();return None,{'reason':'insufficient_references_or_pose','candidates':[]}
        diagonal=max(float(np.linalg.norm(last_box[2:]-last_box[:2])),1.)
        for i,box in enumerate(boxes):
            pose=tuple(v[i] for v in keypoints)
            if common_joints(pose,pose) is None:continue
            descriptor=appearance(frame,box);best=None
            for reference,look,body in self.gallery:
                ratio=float(np.prod(box[2:]-box[:2])/np.prod(reference[2:]-reference[:2]))
                color=appearance_distance(descriptor,look);similarity=skeleton_similarity(body,pose)
                distance=float(np.linalg.norm((box[:2]+box[2:]-last_box[:2]-last_box[2:])/2))/diagonal
                if not .5<=ratio<=2 or color>.3 or similarity is None or similarity<.7 or distance>1.5:continue
                score=.6*(1-color)+.4*similarity
                if best is None or score>best:best=score
            if best is None:continue
            diagnostics.append({'candidate_index':i,'score':best})
            candidates.append((best,i,descriptor))
        candidates.sort(key=lambda r:r[0],reverse=True)
        if not candidates or (len(candidates)>1 and candidates[0][0]-candidates[1][0]<.18):
            self.clear_pending();return None,{'reason':'no_clear_reidentification','candidates':diagnostics}
        _,index,descriptor=candidates[0];box=boxes[index]
        for j,other in enumerate(boxes):
            if j==index:continue
            ratio=float(np.prod(other[2:]-other[:2])/np.prod(box[2:]-box[:2]))
            if .4<=ratio<=2.5 and box_iou(box,other)>.2:
                self.clear_pending();return None,{'reason':'overlapping_people','candidates':diagnostics}
        consistent=(self.pending is not None and box_iou(self.pending[0],box)>.35 and
                    appearance_distance(self.pending[1],descriptor)<.25)
        self.hits=self.hits+1 if consistent else 1
        self.pending=(box.copy(),descriptor)
        return (index if self.hits>=3 else None),{'reason':'confirmed' if self.hits>=3 else 'confirming',
            'candidate_index':index,'confirmations':self.hits,'candidates':diagnostics}
