"""Guard prompted internal regions; diagnostic masks are not anatomy labels."""
import numpy as np


def validate_prompts(objects,width,height):
    if not 1<=len(objects)<=4:raise ValueError('Expected one to four prompted regions.')
    names=set()
    for obj in objects:
        name=obj['name'];points=np.asarray(obj['points'],float);labels=np.asarray(obj['labels'])
        if not isinstance(name,str) or not name.isascii() or not name.replace('_','').isalnum() or name in names:raise ValueError('Invalid region name.')
        names.add(name)
        if points.ndim!=2 or points.shape[1]!=2 or not 1<=len(points)<=32 or labels.shape!=(len(points),) or not np.isfinite(points).all():raise ValueError('Invalid region points.')
        if np.any(points<0) or np.any(points>=[width,height]) or not np.isin(labels,[0,1]).all() or not np.any(labels==1):raise ValueError('Invalid region labels or bounds.')


def assess_region(mask,person,object_logit,previous=None):
    mask=np.asarray(mask,bool);person=np.asarray(person,bool)
    if mask.ndim!=2 or mask.shape!=person.shape:raise ValueError('Region/person dimensions differ.')
    raw=int(mask.sum());inside=mask&person;area=int(inside.sum());parent=int(person.sum())
    reasons=[]
    if not np.isfinite(object_logit) or object_logit<=0:reasons.append('object_not_present')
    if parent==0:reasons.append('person_unavailable')
    if area<16:reasons.append('region_too_small')
    if area/max(parent,1)>.65:reasons.append('region_covers_most_of_person')
    if (raw-area)/max(raw,1)>.2:reasons.append('region_leaks_outside_person')
    if previous is not None:
        previous=np.asarray(previous,bool)
        if previous.shape!=mask.shape:raise ValueError('Previous region dimensions differ.')
        old=int(previous.sum())
        if old and not .25<=area/old<=4:reasons.append('abrupt_region_area_change')
    return inside,{'status':'review' if reasons else 'prompted_region_unverified','reasons':reasons,
        'raw_pixels':raw,'inside_pixels':area,'person_pixels':parent,'inside_person_fraction':area/max(parent,1),
        'outside_person_fraction':(raw-area)/max(raw,1),'object_presence_logit':float(object_logit) if np.isfinite(object_logit) else None,
        'semantic_label_verified':False,'use_for_pose_exclusion':False}


def joint_region_evidence(points,regions):
    """Overlap is a review hint; an occluded real joint can also overlap clothing."""
    points=np.asarray(points,float)
    if points.shape!=(70,2) or not np.isfinite(points).all():raise ValueError('Expected finite MHR70 image joints.')
    result=[]
    for j,(x,y) in enumerate(points):
        hits=[]
        for name,(mask,info) in regions.items():
            h,w=mask.shape
            if info['status']=='prompted_region_unverified' and 0<=x<w and 0<=y<h and mask[min(h-1,round(y)),min(w-1,round(x))]:hits.append(name)
        if hits:result.append({'joint_index':j,'regions':hits,'action':'review_only','anatomical_error_confirmed':False})
    return result
