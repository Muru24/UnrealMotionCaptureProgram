"""Render a local model animation preview with a camera following its root."""
import sys,json
from pathlib import Path
import bpy
from mathutils import Vector


def run(source,out,mode='samples',limit=None):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(Path(source).resolve()))
    scene=bpy.context.scene;arm=next(o for o in scene.objects if o.type=='ARMATURE');scene.frame_set(1)
    meshes=[o for o in scene.objects if o.type=='MESH' and not o.hide_render]
    for material in bpy.data.materials:
        if material.node_tree:
            texture=material.node_tree.nodes.get('mmd_base_tex')
            if texture is not None:material.node_tree.nodes.active=texture
    points=[o.matrix_world@Vector(c) for o in meshes for c in o.bound_box]
    lo=Vector(tuple(min(p[k] for p in points) for k in range(3)));hi=Vector(tuple(max(p[k] for p in points) for k in range(3)))
    size=max(hi-lo);center=(lo+hi)/2
    bpy.ops.object.camera_add();cam=bpy.context.object;scene.camera=cam
    cam.data.type='ORTHO';cam.data.ortho_scale=size*1.5;cam.data.clip_start=.001;cam.data.clip_end=1000
    scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='TEXTURE'
    if arm.get('motion_preserve_materials'):
        scene.display.shading.color_type=arm.get('motion_preview_shading','MATERIAL')
    elif arm.get('motion_root_bone'):
        # Engine shader graphs are not portable to Blender; use a neutral
        # studio material rather than displaying missing textures as magenta.
        scene.display.shading.color_type='OBJECT'
        for mesh in meshes:mesh.color=(.62,.66,.72,1)
    if scene.world is None:scene.world=bpy.data.worlds.new('ModelPreviewWorld')
    scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True;scene.display.shading.background_type='WORLD';scene.world.color=(.045,.045,.055)
    scene.render.resolution_x=512;scene.render.resolution_y=640;scene.render.resolution_percentage=100
    extension='jpg' if mode=='all' else 'png';scene.render.image_settings.file_format='JPEG' if extension=='jpg' else 'PNG';scene.render.image_settings.quality=95
    root_name=arm.get('motion_root_bone') or ('全ての親' if '全ての親' in arm.pose.bones else 'root')
    base=(arm.matrix_world@arm.pose.bones[root_name].head).copy()
    props=[o for o in meshes if o.get('grip_anchor_rest') is not None]
    if props:
        # Rigid weapon vertices are stored at bind pose. Frame its complete
        # animated envelope rather than clipping the blade at the image edge.
        from itertools import product
        corners={o.name:[Vector(c) for c in product(*[(min(v.co[k] for v in o.data.vertices),max(v.co[k] for v in o.data.vertices)) for k in range(3)])] for o in props}
        envelope=list(points)
        for frame in range(scene.frame_start,scene.frame_end+1):
            scene.frame_set(frame)
            shift=arm.matrix_world@arm.pose.bones[root_name].head-base
            for prop in props:
                delta=arm.pose.bones['hand_r'].matrix@arm.data.bones['hand_r'].matrix_local.inverted()
                envelope.extend(arm.matrix_world@delta@c-shift for c in corners[prop.name])
        lo=Vector(tuple(min(p[k] for p in envelope) for k in range(3)));hi=Vector(tuple(max(p[k] for p in envelope) for k in range(3)))
        center=(lo+hi)/2;size=max(hi-lo);cam.data.ortho_scale=size*1.9
    frames=range(scene.frame_start,min(scene.frame_end+1,scene.frame_start+int(limit)) if limit else scene.frame_end+1) if mode in ('all','all-png') else sorted(set([1,scene.frame_end//4,scene.frame_end//2,scene.frame_end]))
    for frame in frames:
        scene.frame_set(frame);target=center+(arm.matrix_world@arm.pose.bones[root_name].head-base)
        cam.location=target+Vector((size*.65,-size*2,size*.5));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(out/f'{frame:05d}.{extension}');bpy.ops.render.render(write_still=True)
    (out/'render.json').write_text(json.dumps({'frames':len(frames),'fps':scene.render.fps/scene.render.fps_base,'image_extension':extension,'camera':'root_following','source':str(source)}),encoding='utf-8')


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
