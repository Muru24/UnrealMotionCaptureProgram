"""Export the final corrected Manny automatically, preserving its source blend."""
import sys,json,hashlib,shutil
from pathlib import Path
import bpy


def run(source,out,stem='Manny_Animation'):
    source=Path(source).resolve();out=Path(out).resolve();before=hashlib.sha256(source.read_bytes()).hexdigest()
    if stem not in ('Manny_Animation','Model_Animation'):raise ValueError('Invalid export name')
    blend=out/(stem+'.blend');fbx=out/(stem+'.fbx')
    if blend.exists() or fbx.exists():raise FileExistsError('Final animation already exists')
    bpy.ops.wm.open_mainfile(filepath=str(source));arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    bpy.ops.object.select_all(action='DESELECT');arm.hide_set(False);arm.select_set(True);bpy.context.view_layer.objects.active=arm
    for obj in bpy.context.scene.objects:
        if obj.type=='MESH' and any(m.type=='ARMATURE' and m.object==arm for m in obj.modifiers):obj.hide_set(False);obj.select_set(True)
    bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'ARMATURE','MESH'},add_leaf_bones=False,
        use_armature_deform_only=False,bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,
        bake_anim_simplify_factor=0.,axis_forward='X',axis_up='Z')
    shutil.copyfile(source,blend)
    if hashlib.sha256(source.read_bytes()).hexdigest()!=before:raise ValueError('Final animation source changed')
    (out/'delivery.json').write_text(json.dumps({'status':'completed','source_sha256':before,'source_blend':str(source),
        'blend':str(blend),'fbx':str(fbx),'frames':bpy.context.scene.frame_end-bpy.context.scene.frame_start+1,
        'hand_stabilization_applied':True,'fbx_engine_reimport_verified':False},indent=2),encoding='utf-8')


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
