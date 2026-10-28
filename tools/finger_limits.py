"""Conservative reference-rig finger guards, not calibrated anatomical limits.

Quaternions are xyzw. Only finger-local rotation changes; translations and the
wrist/body pose are untouched. Thumb opposition keeps a broad swing cone.
"""
import math
from manny_leg_alignment import unit,dot,sub,scale,cross,rotate,transport

LIMITS={1:(-20.,100.,35.),2:(-10.,110.,12.),3:(-10.,90.,10.)}


def slerp(a,b,t):
    a=unit(a);b=unit(b);c=dot(a,b)
    if c<0:b=scale(b,-1);c=-c
    c=max(-1.,min(1.,c))
    if c>.9995:return unit(tuple((1-t)*x+t*y for x,y in zip(a,b)))
    theta=math.acos(c);den=math.sin(theta)
    return unit(tuple((math.sin((1-t)*theta)*x+math.sin(t*theta)*y)/den for x,y in zip(a,b)))


def constrain(q,curl,segment,thumb=False):
    if len(q)!=4 or not all(math.isfinite(x) for x in q) or dot(q,q)<1e-12:raise ValueError('Invalid finger quaternion.')
    if segment not in LIMITS:raise ValueError('Invalid finger segment.')
    q=unit(q);axis=(0.,1.,0.);d=rotate(q,axis);reasons=[]
    if thumb:
        angle=math.acos(max(-1.,min(1.,dot(d,axis))));limit=math.radians(115)
        if angle<=limit+1e-9:return q,reasons
        side=sub(d,scale(axis,dot(d,axis)))
        if dot(side,side)<1e-12:side=sub(curl,scale(axis,dot(curl,axis)))
        side=unit(side)
        desired=tuple(math.cos(limit)*a+math.sin(limit)*s for a,s in zip(axis,side));reasons.append('thumb_swing_cone')
    else:
        curl=unit(sub(curl,scale(axis,dot(curl,axis))));spread=unit(cross(curl,axis))
        flex=math.atan2(dot(d,curl),dot(d,axis));abduction=math.atan2(dot(d,spread),math.hypot(dot(d,axis),dot(d,curl)))
        lo,hi,width=map(math.radians,LIMITS[segment]);f=max(lo,min(hi,flex));a=max(-width,min(width,abduction))
        if abs(f-flex)>1e-9:reasons.append('flexion_range')
        if abs(a-abduction)>1e-9:reasons.append('sideways_range')
        if not reasons:return q,reasons
        desired=tuple(math.cos(a)*(math.cos(f)*y+math.sin(f)*c)+math.sin(a)*s for y,c,s in zip(axis,curl,spread))
    return transport(q,d,desired),reasons


def guard_rotation(q,curl,segment,fps,previous=None,thumb=False):
    if not math.isfinite(fps) or fps<=0:raise ValueError('Invalid finger fps.')
    result,reasons=constrain(q,curl,segment,thumb)
    if previous is not None:
        previous=unit(previous);angle=2*math.acos(min(1.,abs(dot(previous,result))))
        limit=math.radians(1080 if thumb else 720)/fps
        if angle>limit:
            result=slerp(previous,result,limit/angle);reasons.append('angular_speed')
            # Joint range takes precedence when the two priors conflict.
            result,extra=constrain(result,curl,segment,thumb);reasons.extend(extra)
    return unit(result),sorted(set(reasons))
