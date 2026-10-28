"""Bake a mapped PMX rig from an existing reference motion, in a new file."""
import sys,json,math,hashlib
from pathlib import Path
import bpy
from mathutils import Matrix,Vector


def run(model,source,out):
    model=Path(model).resolve();source=Path(source).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    signatures={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (model,source)}
    bpy.ops.wm.open_mainfile(filepath=str(model));arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
    with bpy.data.libraries.load(str(source),link=False) as (a,b):b.objects=['MotionSkeleton']
    src=b.objects[0];bpy.context.collection.objects.link(src);src.hide_render=True;src.hide_set(True)
    data=json.loads(source.with_name('animation.json').read_text(encoding='utf-8'))
    mapping={'下半身':'pelvis','上半身':'spine_01','上半身2':'spine_02','首':'neck_01','頭':'head'}
    for jp,side in [('左','l'),('右','r')]:
        for target,ref in [('肩','clavicle'),('腕','upperarm'),('ひじ','lowerarm'),('手首','hand'),('足','thigh'),('ひざ','calf'),('足首','foot'),('つま先','ball'),('足D','thigh'),('ひざD','calf'),('足首D','foot'),('足先EX','ball')]:mapping[jp+target]=ref+'_'+side
        for target,ref in [('人指','index'),('中指','middle'),('薬指','ring'),('小指','pinky')]:
            for k,num in [(1,'１'),(2,'２')]:
                if f'{ref}_{k:02d}_{side}' in src.pose.bones:mapping[jp+target+num]=f'{ref}_{k:02d}_{side}'
    assert all(n in arm.pose.bones and s in src.pose.bones for n,s in mapping.items())
    constraints=0
    for pb in arm.pose.bones:
        constraints+=len(pb.constraints)
        for c in list(pb.constraints):pb.constraints.remove(c)
        pb.rotation_mode='QUATERNION';pb.matrix_basis=Matrix.Identity(4)
    arm.animation_data_clear();arm.data.pose_position='POSE'
    # One explicit model profile. Unmapped helpers retain rest transforms and follow parents.
    calibration={}
    for target,ref in mapping.items():
        tr=arm.data.bones[target].matrix_local.to_3x3();sr=src.data.bones[ref].matrix_local.to_3x3()
        align=tr.col[1].normalized().rotation_difference(sr.col[1].normalized()).to_matrix()
        calibration[target]=sr.transposed()@align@tr
    scale=arm.data.bones['下半身'].head_local.z/src.data.bones['pelvis'].head_local.z
    root=arm.pose.bones['全ての親'];fps=float(data['fps']);scene=bpy.context.scene
    scene.render.fps=round(fps);scene.render.fps_base=round(fps)/fps;scene.frame_start=1;scene.frame_end=len(data['frames'])
    maximum_length_error=0.;changes={n:0. for n in mapping};first={}
    for i in range(scene.frame_end):
        scene.frame_set(i+1);root.location=src.pose.bones['root'].location*scale
        root.rotation_quaternion=src.pose.bones['root'].rotation_quaternion.copy()
        root.keyframe_insert('location',frame=i+1);root.keyframe_insert('rotation_quaternion',frame=i+1)
        solved={}
        for pb in arm.pose.bones:
            rest=pb.bone.matrix_local;parent=pb.parent
            parent_matrix=Matrix.Identity(4) if parent is None else solved[parent.name]
            parent_rest=Matrix.Identity(4) if parent is None else parent.bone.matrix_local
            anchor=rest.copy() if parent is None else parent_matrix@parent_rest.inverted()@rest
            if pb==root:
                solved[pb.name]=pb.bone.convert_local_to_pose(pb.matrix_basis,rest);continue
            if pb.name in mapping:
                rotation=src.pose.bones[mapping[pb.name]].matrix.to_3x3().normalized()@calibration[pb.name]
                desired=rotation.to_4x4();desired.translation=anchor.translation
                basis=pb.bone.convert_local_to_pose(desired,rest,parent_matrix=parent_matrix,parent_matrix_local=parent_rest,invert=True)
                pb.rotation_quaternion=basis.to_quaternion().normalized();pb.location=(0,0,0);pb.scale=(1,1,1)
                pb.keyframe_insert('rotation_quaternion',frame=i+1,group=pb.name)
                if pb.name not in first:first[pb.name]=pb.rotation_quaternion.copy()
                changes[pb.name]=max(changes[pb.name],math.degrees(first[pb.name].rotation_difference(pb.rotation_quaternion).angle))
            solved[pb.name]=pb.bone.convert_local_to_pose(pb.matrix_basis,rest,parent_matrix=parent_matrix,parent_matrix_local=parent_rest)
            assert all(math.isfinite(v) for row in solved[pb.name] for v in row)
        bpy.context.view_layer.update()
        for pb in arm.pose.bones:maximum_length_error=max(maximum_length_error,abs((pb.tail-pb.head).length-pb.bone.length))
    for layer in arm.animation_data.action.layers:
        for strip in layer.strips:
            for slot in arm.animation_data.action.slots:
                bag=strip.channelbag(slot)
                if bag:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:key.interpolation='LINEAR'
    bpy.data.objects.remove(src,do_unlink=True)
    scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'animation.blend'))
    assert maximum_length_error<1e-5
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in signatures.items())
    (out/'report.json').write_text(json.dumps({'status':'completed','input_sha256':signatures,'mapping':mapping,'root_motion_scale':scale,'frames':scene.frame_end,'fps':fps,'removed_constraints':constraints,'max_bone_length_error_m':maximum_length_error,'rotation_ranges_degrees':changes,'limitations':['model_specific_mapping','short_character_proportions_no_contact_IK','unmapped_face_ears_hair_not_tracked','only_existing_finger_bones_mapped','MMD_physics_disabled_in_preview']},ensure_ascii=False,indent=2),encoding='utf-8')
    print('PMX_RETARGETED',len(mapping),scene.frame_end,maximum_length_error,flush=True)


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
