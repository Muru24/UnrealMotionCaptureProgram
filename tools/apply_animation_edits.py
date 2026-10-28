"""Bake editor offsets to a new Blender animation and model FBX."""
import sys,json,hashlib
from pathlib import Path
import bpy,numpy as np
from mathutils import Quaternion,Vector,Matrix
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from app.editable_animation import EditableAnimation,MODEL,multiply,matrix


def run(cache,project,out):
    editor=EditableAnimation(cache);editor.load(project);source=Path(editor.info['source_blend']);out=Path(out)
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    if before!=editor.info['source_sha256']:raise ValueError('편집 원본이 변경되었습니다.')
    bpy.ops.wm.open_mainfile(filepath=str(source));scene=bpy.context.scene;arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
    max_error=0.;previous={}
    for f in range(editor.count):
        scene.frame_set(f+editor.info['frame_start'])
        locations,quaternions,scales=editor.local_channels(f)
        for i,n in enumerate(editor.names):
            pb=arm.pose.bones[n];q=quaternions[i]
            if n in previous and previous[n]@q<0:q=-q
            previous[n]=q.copy();pb.rotation_mode='QUATERNION';pb.location=Vector(locations[i]);pb.rotation_quaternion=Quaternion(q);pb.scale=Vector(scales[i])
            for channel in ('location','rotation_quaternion','scale'):pb.keyframe_insert(channel,frame=f+editor.info['frame_start'],group=n)
        loc,q=editor.offset(MODEL,f);arm.matrix_world=Matrix(editor.data['object_matrices'][f]@matrix(loc,q));arm.rotation_mode='QUATERNION'
        for channel in ('location','rotation_quaternion','scale'):arm.keyframe_insert(channel,frame=f+editor.info['frame_start'])
        bpy.context.view_layer.update();expected=editor.transforms(f)
        for i,n in enumerate(editor.names):max_error=max(max_error,float(np.max(np.abs(np.array(arm.matrix_world@arm.pose.bones[n].matrix)-expected[i]))))
    if max_error>1e-4:raise ValueError(f'실시간 편집과 Blender 결과가 다릅니다: {max_error}')
    scene.frame_set(scene.frame_start);bpy.ops.wm.save_as_mainfile(filepath=str(out/'animation.blend'))
    bpy.ops.object.select_all(action='DESELECT');arm.hide_set(False);arm.select_set(True);bpy.context.view_layer.objects.active=arm
    for obj in scene.objects:
        if obj.type=='MESH' and any(m.type=='ARMATURE' and m.object==arm for m in obj.modifiers):obj.hide_set(False);obj.select_set(True)
    bpy.ops.export_scene.fbx(filepath=str(out/'Edited_Manny.fbx'),use_selection=True,object_types={'ARMATURE','MESH'},
        add_leaf_bones=False,use_armature_deform_only=False,bake_anim=True,bake_anim_use_all_actions=False,
        bake_anim_use_nla_strips=False,bake_anim_simplify_factor=0.,axis_forward='X',axis_up='Z')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    (out/'edit-report.json').write_text(json.dumps({'status':'completed','frames':editor.count,'fps':editor.fps,
        'source_sha256':before,'edited_bones':list(editor.edits),'live_export_max_matrix_error':max_error,
        'limb_ik':editor.limb_ik,'limits':['two_bone_ik_no_collision_solver','fbx_engine_reimport_not_verified']},indent=2),encoding='utf-8')


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
