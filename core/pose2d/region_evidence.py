"""Retain bounded accessory observations without changing person tracking."""
import cv2,numpy as np


def reconcile(mask,person,logit,previous=None):
    mask=np.asarray(mask,bool);person=np.asarray(person,bool)
    if mask.ndim!=2 or person.shape!=mask.shape:raise ValueError('Region dimensions differ.')
    kept=np.zeros_like(mask);reasons=[];parent=int(person.sum())
    if not np.isfinite(logit) or logit<=0 or parent<16:
        return kept,{'weight':0.,'reason':'missing_region_or_person','outside_pixels_retained':0}
    # Require an attachment to the actual person, not just proximity to its box.
    count,labels,stats,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8),8)
    for label in range(1,count):
        component=labels==label;area=int(stats[label,cv2.CC_STAT_AREA]);overlap=int((component&person).sum())
        if area>=16 and overlap/max(area,1)>=.1 and area<=parent*1.5:kept|=component
    area=int(kept.sum());inside=int((kept&person).sum())
    weight=.5 if area else 0.
    if area and inside/area<.8:weight*=.5;reasons.append('parent_disagreement')
    if inside/max(parent,1)>.65:weight*=.3;reasons.append('possible_body_occlusion')
    if previous is not None:
        previous=np.asarray(previous,bool)
        if previous.shape!=mask.shape:raise ValueError('Previous region dimensions differ.')
        old=int(previous.sum());intersection=int((kept&previous).sum());union=int((kept|previous).sum())
        if not old or not .25<=area/old<=4 or intersection/max(union,1)<.05:
            weight=0.;reasons.append('temporal_confirmation_missing')
    else:weight=0.;reasons.append('temporal_confirmation_missing')
    return kept,{'weight':weight,'reason':','.join(reasons) or 'prompted_region_unverified',
        'outside_pixels_retained':int((kept&~person).sum()),'semantic_verified':False,'hard_exclusion':False}


def soft_cost(points,regions):
    points=np.asarray(points,float)
    if points.ndim!=2 or points.shape[1]!=2 or not np.isfinite(points).all():raise ValueError('Invalid image points.')
    values=[]
    for x,y in points:
        value=0.
        for mask,info in regions.values():
            h,w=mask.shape
            if 0<=x<w and 0<=y<h and mask[min(h-1,round(y)),min(w-1,round(x))]:value=max(value,float(info['weight']))
        values.append(value)
    return .2*float(np.mean(values)) if values else 0.
