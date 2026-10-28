"""Convert a local PMX to a packed Blender model without changing its source."""
import sys,json,hashlib
from pathlib import Path
import bpy


def run(source,out,addon):
    source=Path(source).resolve();out=Path(out).resolve()
    if source.suffix.lower()!='.pmx' or not source.is_file():raise ValueError('PMX file required')
    signature=hashlib.sha256(source.read_bytes()).hexdigest()
    out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(Path(addon).parent))
    import mmd_tools
    mmd_tools.register()
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.mmd_tools.import_model(filepath=str(source),scale=.08,types={'MESH','ARMATURE','MORPHS'},rename_bones=False)
    arms=[o for o in bpy.data.objects if o.type=='ARMATURE'];meshes=[o for o in bpy.data.objects if o.type=='MESH']
    if len(arms)!=1 or not meshes:raise ValueError('Expected one rig and a skinned mesh')
    arm=arms[0];arm.show_in_front=True
    images=[]
    for im in bpy.data.images:
        if im.source=='FILE':
            exists=Path(bpy.path.abspath(im.filepath)).is_file()
            images.append({'name':im.name,'exists':exists})
            if exists:im.pack()
    bpy.context.scene.unit_settings.system='METRIC'
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
    report={'source':str(source),'source_sha256':signature,'addon_version':mmd_tools.MMD_TOOLS_VERSION,'armature':arm.name,'meshes':len(meshes),'vertices':sum(len(m.data.vertices) for m in meshes),'images':images,'bones':[{'name':b.name,'jp':arm.pose.bones[b.name].mmd_bone.name_j,'en':arm.pose.bones[b.name].mmd_bone.name_e,'parent':None if b.parent is None else b.parent.name,'head':list(b.head_local),'tail':list(b.tail_local),'deform':b.use_deform} for b in arm.data.bones]}
    (out/'import.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==signature
    print('PMX_IMPORTED',len(report['bones']),report['vertices'],flush=True)


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
