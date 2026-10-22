"""Mask geometry checks only: none of these checks proves person identity."""
import cv2
import numpy as np
from core.pose2d.motion import BodyMotion


class MaskPositionGuard:
    """Track a visible region, not anatomical joints or a verified identity."""
    def __init__(self,fps,width,height,start_index=0):
        self.start_index=start_index
        self.filter=BodyMotion(fps);self.width=width;self.height=height
        self.horizon=max(1,int(fps*.5));self.last_index=None;self.pending=None
        self.size=None;self.locked=False
        self.references=[];self.cut_started=None;self.fps=fps

    def evaluate(self,box,mask,index,reason,scene_cut=False,frame=None):
        if scene_cut:
            self.cut_started=index;self.pending=None
        predicted=None;residual=None;center=None;hist=None;appearance_distance=None
        if reason is None and frame is not None:
            hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
            hist=cv2.calcHist([hsv],[0,1,2],mask.astype(np.uint8),[12,8,8],[0,180,0,256,0,256])
            hist/=max(float(hist.sum()),1.)
            if self.references:appearance_distance=min(float(cv2.compareHist(hist,h,cv2.HISTCMP_BHATTACHARYYA)) for h in self.references)
        if self.filter.x is not None and self.cut_started is None:
            predicted=self.filter.predict()
            if index-self.last_index>self.horizon:self.locked=True
        elif self.cut_started is not None and index-self.cut_started>=self.horizon:self.locked=True
        if self.locked:reason='target_reselection_required'
        if reason is None:
            ys,xs=np.nonzero(mask)
            center=np.array([xs.mean(),ys.mean()])
            size=np.asarray(box[2:])-box[:2]
            if self.cut_started is not None:
                if appearance_distance is None or appearance_distance>.55:reason='scene_appearance_unconfirmed';self.pending=None
                elif self.pending is None or index!=self.pending[0]+1 or np.linalg.norm(center-self.pending[1])>max(np.linalg.norm(size),1.)*.65:
                    reason='scene_reconnection_pending';self.pending=(index,center)
                else:
                    # A cut invalidates old spatial velocity, even with matching visual memory.
                    self.filter=BodyMotion(self.fps);self.cut_started=None
            elif predicted is not None:
                scale=max(float(np.linalg.norm(self.size)),1.)
                residual=float(np.linalg.norm(center-predicted)/scale)
                # Do not let growing Kalman covariance permit an arbitrary new person.
                if residual>.65:reason='mask_motion_mismatch'
                elif index-self.last_index>2:
                    if self.pending is None or index!=self.pending[0]+1 or np.linalg.norm(center-self.pending[1])>scale*.25:
                        reason='mask_reconnection_pending';self.pending=(index,center)
            elif index!=self.start_index:
                self.locked=True;reason='target_reselection_required'
            if reason is None:
                proxy=np.r_[center-size/2,center+size/2]
                if self.filter.x is None:self.filter.initialize(proxy,None)
                else:self.filter.update(proxy,None)
                self.size=size;self.last_index=index;self.pending=None
                if hist is not None and (appearance_distance is None or appearance_distance>.08):
                    self.references.append(hist)
                    if len(self.references)>12:del self.references[1]
        if reason not in (None,'mask_reconnection_pending','scene_reconnection_pending'):self.pending=None
        predicted_box=None
        if predicted is not None and not self.locked:
            p=np.r_[predicted-self.size/2,predicted+self.size/2]
            p[[0,2]]=np.clip(p[[0,2]],0,self.width);p[[1,3]]=np.clip(p[[1,3]],0,self.height)
            if np.all(p[2:]>p[:2]):predicted_box=p.tolist()
        return reason,{'prediction_only':reason is not None and predicted_box is not None,
            'observation_kind':'mask_region','observed_center':None if reason or center is None else center.tolist(),
            'predicted_center':None if predicted_box is None else predicted.tolist(),
            'predicted_bbox':predicted_box,'residual_normalized':residual,
            'prediction_horizon_frames':self.horizon,'requires_reselection':self.locked,
            'appearance_distance':appearance_distance,'scene_reconnection_pending':self.cut_started is not None,
            'identity_verified':False}


class MaskTrack:
    def __init__(self, width, height, fps, *, motion_guard=False, start_index=0):
        if type(start_index) is not int or start_index<0:raise ValueError('Invalid mask tracking start frame.')
        self.width=width;self.height=height;self.fps=fps
        self.previous=None;self.missing=0;self.segment=0
        self.guard=MaskPositionGuard(fps,width,height,start_index) if motion_guard else None
        self.next_index=start_index

    def evaluate(self, logits, object_logit, index, *, scene_cut=False,frame=None):
        if self.guard and index!=self.next_index:raise ValueError('Mask tracking frames must be consecutive from the selected start.')
        a=np.asarray(logits,dtype=np.float32)
        if a.shape!=(self.height,self.width):raise ValueError('SAM 2 mask dimensions changed.')
        reason=None;box=None;area=0;dominance=0.;stability=0.;jump=None
        if not np.isfinite(a).all() or not np.isfinite(object_logit):reason='nonfinite_mask'
        else:
            mask=(a>0).astype(np.uint8)
            _,_,stats,_=cv2.connectedComponentsWithStats(mask,connectivity=8)
            areas=stats[1:,cv2.CC_STAT_AREA]
            area=int(areas.sum())
            if area:
                dominance=float(areas.max()/area)
                # Include detached visible limbs, not just the largest component.
                ys,xs=np.nonzero(mask)
                box=[int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1]
                stability=float(np.count_nonzero(a>1)/max(np.count_nonzero(a>-1),1))
            if object_logit<=0:reason='object_not_visible'
            elif area<max(32,self.width*self.height*.0001):reason='empty_or_tiny_mask'
            elif area>self.width*self.height*.85:reason='mask_covers_frame'
            elif dominance<.5:reason='fragmented_mask'
            elif stability<.5:reason='unstable_mask'
            elif self.previous is not None:
                previous_index,old,old_area=self.previous
                old=np.asarray(old);current=np.asarray(box)
                distance=float(np.linalg.norm((current[:2]+current[2:]-old[:2]-old[2:])/2))
                diagonal=max(float(np.linalg.norm(old[2:]-old[:2])),1.)
                jump=distance/diagonal/max(1,index-previous_index)
                ratio=area/old_area
                if self.guard is None and jump>.65:reason='mask_position_jump'
                elif not .15<=ratio<=6:reason='mask_area_jump'
        motion={'prediction_only':False,'observation_kind':'mask_region'}
        if self.guard:
            reason,motion=self.guard.evaluate(box,None if reason else a>0,index,reason,scene_cut,frame)
            self.next_index+=1
        if reason is None:
            if self.missing:
                self.segment+=1
            self.previous=(index,box,area);self.missing=0
        else:self.missing+=1
        return {'frame_index':index,'timestamp':index/self.fps,
            'roi':None if reason else padded_roi(box,self.width,self.height),
            'person_bbox':None if reason else box,
            'tracking':{'state':('lost' if motion.get('requires_reselection') else 'uncertain') if reason else 'tracked','reason':reason or 'mask_observed',
                        'track_id':1,'missing_frames':self.missing,'requires_reselection':motion.get('requires_reselection',self.missing/self.fps>.5)},
            'people_detected':0,'detector_diagnostics':{'mode':'no_per_frame_person_detector','people_count_observed':False},
            'skeleton_duplicates':[],'association_scores':[],
            'motion':motion,
            'tracking_segment':self.segment,
            'mask':{'area_pixels':area,'largest_component_fraction':dominance,'stability':stability,
                    'object_logit':float(object_logit) if np.isfinite(object_logit) else None,
                    'position_jump_normalized':jump,'identity_verified':False}}


def waiting_for_target(index,fps):
    """No observation or prediction exists before the selected target starts."""
    return {'frame_index':index,'timestamp':index/fps,'roi':None,'person_bbox':None,
        'tracking':{'state':'uninitialized','reason':'before_target_start','track_id':1,
                    'missing_frames':0,'requires_reselection':False},
        'people_detected':0,'detector_diagnostics':{'mode':'before_target_start','people_count_observed':False},
        'skeleton_duplicates':[],'association_scores':[],
        'motion':{'prediction_only':False,'observation_kind':None,'observed_center':None,
                  'predicted_center':None,'predicted_bbox':None},'tracking_segment':0,
        'mask':{'area_pixels':0,'largest_component_fraction':0.,'stability':0.,
                'object_logit':None,'position_jump_normalized':None,'identity_verified':False}}


def padded_roi(box,width,height):
    x1,y1,x2,y2=box;dx=(x2-x1)*.25;dy=(y2-y1)*.15
    return [max(0,x1-dx),max(0,y1-dy),min(width,x2+dx),min(height,y2+dy)]
