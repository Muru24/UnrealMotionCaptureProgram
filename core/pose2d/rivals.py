"""Short-lived other-person positions; appearance is frozen during target loss."""
import numpy as np


def head_center(keypoints):
    if keypoints is None:return None
    coords,scores=keypoints
    coords=np.asarray(coords)[:5];scores=np.asarray(scores)[:5]
    valid=(scores>.5)&np.isfinite(coords).all(axis=1)
    return coords[valid].mean(axis=0) if valid.sum()>=3 else None


class OtherPeople:
    def __init__(self,fps):
        self.frame=-1;self.ttl=max(1,round(fps));self.references=[]

    def advance(self):
        self.frame+=1
        self.references=[r for r in self.references if self.frame-r['frame']<=self.ttl]

    def observe(self,frame,boxes,selected,allow_follow=True,keypoints=None):
        if selected is None:
            if allow_follow:self._follow(frame,boxes)
            return
        from .tracker import appearance,appearance_distance,box_iou
        selected=np.asarray(selected)
        selected_area=float(np.prod(selected[2:]-selected[:2]))
        others=[b for b in boxes if box_iou(b,selected)<.15 and .25<=float(np.prod(b[2:]-b[:2]))/selected_area<=4]
        for index,box in enumerate(others):
            # Duplicate/overlapping observations cannot seed independent people.
            if any(j!=index and box_iou(box,b)>.2 for j,b in enumerate(others)):continue
            descriptor=appearance(frame,box)
            indices=[i for i,b in enumerate(boxes) if np.array_equal(b,box)]
            head=head_center(tuple(v[indices[0]] for v in keypoints)) if keypoints is not None and len(indices)==1 else None
            matches=[r for r in self.references if box_iou(r['box'],box)>.65 and
                     appearance_distance(r['look'],descriptor)<.25]
            if len(matches)>1:continue
            if matches:
                reference=matches[0];reference.update(box=box.copy(),look=descriptor,frame=self.frame,head=head)
            elif len(self.references)<4:
                self.references.append({'box':box.copy(),'look':descriptor,'frame':self.frame,'head':head})

    def _follow(self,frame,boxes):
        from .tracker import appearance,appearance_distance,box_iou
        # No new people or appearance learning: only confirm a known person's
        # nearby, unambiguous position twice before refreshing that position.
        proposals=[]
        for reference in self.references:
            old=reference['box'];diagonal=max(float(np.linalg.norm(old[2:]-old[:2])),1.)
            matches=[]
            for i,box in enumerate(boxes):
                ratio=float(np.prod(box[2:]-box[:2])/np.prod(old[2:]-old[:2]))
                distance=float(np.linalg.norm((box[:2]+box[2:]-old[:2]-old[2:])/2))/diagonal
                if not (.5<=ratio<=2 and box_iou(old,box)>.35 and distance<.2):continue
                if appearance_distance(appearance(frame,box),reference['look'])>=.3:continue
                if any(j!=i and box_iou(box,b)>.2 for j,b in enumerate(boxes)):continue
                matches.append(i)
            if len(matches)==1:proposals.append((reference,matches[0]))
            else:reference.pop('pending',None)
        for reference,index in proposals:
            if sum(i==index for _,i in proposals)>1:
                reference.pop('pending',None);continue
            box=boxes[index];pending=reference.get('pending')
            hits=pending[2]+1 if pending is not None and pending[0]==self.frame-1 and box_iou(pending[1],box)>.5 else 1
            reference['pending']=(self.frame,box.copy(),hits)
            if hits>=2:reference.update(box=box.copy(),frame=self.frame)

    def check(self,box,descriptor,target_box,target_appearance_distance,keypoints=None,target_keypoints=None):
        from .tracker import appearance_distance,box_iou
        def similarity(reference,color):
            diagonal=max(float(np.linalg.norm(reference[2:]-reference[:2])),1.)
            distance=float(np.linalg.norm((reference[:2]+reference[2:]-box[:2]-box[2:])/2))/diagonal
            overlap=box_iou(reference,box)
            return .55*overlap+.25*max(0.,1-distance/.3)+.2*(1-color),overlap,distance
        target_score,_,_=similarity(target_box,target_appearance_distance)
        for reference in self.references:
            old=reference['box'];ratio=float(np.prod(box[2:]-box[:2])/np.prod(old[2:]-old[:2]))
            color=appearance_distance(descriptor,reference['look'])
            rival_score,overlap,distance=similarity(old,color)
            head=head_center(keypoints);target_head=head_center(target_keypoints)
            other_head=reference.get('head')
            diagonal=max(float(np.linalg.norm(old[2:]-old[:2])),1.)
            if head is not None and target_head is not None and other_head is not None:
                other_distance=float(np.linalg.norm(head-other_head))/diagonal
                target_distance=float(np.linalg.norm(head-target_head))/diagonal
                if (.5<=ratio<=2 and color<.55 and other_distance<.15 and
                        target_distance>2*other_distance+.1):
                    return {'rejected':True,'reason':'matches_recent_other_person',
                            'evidence':'confident_head_position',
                            'other_head_distance':other_distance,'target_head_distance':target_distance,
                            'reference_age_frames':self.frame-reference['frame']}
            if (.7<=ratio<=1.4 and overlap>.65 and distance<.15 and color<.25 and
                    rival_score>=.8 and rival_score>target_score+.15):
                return {'rejected':True,'reason':'matches_recent_other_person','rival_score':rival_score,
                        'target_score':target_score,'reference_box':old.tolist(),
                        'reference_age_frames':self.frame-reference['frame']}
        return {'rejected':False}
