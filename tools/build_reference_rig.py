"""Run with Blender --background --factory-startup --python this_file."""
from pathlib import Path
import json,math
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'assets/skeletons';spec=json.loads((out/'humanoid_v1.json').read_text(encoding='utf-8'))
targets=[out/'MotionHumanoid22.blend',out/'MotionHumanoid22_Unity.fbx',out/'MotionHumanoid22_Unreal.fbx']
if any(p.exists() for p in targets):raise FileExistsError('Reference assets already exist; preserve them before regenerating.')
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=1.
arm_data=bpy.data.armatures.new('MotionHumanoid22');arm=bpy.data.objects.new('MotionSkeleton',arm_data)
bpy.context.collection.objects.link(arm);bpy.context.view_layer.objects.active=arm;arm.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
for item in spec['bones']:
    bone=arm_data.edit_bones.new(item['name']);bone.head=item['head'];bone.tail=item['tail']
    bone.use_deform=item['deform']
    if item['parent']:
        bone.parent=arm_data.edit_bones[item['parent']]
        bone.use_connect=(bone.head-bone.parent.tail).length<1e-6
bpy.ops.object.mode_set(mode='OBJECT');arm.show_in_front=True;arm_data.display_type='OCTAHEDRAL'
arm['reference_schema']=spec['schema'];arm['pose']='T-pose';arm['animation_baked']=False
vertices=[];faces=[];groups=[]
for item in spec['bones']:
    if not item['deform']:continue
    a,b=Vector(item['head']),Vector(item['tail']);axis=(b-a).normalized()
    helper=Vector((0,1,0)) if abs(axis.y)<.9 else Vector((1,0,0))
    u=axis.cross(helper).normalized();v=axis.cross(u).normalized()
    radius=.075 if item['name'] in ('pelvis','spine_01','spine_02','head') else .028
    mid=a.lerp(b,.45);base=len(vertices)
    vertices.extend([tuple(a),tuple(b),tuple(mid+u*radius),tuple(mid+v*radius),tuple(mid-u*radius),tuple(mid-v*radius)])
    for j in range(4):
        k=2+j;l=2+(j+1)%4;faces.extend([(base,base+k,base+l),(base+1,base+l,base+k)])
    groups.append((item['name'],list(range(base,base+6))))
mesh_data=bpy.data.meshes.new('BoneProxyMesh');mesh_data.from_pydata(vertices,[],faces);mesh_data.update()
mesh=bpy.data.objects.new('BoneProxy',mesh_data);bpy.context.collection.objects.link(mesh)
mesh.parent=arm;mod=mesh.modifiers.new('SkeletonSkin','ARMATURE');mod.object=arm
for name,indices in groups:mesh.vertex_groups.new(name=name).add(indices,1.,'REPLACE')
for color,name in (((.13,.48,.85,1),'Left'),((.9,.46,.16,1),'Right'),((.15,.7,.4,1),'Body')):
    material=bpy.data.materials.new(name);material.diffuse_color=color;mesh.data.materials.append(material)
for polygon in mesh.data.polygons:
    name=groups[polygon.index//8][0];polygon.material_index=0 if name.endswith('_l') else 1 if name.endswith('_r') else 2
mesh['purpose']='Rigidly skinned bone visualization, not a production character mesh'
for area in bpy.context.screen.areas if bpy.context.screen else []:
    if area.type=='VIEW_3D':
        area.spaces.active.region_3d.view_distance=3.5
        area.spaces.active.region_3d.view_location=Vector((0,0,1))
bpy.ops.wm.save_as_mainfile(filepath=str(targets[0]))
mesh.select_set(True);arm.select_set(True);bpy.context.view_layer.objects.active=arm
for target,forward,up in ((targets[1],'-Z','Y'),(targets[2],'X','Z')):
    bpy.ops.export_scene.fbx(filepath=str(target),use_selection=True,object_types={'ARMATURE','MESH'},
        add_leaf_bones=False,use_armature_deform_only=False,bake_anim=False,
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward=forward,axis_up=up)
report={'blender_version':bpy.app.version_string,'bones':len(arm.data.bones),
    'roots':[b.name for b in arm.data.bones if b.parent is None],
    'mesh_vertices':len(mesh.data.vertices),'vertex_groups':len(mesh.vertex_groups),
    'asset_files':[p.name for p in targets],'scale_length':bpy.context.scene.unit_settings.scale_length,
    'animation_baked':False,'unreal_import_verified':False,'unity_import_verified':False}
(out/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('REFERENCE_RIG',json.dumps(report),flush=True)
