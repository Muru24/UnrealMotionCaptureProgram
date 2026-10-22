"""Render a temporary scene from an animated file; never save scene changes."""
from pathlib import Path
import sys,bpy
from mathutils import Vector
args=sys.argv[sys.argv.index('--')+1:]
bpy.ops.wm.open_mainfile(filepath=args[0]);scene=bpy.context.scene
scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO'
scene.display.shading.color_type='MATERIAL';scene.display.shading.show_shadows=True
scene.display.shading.background_type='WORLD';scene.world.color=(.025,.035,.055)
scene.render.resolution_x=480;scene.render.resolution_y=540;scene.render.resolution_percentage=100
camera_data=bpy.data.cameras.new('QA Camera');camera=bpy.data.objects.new('QA Camera',camera_data)
scene.collection.objects.link(camera);camera.location=(2,-5,2.3)
camera.rotation_euler=(Vector((0,0,1))-camera.location).to_track_quat('-Z','Y').to_euler()
camera_data.type='ORTHO';camera_data.ortho_scale=2.5;scene.camera=camera
out=Path(args[1]);out.mkdir(exist_ok=True,parents=True)
for frame in (1,101,201):
    scene.frame_set(frame);scene.render.filepath=str(out/f'blender-frame-{frame}.png');bpy.ops.render.render(write_still=True)
