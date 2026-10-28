"""Render a textured local rig review, retaining its original material colors."""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def run(source, output, mode='samples'):
    source, output = Path(source).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == 'ARMATURE')
    scene.frame_set(scene.frame_start)
    meshes = [o for o in scene.objects if o.type == 'MESH']
    points = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    lo = Vector([min(p[k] for p in points) for k in range(3)])
    hi = Vector([max(p[k] for p in points) for k in range(3)])
    center = (hi + lo) / 2
    size = max(hi - lo)
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    scene.camera = camera
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = size * 1.5
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'MATERIAL'
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.background_type = 'WORLD'
    if scene.world is None:
        scene.world = bpy.data.worlds.new('ReviewWorld')
    scene.world.color = (.025, .035, .05)
    scene.render.resolution_x = 640
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    root = arm.pose.bones[arm.get('motion_root_bone', 'root')]
    base = (arm.matrix_world @ root.head).copy()
    frames = (range(scene.frame_start, scene.frame_end + 1) if mode == 'all' else
              sorted({scene.frame_start, scene.frame_end // 4, scene.frame_end // 2, scene.frame_end}))
    for frame in frames:
        scene.frame_set(frame)
        target = center + (arm.matrix_world @ root.head - base)
        camera.location = target + Vector((size * .6, -size * 2, size * .30))
        camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = str(output / f'{frame:05d}.png')
        bpy.ops.render.render(write_still=True)
    (output / 'render.json').write_text(json.dumps({'frames': len(frames),
        'fps': scene.render.fps / scene.render.fps_base,
        'source': str(source), 'camera': 'root_following'}), encoding='utf-8')


if __name__ == '__main__':
    run(*sys.argv[sys.argv.index('--') + 1:])
