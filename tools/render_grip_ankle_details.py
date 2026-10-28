"""Render high-resolution hand contact and ankle junctions for visual QA."""
import sys,json
from pathlib import Path
import bpy
from mathutils import Vector

source,out,kind=sys.argv[sys.argv.index('--')+1:];out=Path(out).resolve();out.mkdir(exist_ok=True,parents=True)
bpy.ops.wm.open_mainfile(filepath=str(Path(source).resolve()));scene=bpy.context.scene;arm=next(o for o in scene.objects if o.type=='ARMATURE')
bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';scene.camera=cam
scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_cavity=True
scene.render.resolution_x=800;scene.render.resolution_y=800;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
for f in [1,31,111,201,301,445]:
    scene.frame_set(f);pelvis=arm.pose.bones['pelvis'];body=(pelvis.matrix@pelvis.bone.matrix_local.inverted()).to_3x3()
    if kind=='ankles':
        center=(arm.pose.bones['foot_l'].head+arm.pose.bones['foot_r'].head)*.5+Vector((0,0,.08))
        direction=body@Vector((.6,-1,.35));cam.data.ortho_scale=1.0
    else:
        sword=bpy.data.objects['GripSword'];delta=arm.pose.bones['hand_r'].matrix@arm.data.bones['hand_r'].matrix_local.inverted()
        center=delta@Vector(sword['grip_anchor_rest']);axis=(delta.to_3x3()@Vector(sword['grip_axis_rest'])).normalized()
        center-=axis*.10;front=delta.to_3x3()@Vector(sword['grip_front_rest']);direction=front+axis*.25;cam.data.ortho_scale=.64
    cam.location=center+direction.normalized()*2;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(out/f'{f:05d}.png');bpy.ops.render.render(write_still=True)
