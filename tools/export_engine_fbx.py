"""Blender-only export of an existing, verified M4 animation; originals stay immutable."""
import sys,json,math
from pathlib import Path
import bpy

def run(source,out):
    animation=json.loads((source.parent/'animation.json').read_text(encoding='utf-8'))
    if animation.get('schema')!='standard_bone_animation_v1':raise ValueError('M4 animation required')
    out.mkdir(exist_ok=False)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene=bpy.context.scene;arm=bpy.data.objects['MotionSkeleton'];mesh=bpy.data.objects['BoneProxy']
    if bpy.data.objects.get('FingerProxy') is not None:
        bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);bpy.data.objects['FingerProxy'].select_set(True)
        bpy.context.view_layer.objects.active=mesh;bpy.ops.object.join()
    fps=float(animation['fps']);factor=30/fps
    # Integer sampling rate avoids fractional-frame FBX import ambiguity in game engines.
    for layer in arm.animation_data.action.layers:
        for strip in layer.strips:
            for slot in arm.animation_data.action.slots:
                bag=strip.channelbag(slot)
                if bag:
                    for curve in bag.fcurves:
                        for p in curve.keyframe_points:
                            p.co.x=1+(p.co.x-1)*factor
                            p.handle_left.x=1+(p.handle_left.x-1)*factor
                            p.handle_right.x=1+(p.handle_right.x-1)*factor
                        curve.update()
    scene.render.fps=30;scene.render.fps_base=1
    scene.frame_start=1;scene.frame_end=round((len(animation['frames'])-1)*factor)+1
    # FBX doesn't preserve per-bone JSON missing flags or object visibility as pose validity.
    for obj in (arm,mesh):
        if obj.animation_data and obj.animation_data.action:
            for layer in obj.animation_data.action.layers:
                for strip in layer.strips:
                    for slot in obj.animation_data.action.slots:
                        bag=strip.channelbag(slot)
                        if bag:
                            for curve in list(bag.fcurves):
                                if curve.data_path in ('hide_viewport','hide_render'):bag.fcurves.remove(curve)
        obj.hide_viewport=False;obj.hide_render=False
    bpy.ops.object.select_all(action='DESELECT');arm.select_set(True);mesh.select_set(True)
    bpy.context.view_layer.objects.active=arm;scene.frame_set(1)
    arm.name='Armature'
    for name,forward,up in [('Motion_Unreal.fbx','X','Z'),('Motion_Unity.fbx','-Z','Y')]:
        bpy.ops.export_scene.fbx(filepath=str(out/name),use_selection=True,object_types={'ARMATURE','MESH'},
            add_leaf_bones=False,use_armature_deform_only=False,bake_anim=True,bake_anim_use_all_actions=False,
            mesh_smooth_type='FACE',
            bake_anim_use_nla_strips=False,bake_anim_simplify_factor=0.,bake_anim_step=1.,
            apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward=forward,axis_up=up)
    report={'status':'exported','source_fps':fps,'fbx_fps':30,'source_frames':len(animation['frames']),
        'fbx_frames':scene.frame_end,'source_duration_seconds':(len(animation['frames'])-1)/fps,
        'fbx_duration_seconds':(scene.frame_end-1)/30,'bones':len(arm.data.bones),
        'missing_pose_frames':len(animation['frames'])-animation['frames_with_pose'],
        'missing_spans':animation.get('orientation_policy',{}).get('missing_spans',[]),
        'finger_policy':animation.get('finger_policy'),
        'limits':['reference_rig_not_target_retarget','missing_pose_uses_parent_rest_fallback_not_reconstruction',
                  'fbx_has_no_validity_flags_consult_source_animation_json','unity_import_not_verified']}
    (out/'export.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('FBX_EXPORTED',scene.frame_end,flush=True)

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:];run(Path(args[0]),Path(args[1]))
