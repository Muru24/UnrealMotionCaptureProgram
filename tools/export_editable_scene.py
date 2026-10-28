"""Export a lightweight skinned mesh and animation channels for the local editor."""
import sys,json,hashlib,math
from pathlib import Path
import bpy,numpy as np


def run(source,out):
    source=Path(source).resolve();out=Path(out).resolve();out.mkdir(exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source));arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');scene=bpy.context.scene
    bones=sorted(arm.data.bones,key=lambda b:len(b.parent_recursive));names=[b.name for b in bones];parents=[-1 if b.parent is None else names.index(b.parent.name) for b in bones]
    rest=np.array([list(map(list,b.matrix_local)) for b in bones]);local=[rest[i] if p<0 else np.linalg.inv(rest[p])@rest[i] for i,p in enumerate(parents)]
    locations=[];quaternions=[];scales=[];objects=[];max_error=0.
    for frame in range(scene.frame_start,scene.frame_end+1):
        scene.frame_set(frame);l=[];q=[];s=[];solved=[]
        for i,b in enumerate(bones):
            pb=arm.pose.bones[b.name];v,r,z=pb.matrix_basis.decompose();l.append(list(v));q.append(list(r));s.append(list(z))
            result=(np.eye(4) if parents[i]<0 else solved[parents[i]])@local[i]@np.array(pb.matrix_basis)
            max_error=max(max_error,float(np.max(np.abs(result-np.array(pb.matrix)))));solved.append(result)
        locations.append(l);quaternions.append(q);scales.append(s);objects.append(np.array(arm.matrix_world))
    if max_error>1e-4:raise ValueError(f'편집기가 지원하지 않는 본 상속 방식입니다: {max_error}')
    vertices=[];triangles=[];weight_ids=[];weights=[]
    meshes=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==arm for m in o.modifiers)]
    # Allocate by surface complexity. Equal per-object quotas reduce a dense
    # body to ~100 triangles when a character has dozens of tiny accessories.
    total_faces=sum(max(1,len(o.data.polygons)*2) for o in meshes)
    for obj in meshes:
        for m in obj.modifiers:m.show_viewport=False
        faces=max(1,len(obj.data.polygons)*2);budget=max(24,4500*faces/total_faces)
        dec=obj.modifiers.new('EditorPreview','DECIMATE');dec.ratio=min(1.,budget/faces)
        deps=bpy.context.evaluated_depsgraph_get();ev=obj.evaluated_get(deps);mesh=ev.to_mesh(preserve_all_data_layers=True,depsgraph=deps);mesh.calc_loop_triangles()
        transform=arm.matrix_world.inverted()@obj.matrix_world;base=len(vertices)
        for v in mesh.vertices:
            vertices.append(list(transform@v.co));groups=[]
            for g in v.groups:
                n=obj.vertex_groups[g.group].name
                if n in names and g.weight>1e-6:groups.append((names.index(n),g.weight))
            groups=sorted(groups,key=lambda x:x[1],reverse=True)[:8] or [(0,1.)];total=sum(w for _,w in groups)
            weight_ids.append([i for i,w in groups]+[0]*(8-len(groups)));weights.append([w/total for i,w in groups]+[0.]*(8-len(groups)))
        triangles.extend([[base+i for i in t.vertices] for t in mesh.loop_triangles]);ev.to_mesh_clear()
    if not vertices:raise ValueError('스킨 메시를 찾을 수 없습니다.')
    np.savez_compressed(out/'scene.npz',vertices=np.array(vertices,dtype=np.float32),triangles=np.array(triangles,dtype=np.int32),weight_ids=np.array(weight_ids,dtype=np.int32),weights=np.array(weights,dtype=np.float32),rest=rest,locations=np.array(locations),quaternions=np.array(quaternions),scales=np.array(scales),object_matrices=np.array(objects))
    (out/'scene.json').write_text(json.dumps({'schema':'editable_scene_v1','source_blend':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'names':names,'parents':parents,'frame_start':scene.frame_start,'frames':scene.frame_end-scene.frame_start+1,'fps':scene.render.fps/scene.render.fps_base,
        'preview_triangles':len(triangles),'channel_rebuild_error':max_error},ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
