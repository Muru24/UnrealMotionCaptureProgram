"""Conservative input crop envelope; never changes a mask or target decision."""
import math
import numpy as np


class RoiEnvelope:
    def __init__(self, fps, tau_seconds=.12, max_area_ratio=1.8):
        if not np.isfinite(fps) or fps<=0:raise ValueError('Invalid ROI fps.')
        if not np.isfinite(tau_seconds) or tau_seconds<=0:raise ValueError('Invalid ROI time constant.')
        if not np.isfinite(max_area_ratio) or max_area_ratio<1:raise ValueError('Invalid ROI area limit.')
        self.alpha=1-math.exp(-1/(fps*tau_seconds))
        self.max_area_ratio=max_area_ratio
        self.previous=None

    def update(self,row):
        result=dict(row)
        target=row['roi']
        result['roi_observation']=None if target is None else list(target)
        if target is None:
            self.previous=None
            result['roi_stabilization']={'method':'expand_immediately_contract_exponentially','reset':'not_observed'}
            return result
        target=np.asarray(target,dtype=float)
        observed=np.asarray(row['person_bbox'],dtype=float)
        if target.shape!=(4,) or observed.shape!=(4,) or not np.isfinite(np.r_[target,observed]).all():
            raise ValueError('Invalid observed ROI.')
        if np.any(target[2:]<=target[:2]) or np.any(observed[2:]<=observed[:2]):raise ValueError('Empty observed ROI.')
        index=row['frame_index'];segment=row.get('tracking_segment',0)
        filtered=target.copy();reason='initial'
        if self.previous is not None:
            last_index,last_segment,old_roi,old_box=self.previous
            distance=float(np.linalg.norm((observed[:2]+observed[2:]-old_box[:2]-old_box[2:])/2))
            diagonal=max(float(np.linalg.norm(old_box[2:]-old_box[:2])),1.)
            if index!=last_index+1:reason='frame_gap'
            elif segment!=last_segment:reason='segment_boundary'
            elif distance/diagonal>.35:reason='abrupt_geometry'
            else:
                eased=old_roi+self.alpha*(target-old_roi)
                filtered=np.r_[np.minimum(target[:2],eased[:2]),np.maximum(target[2:],eased[2:])]
                ratio=float(np.prod(filtered[2:]-filtered[:2])/np.prod(target[2:]-target[:2]))
                if ratio>self.max_area_ratio:filtered=target.copy();reason='area_limit'
                else:reason=None
        ratio=float(np.prod(filtered[2:]-filtered[:2])/np.prod(target[2:]-target[:2]))
        self.previous=(index,segment,filtered.copy(),observed.copy())
        result['roi']=filtered.tolist()
        result['roi_stabilization']={'method':'expand_immediately_contract_exponentially',
            'reset':reason,'area_ratio_to_observed_roi':ratio,'alpha':self.alpha}
        return result
