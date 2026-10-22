"""Independent FBX reimport of both axes: evaluated heads and reference scale."""
import sys,json,math
from pathlib import Path
import bpy
from mathutils import Vector
args=sys.argv[sys.argv.index('--')+1:];source,out,target=map(Path,args)
metadata=json.loads((out/'export.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=str(source));scene=bpy.context.scene;arm=bpy.data.objects['MotionSkeleton']
samples=sorted(set([1,metadata['fbx_frames']//3,metadata['fbx_frames']//2,metadata['fbx_frames']]))
expected={}
for f in samples:
    original=1+(f-1)*metadata['source_fps']/30
    scene.frame_set(math.floor(original),subframe=original%1);bpy.context.view_layer.update()
    expected[f]={b.name:tuple(arm.matrix_world@b.head) for b in arm.pose.bones}
results=[]
for name in ('Motion_Unreal.fbx','Motion_Unity.fbx'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps=30;bpy.context.scene.render.fps_base=1
    bpy.ops.import_scene.fbx(filepath=str(out/name),anim_offset=0.)
    arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');scene=bpy.context.scene
    # FBX has joint transforms, not Blender's use_connect flag. The importer guesses
    # a connected pelvis from its inferred root length, suppressing pelvis translation.
    bpy.context.view_layer.objects.active=arm;arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for bone in arm.data.edit_bones:bone.use_connect=False
    bpy.ops.object.mode_set(mode='OBJECT')
    for layer in arm.animation_data.action.layers:
        for strip in layer.strips:
            for slot in arm.animation_data.action.slots:
                bag=strip.channelbag(slot)
                if bag:
                    curve=bag.fcurves[0];print('IMPORTED KEYS',name,tuple(curve.keyframe_points[0].co),tuple(curve.keyframe_points[-1].co),flush=True)
    assert set(arm.pose.bones.keys())==set(next(iter(expected.values())))
    maximum=0.;worst=None;frame_errors=[]
    for f in samples:
        scene.frame_set(f);bpy.context.view_layer.update()
        for b in arm.pose.bones:
            error=(arm.matrix_world@b.head-Vector(expected[f][b.name])).length
            if error>maximum:maximum=error;worst=[f,b.name,list(arm.matrix_world@b.head),expected[f][b.name]]
        frame_errors.append([f,maximum])
    print('DEBUG',name,frame_errors,worst,'fps',scene.render.fps,scene.render.fps_base,flush=True)
    assert maximum<.002,(name,maximum)
    results.append({'file':name,'bones':len(arm.data.bones),'max_head_error_m':maximum})
target.write_text(json.dumps({'passed':True,'samples':samples,'files':results,'expected_source_heads_m':expected},indent=2),encoding='utf-8')
print(json.dumps(results),flush=True)
