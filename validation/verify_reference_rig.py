"""Blender-only round trip; this does not certify Unity/Unreal imports."""
from pathlib import Path
import json
import bpy
from mathutils import Vector
root=Path(__file__).resolve().parents[1];out=root/'assets/skeletons'
spec=json.loads((out/'humanoid_v1.json').read_text(encoding='utf-8'));expected={b['name']:b for b in spec['bones']}
records=[]
for filename in ('MotionHumanoid22.blend','MotionHumanoid22_Unity.fbx','MotionHumanoid22_Unreal.fbx'):
    if filename.endswith('.blend'):bpy.ops.wm.open_mainfile(filepath=str(out/filename))
    else:
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        bpy.ops.import_scene.fbx(filepath=str(out/filename))
    arms=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'];meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    assert len(arms)==len(meshes)==1
    arm=arms[0];mesh=meshes[0];assert set(arm.data.bones.keys())==set(expected)
    errors=[]
    for bone in arm.data.bones:
        want=expected[bone.name]
        assert (None if bone.parent is None else bone.parent.name)==want['parent']
        errors.append((arm.matrix_world@bone.head_local-Vector(want['head'])).length)
    assert max(errors)<1e-4,(filename,max(errors))
    assert all(mesh.vertex_groups.get(b['name']) is not None for b in spec['bones'] if b['deform'])
    assert any(m.type=='ARMATURE' and m.object==arm for m in mesh.modifiers)
    records.append({'file':filename,'bones':len(arm.data.bones),'max_head_error_m':max(errors),'skin_binding':True})
(root/'validation/m3/rig-roundtrip.json').write_text(json.dumps({'blender_version':bpy.app.version_string,
    'results':records,'unity_import_tested':False,'unreal_import_tested':False},indent=2),encoding='utf-8')
print('ROUNDTRIP',json.dumps(records),flush=True)
