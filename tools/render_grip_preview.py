"""Render a close view following the sword handle for manual contact review."""
import sys,json
from pathlib import Path
import bpy
from mathutils import Vector


def run(source,out,mode='samples'):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(Path(source).resolve()));scene=bpy.context.scene;sword=bpy.data.objects['GripSword']
    for material in bpy.data.materials:
        if material.node_tree:
            node=material.node_tree.nodes.get('mmd_base_tex')
            if node is not None:material.node_tree.nodes.active=node
    bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=.42;cam.data.clip_start=.001;scene.camera=cam
    scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='TEXTURE';scene.display.shading.show_cavity=True;scene.world.color=(.045,.045,.055)
    scene.render.resolution_x=640;scene.render.resolution_y=640;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    frames=range(1,scene.frame_end+1) if mode=='all' else [1,71,151,223,351]
    for frame in frames:
        scene.frame_set(frame);m=sword.matrix_world;center=m.translation-m.to_3x3().col[2]*.06;direction=(m.to_3x3().col[0]*.6+m.to_3x3().col[1]).normalized()
        cam.location=center+direction*.5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/f'{frame:05d}.png');bpy.ops.render.render(write_still=True)
    (out/'render.json').write_text(json.dumps({'frames':len(frames),'fps':scene.render.fps/scene.render.fps_base,'source':str(source),'camera':'handle_following_contact_review'}),encoding='utf-8')


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
