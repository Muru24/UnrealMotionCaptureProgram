"""Bake evaluated UE poses onto the same mesh; no second retarget solve."""
import sys,json,math
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Vector,Quaternion


def run(model,packet,out):
    out=Path(out);data=json.loads(Path(packet).read_text(encoding='utf-8'))
    assert data['status']=='completed'
    bpy.ops.wm.open_mainfile(filepath=str(Path(model).resolve()))
    arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');arm.animation_data_clear()
    bones=sorted(arm.data.bones,key=lambda b:len(b.parent_recursive))
    assert all(b.name in data['reference'] for b in bones)
    # Fit only the coordinate convention using corresponding reference heads.
    # An orthogonal reflection is allowed: Unreal and Blender differ in handedness.
    a=np.array([data['reference'][b.name]['p'] for b in bones])*.01
    b=np.array([list(b.head_local) for b in bones]);ac=a.mean(0);bc=b.mean(0)
    u,_,vt=np.linalg.svd((a-ac).T@(b-bc));c=(u@vt).T
    offset=bc-c@ac
    residual=float(np.max(np.linalg.norm((c@a.T).T+offset-b,axis=1)))
    if residual>.002:raise ValueError(f'Manny reference mismatch: {residual}m')
    conv=Matrix(c.tolist());previous={};max_head_error=0.;max_angle=0.
    scene=bpy.context.scene;fps=data['fps'];scene.render.fps=round(fps);scene.render.fps_base=round(fps)/fps
    scene.frame_start=1;scene.frame_end=len(data['frames'])
    for i,row in enumerate(data['frames'],1):
        scene.frame_set(i)
        solved={}
        for bone in bones:
            name=bone.name;pb=arm.pose.bones[name];t=row[name];ref=data['reference'][name]
            def rotation(q):return Quaternion((q[3],*q[:3])).to_matrix()
            desired=(conv@rotation(t['q'])@rotation(ref['q']).transposed()@conv.transposed()@bone.matrix_local.to_3x3()).to_4x4()
            desired.translation=Vector((c@(np.array(t['p'])*.01)+offset).tolist())
            parent=pb.parent
            kwargs={'parent_matrix':solved[parent.name],'parent_matrix_local':parent.bone.matrix_local} if parent else {}
            basis=bone.convert_local_to_pose(desired,bone.matrix_local,invert=True,**kwargs)
            loc,q,scale=basis.decompose()
            if name in previous and q.dot(previous[name])<0:q.negate()
            previous[name]=q.copy();pb.rotation_mode='QUATERNION';pb.location=loc;pb.rotation_quaternion=q;pb.scale=scale
            for channel in ('location','rotation_quaternion','scale'):pb.keyframe_insert(channel,frame=i,group=name)
            solved[name]=desired
        bpy.context.view_layer.update()
        for name,desired in solved.items():
            pb=arm.pose.bones[name]
            max_head_error=max(max_head_error,(pb.head-desired.translation).length)
            angle=pb.matrix.to_quaternion().rotation_difference(desired.to_quaternion()).angle
            max_angle=max(max_angle,min(angle,abs(2*math.pi-angle)))
        if i%100==0:print('UE_POSE_BAKE',i,flush=True)
    assert max_head_error<1e-4,max_head_error
    assert max_angle<.002,max_angle
    arm['motion_root_bone']='pelvis';arm.hide_set(True);scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'animation.blend'))
    (out/'bake-report.json').write_text(json.dumps({'status':'completed','pipeline':data['pipeline'],
        'frames':scene.frame_end,'fps':fps,'bones':len(bones),'reference_fit_error_m':residual,
        'max_engine_head_error_m':max_head_error,'max_engine_rotation_error_rad':max_angle},indent=2),encoding='utf-8')


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
