"""Mesh-sized deformation helpers; motion joints remain unchanged."""
import json,math
import numpy as np
import bpy
from mathutils import Quaternion,Vector


def helper_count(length,radius):
    if length<=0 or radius<=0:return 0
    ratio=length/radius
    return 3 if ratio>5.5 else 2 if ratio>2.5 else 0


def build(arm,body,meshes,rigid):
    points=np.array([v.co[:] for v in body.data.vertices]);plan=[]
    for side in ('l','r'):
        for part in ('upperarm','lowerarm','thigh','calf'):
            bone=arm.data.bones[f'{part}_{side}'];a=np.array(bone.head_local);b=np.array(bone.tail_local)
            axis=b-a;length=float(np.linalg.norm(axis));t=(points-a)@axis/(length*length)
            distance=np.linalg.norm(points-(a+np.clip(t,0,1)[:,None]*axis),axis=1)
            mask=(t>.2)&(t<.8)&(distance<length*.65)
            radius=float(np.quantile(distance[mask],.2)) if mask.sum()>20 else length*.3
            count=helper_count(length,max(radius,.005))
            for i in range(count):
                plan.append({'name':f'{part}_deform_{i+1:02d}_{side}','parent':bone.name,
                    'center':(i+.5)/count,'start':i/count,'end':(i+1)/count,
                    'radius_m':radius,'length_m':length})
    bpy.context.view_layer.objects.active=arm
    bpy.ops.object.mode_set(mode='EDIT')
    for row in plan:
        parent=arm.data.edit_bones[row['parent']];bone=arm.data.edit_bones.new(row['name'])
        axis=parent.tail-parent.head;bone.head=parent.head+axis*row['start'];bone.tail=parent.head+axis*row['end']
        bone.roll=parent.roll;bone.parent=parent;bone.use_deform=True
    bpy.ops.object.mode_set(mode='OBJECT')
    # Reassign each limb's existing heat weights to nearby helper centers. This
    # preserves total influence and avoids a second overlapping heat solve.
    for obj in meshes:
        if obj.name in rigid:continue
        by_parent={}
        for row in plan:by_parent.setdefault(row['parent'],[]).append(row)
        for name,rows in by_parent.items():
            old=obj.vertex_groups.get(name)
            if old is None:continue
            groups=[obj.vertex_groups.new(name=r['name']) for r in rows]
            bone=arm.data.bones[name];a=bone.head_local;axis=bone.tail_local-a;length2=axis.length_squared
            for v in obj.data.vertices:
                weight=next((g.weight for g in v.groups if g.group==old.index),0.)
                if weight<1e-6:continue
                t=max(0.,min(1.,(v.co-a).dot(axis)/length2))
                centers=[r['center'] for r in rows]
                if t<=centers[0]:pairs=[(0,1.)]
                elif t>=centers[-1]:pairs=[(len(rows)-1,1.)]
                else:
                    j=next(i for i in range(len(rows)-1) if centers[i]<=t<=centers[i+1])
                    alpha=(t-centers[j])/(centers[j+1]-centers[j]);pairs=[(j,1-alpha),(j+1,alpha)]
                for j,factor in pairs:groups[j].add([v.index],weight*factor,'REPLACE')
                old.remove([v.index])
    arm['motion_deform_helpers']=json.dumps(plan)
    return plan


def pose(arm,frame):
    plan=json.loads(arm.get('motion_deform_helpers','[]'))
    if not plan:return
    previous=getattr(pose,'previous',{})
    if previous.get('arm')!=arm.as_pointer() or previous.get('frame')!=frame-1:
        previous={'arm':arm.as_pointer(),'angles':{}}
    angles={}
    centers={}
    for row in plan:centers.setdefault(row['parent'],[]).append(row['center'])
    for row in plan:
        q=arm.pose.bones[row['parent']].rotation_quaternion.normalized()
        # Extract only axial twist. Joint swing and center positions continue
        # to come from the tracked anatomical bones.
        twist=Quaternion((q.w,0.,q.y,0.))
        if twist.magnitude<1e-8:twist=Quaternion()
        else:twist.normalize()
        angle=2*math.atan2(twist.y,twist.w)
        if row['parent'] in previous['angles']:
            prior=previous['angles'][row['parent']];angle+=2*math.pi*round((prior-angle)/(2*math.pi))
        angles[row['parent']]=angle
        # The distal helper must meet the wrist/ankle with the full tracked
        # twist. Using its segment midpoint leaves a residual turn at the joint.
        values=centers[row['parent']];lo,hi=min(values),max(values)
        fraction=(row['center']-lo)/(hi-lo) if hi>lo else 1.
        correction=Quaternion(Vector((0,1,0)),-angle*(1-fraction))
        pb=arm.pose.bones[row['name']];pb.rotation_mode='QUATERNION';pb.rotation_quaternion=correction
        pb.keyframe_insert('rotation_quaternion',frame=frame,group=pb.name)
    pose.previous={'arm':arm.as_pointer(),'frame':frame,'angles':angles}
