"""Quaternion-only temporal filtering and conservative grip wrist limits."""
import math
from mathutils import Quaternion


def smooth_quaternions(values,fps,seconds=.07,speed=300):
    radius=max(1,math.ceil(3*seconds*fps));result=[]
    for i,reference in enumerate(values):
        total=[0.,0.,0.,0.]
        for j in range(max(0,i-radius),min(len(values),i+radius+1)):
            q=values[j];weight=math.exp(-.5*((j-i)/(fps*seconds))**2)
            if reference.dot(q)<0:weight=-weight
            for k in range(4):total[k]+=q[k]*weight
        result.append(Quaternion(total).normalized())
    for order in [range(1,len(result)),range(len(result)-2,-1,-1)]:
        previous=None
        for i in order:
            p=result[i-1] if order.step>0 else result[i+1];q=result[i]
            if p.dot(q)<0:q=-q
            angle=p.rotation_difference(q).angle;angle=min(angle,2*math.pi-angle)
            result[i]=p.slerp(q,min(1,math.radians(speed)/fps/max(angle,1e-8)))
    return result


def limit_wrist(q,swing_degrees=40,twist_degrees=50):
    swing,twist=q.normalized().to_swing_twist('Y')
    angle=swing.angle
    if angle>math.pi:swing=-swing;angle=swing.angle
    if angle>math.radians(swing_degrees):swing=Quaternion().slerp(swing,math.radians(swing_degrees)/angle)
    twist=max(-math.radians(twist_degrees),min(math.radians(twist_degrees),twist))
    return (swing@Quaternion((0,1,0),twist)).normalized()
