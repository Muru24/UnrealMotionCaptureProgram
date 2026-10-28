"""FK retarget to imported humanoid controls; preserve original rest/skin data."""
import sys,json,math,hashlib
from pathlib import Path
import bpy
from mathutils import Matrix,Vector


def run(model,source,profile_path,out):
    model,source,profile_path,out=map(lambda p:Path(p).resolve(),(model,source,profile_path,out))
    p=json.loads(profile_path.read_text(encoding='utf-8'))
    if hashlib.sha256(model.read_bytes()).hexdigest()!=p['model_sha256']:raise ValueError('모델 해시가 다릅니다.')
    inputs={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in (model,source,profile_path)}
    bpy.ops.wm.open_mainfile(filepath=str(model));arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    with bpy.data.libraries.load(str(source),link=False) as (a,b):b.objects=['MotionSkeleton']
    src=b.objects[0];bpy.context.collection.objects.link(src);src.hide_set(True);src.hide_render=True
    arm.animation_data_clear();mapping={n:r for n,r in p['mapping'].items() if r['source'] in src.pose.bones}
    calibration={};finger_axes={};groups={};rest={b.name:(list(b.head_local),list(b.tail_local)) for b in arm.data.bones}
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from hand_retarget import palm_frame,curl_axis
    from adaptive_deform import pose as pose_helpers
    for side in ('l','r'):
        roles=[f'{part}_{side}' for part in ('hand','index_01','middle_01','pinky_01')]
        required=[next((n for n,r in mapping.items() if r['source']==role),None) for role in roles]
        if all(n is not None for n in required):
            palm=palm_frame(arm,*required)
            for name,row in mapping.items():
                if row['mode']=='finger_local' and name.endswith('_'+side):
                    target=curl_axis(arm.data.bones[name].matrix_local,palm,side)
                    source_axis=src.data.bones[row['source']].matrix_local.to_3x3().transposed()@Vector((0,0,-1))
                    source_axis.y=0;source_axis.normalize()
                    finger_axes[name]=source_axis.rotation_difference(target)
    for name,row in mapping.items():
        pb=arm.pose.bones[name];tr=pb.bone.matrix_local.to_3x3();sr=src.data.bones[row['source']].matrix_local.to_3x3()
        align=tr.col[1].normalized().rotation_difference(sr.col[1].normalized()).to_matrix() if row['mode']=='direction' else Matrix.Identity(3)
        calibration[name]=sr.transposed()@align@tr
        depth=0;parent=pb.parent
        while parent:depth+=1;parent=parent.parent
        groups.setdefault(depth,[]).append(name)
    data=json.loads(source.with_name('animation.json').read_text(encoding='utf-8'));fps=float(data['fps']);scene=bpy.context.scene
    scene.render.fps=round(fps);scene.render.fps_base=round(fps)/fps;scene.frame_start=1;scene.frame_end=len(data['frames'])
    root=arm.pose.bones[p['root']];scale=arm.data.bones[p['pelvis']].head_local.z/src.data.bones['pelvis'].head_local.z
    previous={};max_error=0.
    for i in range(scene.frame_end):
        scene.frame_set(i+1)
        delta=src.pose.bones['root'].matrix@src.data.bones['root'].matrix_local.inverted()
        offset=src.pose.bones['pelvis'].head-delta@src.data.bones['pelvis'].head_local
        desired=(delta.to_3x3()@root.bone.matrix_local.to_3x3()).to_4x4()
        desired.translation=root.bone.head_local+(delta.translation+offset)*scale
        basis=root.bone.convert_local_to_pose(desired,root.bone.matrix_local,invert=True)
        root.rotation_mode='QUATERNION';root.location=basis.translation;root.rotation_quaternion=basis.to_quaternion()
        root.keyframe_insert('location',frame=i+1);root.keyframe_insert('rotation_quaternion',frame=i+1)
        bpy.context.view_layer.update()
        for depth in sorted(groups):
            for name in groups[depth]:
                pb=arm.pose.bones[name];parent=pb.parent;rest_matrix=pb.bone.matrix_local
                parent_matrix=parent.matrix.copy() if parent else Matrix.Identity(4)
                parent_rest=parent.bone.matrix_local if parent else Matrix.Identity(4)
                anchor=parent_matrix@parent_rest.inverted()@rest_matrix if parent else rest_matrix.copy()
                if name in finger_axes:
                    align=finger_axes[name];q=(align@src.pose.bones[mapping[name]['source']].rotation_quaternion@align.conjugated()).normalized()
                else:
                    rotation=src.pose.bones[mapping[name]['source']].matrix.to_3x3().normalized()@calibration[name]
                    desired=rotation.to_4x4();desired.translation=anchor.translation
                    basis=pb.bone.convert_local_to_pose(desired,rest_matrix,parent_matrix=parent_matrix,parent_matrix_local=parent_rest,invert=True)
                    q=basis.to_quaternion().normalized()
                if name in previous and q.dot(previous[name])<0:q.negate()
                previous[name]=q.copy();pb.rotation_mode='QUATERNION';pb.rotation_quaternion=q
                pb.keyframe_insert('rotation_quaternion',frame=i+1,group=name)
            bpy.context.view_layer.update()
        pose_helpers(arm,i+1);bpy.context.view_layer.update()
        for pb in arm.pose.bones:
            if not all(math.isfinite(x) for row in pb.matrix for x in row):raise ValueError('Nonfinite target pose')
            max_error=max(max_error,abs((pb.tail-pb.head).length-pb.bone.length))
        if i%100==0:print('BUILTIN_FRAME',i,scene.frame_end,flush=True)
    for b in arm.data.bones:assert (list(b.head_local),list(b.tail_local))==rest[b.name]
    assert max_error<1e-4,max_error
    bpy.data.objects.remove(src,do_unlink=True);scene.frame_set(1)
    arm['motion_root_bone']=p['root'];arm.hide_set(True)
    if p.get('id','').startswith('user_'):arm['motion_preserve_materials']=True
    for obj in scene.objects:
        if obj.type=='MESH':obj.color=(.62,.66,.72,1)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.shading.type='SOLID';area.spaces.active.shading.color_type='OBJECT'
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'animation.blend'))
    assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in inputs.items())
    (out/'report.json').write_text(json.dumps({'status':'completed','model':p['id'],'frames':scene.frame_end,'fps':fps,
        'mapped_bones':len(mapping),'finger_bones':len(finger_axes),'rest_preserved':True,'max_bone_length_error_m':max_error,'input_sha256':inputs,
        'limitations':['FK preview; no new contact solver or engine-specific cloth physics']},indent=2),encoding='utf-8')


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
