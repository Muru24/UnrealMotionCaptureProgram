"""Local, landmark-guided rigging of a static humanoid FBX; never edit input.

Landmarks are explicit model-space points, not a claim of automatic anatomy
recognition. Heat weights are solved on a proxy and transferred to the original
surface without changing its topology, UVs, or materials.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector,Matrix


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def surface_distance_weights(obj,arm):
    """Screened surface diffusion fallback when Blender's heat solver returns holes."""
    import numpy as np
    bones=[b for b in arm.data.bones if b.use_deform]
    points=np.asarray([v.co[:] for v in obj.data.vertices],float)
    distances=[]
    for b in bones:
        a=np.asarray(b.head_local);axis=np.asarray(b.tail_local)-a
        t=np.clip((points-a)@axis/max(float(axis@axis),1e-12),0,1)
        distances.append(np.linalg.norm(points-a-t[:,None]*axis,axis=1))
    d=np.asarray(distances).T;nearest=np.argpartition(d,min(3,len(bones)-1),axis=1)[:,:4]
    seed=np.zeros_like(d);values=1/np.maximum(np.take_along_axis(d,nearest,axis=1),.003)**4
    np.put_along_axis(seed,nearest,values,axis=1);seed/=seed.sum(axis=1,keepdims=True)
    edges=np.asarray([e.vertices[:] for e in obj.data.edges],int);weights=seed.copy()
    if len(edges):
        rows=np.r_[edges[:,0],edges[:,1]];cols=np.r_[edges[:,1],edges[:,0]];degree=np.bincount(rows,minlength=len(points)).clip(1)
        for _ in range(16):
            average=np.zeros_like(weights);np.add.at(average,rows,weights[cols]);average/=degree[:,None]
            weights=.7*seed+.3*average;weights/=weights.sum(axis=1,keepdims=True)
    top=np.argpartition(weights,-4,axis=1)[:,-4:];sparse=np.zeros_like(weights)
    np.put_along_axis(sparse,top,np.take_along_axis(weights,top,axis=1),axis=1);sparse/=sparse.sum(axis=1,keepdims=True)
    obj.vertex_groups.clear();groups=[obj.vertex_groups.new(name=b.name) for b in bones]
    for i,row in enumerate(sparse):
        for j in np.flatnonzero(row>1e-7):groups[j].add([i],float(row[j]),'REPLACE')


def run(source, landmarks, output):
    source, landmarks, output = map(lambda p: Path(p).resolve(), (source, landmarks, output))
    if output.exists():
        raise FileExistsError('Use a new output folder: ' + str(output))
    settings = json.loads(landmarks.read_text(encoding='utf-8'))
    before = digest(source)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(source), ignore_leaf_bones=False)
    if any(o.type == 'ARMATURE' for o in bpy.context.scene.objects):
        raise ValueError('Input already has an armature; preserve and map it instead.')
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    body = bpy.data.objects.get(settings['body_mesh'])
    if body not in meshes:
        raise ValueError('Body mesh not found')
    originals = {o.name: (len(o.data.vertices), len(o.data.polygons)) for o in meshes}
    scale = float(settings['scale'])
    offset = Vector(settings['offset'])
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('Invalid model scale')
    # Bake imported matrices into mesh coordinates, preserving every vertex.
    matrices = {obj.name:obj.matrix_world.copy() for obj in meshes}
    for obj in meshes:
        matrix = matrices[obj.name]
        obj.parent = None
        obj.matrix_world.identity()
        obj.data.transform(Matrix.Scale(scale,4) @ Matrix.Translation(offset) @ matrix,shape_keys=True)
        obj.data.update()
    def point(value):
        return (Vector(value) + offset) * scale
    bpy.ops.object.armature_add()
    arm = bpy.context.object
    arm.name = settings['id'] + 'Rig'
    arm.show_in_front = True
    arm['motion_root_bone'] = 'root'
    arm['motion_preview_shading'] = 'TEXTURE' if any(image.has_data and image.source=='FILE' for image in bpy.data.images) else 'MATERIAL'
    bpy.ops.object.mode_set(mode='EDIT')
    arm.data.edit_bones.remove(arm.data.edit_bones[0])
    for row in settings['bones']:
        bone = arm.data.edit_bones.new(row['name'])
        bone.head, bone.tail = point(row['head']), point(row['tail'])
        if bone.length < .001:
            raise ValueError('Zero length bone: ' + bone.name)
        bone.use_deform = bone.name != 'root'
        bone.align_roll(Vector((0, -1, 0)))
        if row['parent']:
            bone.parent = arm.data.edit_bones[row['parent']]
    bpy.ops.object.mode_set(mode='OBJECT')
    # A smaller body proxy makes heat diffusion feasible on dense source meshes.
    proxy = body.copy()
    proxy.data = body.data.copy()
    proxy.name = '_WeightProxy'
    bpy.context.collection.objects.link(proxy)
    bpy.ops.object.select_all(action='DESELECT')
    proxy.select_set(True)
    bpy.context.view_layer.objects.active = proxy
    decimate = proxy.modifiers.new('WeightProxy', 'DECIMATE')
    decimate.ratio = min(1., settings.get('proxy_vertices', 18000) / max(1, len(proxy.data.vertices)))
    bpy.ops.object.modifier_apply(modifier=decimate.name)
    proxy.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    deform = {b.name for b in arm.data.bones if b.use_deform}
    weighting_method='bone_heat'
    if any(sum(g.weight for g in v.groups)<1e-6 for v in proxy.data.vertices):
        surface_distance_weights(proxy,arm);weighting_method='distance_seeded_surface_diffusion'
        print('HEAT_FALLBACK',weighting_method,flush=True)
    rigid = settings.get('rigid_meshes', {})
    rows = []
    for obj in meshes:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        obj.vertex_groups.clear()
        if obj.name in rigid:
            name = rigid[obj.name]
            if name not in deform:
                raise ValueError('Invalid rigid bone: ' + name)
            group = obj.vertex_groups.new(name=name)
            group.add(list(range(len(obj.data.vertices))), 1., 'REPLACE')
        else:
            for name in deform:
                obj.vertex_groups.new(name=name)
            transfer = obj.modifiers.new('SurfaceWeights', 'DATA_TRANSFER')
            transfer.object = proxy
            transfer.use_vert_data = True
            transfer.data_types_verts = {'VGROUP_WEIGHTS'}
            transfer.vert_mapping = 'POLYINTERP_NEAREST'
            transfer.layers_vgroup_select_src = 'ALL'
            transfer.layers_vgroup_select_dst = 'NAME'
            bpy.ops.object.modifier_apply(modifier=transfer.name)
            bpy.ops.object.vertex_group_limit_total(limit=4)
            bpy.ops.object.vertex_group_normalize_all(lock_active=False)
        unweighted = 0
        max_error = 0.
        for vertex in obj.data.vertices:
            total = sum(g.weight for g in vertex.groups)
            if total <= .0001:
                unweighted += 1
            max_error = max(max_error, abs(total - 1))
        if unweighted or max_error > .001:
            raise ValueError(f'Invalid weights: {obj.name}, {unweighted}, {max_error}')
        modifier = obj.modifiers.new('HumanoidDeform', 'ARMATURE')
        modifier.object = arm
        modifier.use_deform_preserve_volume = True
        obj.parent = arm
        assert originals[obj.name] == (len(obj.data.vertices), len(obj.data.polygons))
        rows.append({'mesh': obj.name, 'vertices': len(obj.data.vertices),
                     'rigid': rigid.get(obj.name), 'unweighted': unweighted,
                     'max_weight_sum_error': max_error})
        print('WEIGHTED', obj.name, len(obj.data.vertices), flush=True)
    proxy_vertices = len(proxy.data.vertices)
    bpy.data.objects.remove(proxy, do_unlink=True)
    helpers=[]
    if settings.get('adaptive_deform'):
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        from adaptive_deform import build
        helpers=build(arm,body,meshes,rigid)
    output.mkdir(parents=True)
    bpy.ops.file.pack_all()
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'model.blend'))
    for obj in meshes:
        obj.select_set(True)
    bpy.ops.export_scene.fbx(filepath=str(output / 'Demon_Rigged.fbx'), use_selection=True,
        object_types={'MESH', 'ARMATURE'}, add_leaf_bones=False, bake_anim=False,
        axis_forward='-Y', axis_up='Z', path_mode='COPY', embed_textures=True)
    profile = {'schema': 'builtin_humanoid_v1', 'id': settings['id'],
        'root': 'root', 'pelvis': 'pelvis', 'bones':len(arm.data.bones), 'deform_helpers':helpers,'weighting_method':weighting_method,
        'model_sha256': digest(output / 'model.blend'),
        'mapping': {b.name: {'source': b.name,
            'mode': 'finger_local' if b.name.startswith(('thumb_', 'index_', 'middle_', 'ring_', 'pinky_')) else 'rest_delta' if b.name in ('pelvis', 'spine_01', 'spine_02', 'neck_01', 'head') or b.name.startswith(('foot_','ball_')) else 'direction'}
            for b in arm.data.bones if b.use_deform and b.name in {r['name'] for r in settings['bones']}}}
    (output / 'profile.json').write_text(json.dumps(profile, indent=2), encoding='utf-8')
    assert digest(source) == before
    report = {'status': 'completed', 'source_sha256': before, 'source_unchanged': True,
        'bones': len(arm.data.bones), 'deform_helpers':len(helpers), 'proxy_vertices': proxy_vertices, 'meshes': rows,
        'topology_preserved': True, 'method': weighting_method+'_proxy_surface_transfer',
        'limitations': ['Model-specific landmarks; not automatic landmark detection',
            'Facial expressions are not tracked; no facial rig generated',
            'Armor collision and cloth physics are not solved']}
    (output / 'rig-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('STATIC_RIG_READY', output, flush=True)


if __name__ == '__main__':
    run(*sys.argv[sys.argv.index('--') + 1:])
