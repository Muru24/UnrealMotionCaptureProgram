"""Blender background: re-open generated files and independently evaluate keyed poses."""
import json,sys,math
from pathlib import Path
import bpy
from mathutils import Vector

def verify(folder,motion):
    data=json.loads(motion.read_text(encoding='utf-8'))
    animation=json.loads((folder/'animation.json').read_text(encoding='utf-8'))
    bpy.ops.wm.open_mainfile(filepath=str(folder/'animation.blend'))
    arm=bpy.data.objects['MotionSkeleton'];scene=bpy.context.scene
    assert len(arm.data.bones)==22 and arm.animation_data.action is not None
    assert scene.frame_end==len(data['frames'])
    assert abs(scene.render.fps/scene.render.fps_base-animation['fps'])<1e-5
    names=animation['bone_names'];max_error=0.;count=0
    previous={};segment=None;meshes=[];sole_heights=[];contact_previous={};max_slide=0.
    for i,(row,solved) in enumerate(zip(data['frames'],animation['frames'])):
        scene.frame_set(i+1);bpy.context.view_layer.update()
        key=(row.get('tracking_segment'),row.get('scene_index'))
        if key!=segment:previous={};contact_previous={};segment=key
        if row['positions'][1] is None:
            assert arm.hide_viewport and bpy.data.objects['BoneProxy'].hide_render
            assert all(q is None for q in solved['local_quaternions_wxyz']);previous={};contact_previous={};continue
        assert not arm.hide_viewport
        if data.get('correction'):
            assert bpy.data.objects.get('Ground (estimated Z=0)') is not None
            obj=bpy.data.objects['BoneProxy'];evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
            for s,side in enumerate(('l','r')):
                state=data['correction']['frames'][i]['feet'][s]
                if state not in ('inferred_contact','inferred_ground_support'):contact_previous.pop(side,None);continue
                point=arm.pose.bones['foot_'+side].head.copy()
                assert abs(point.z-.07)<1e-4
                if state=='inferred_contact':
                    if side in contact_previous:max_slide=max(max_slide,(point-contact_previous[side]).length)
                    contact_previous[side]=point
                else:contact_previous.pop(side,None)
                groups={obj.vertex_groups['foot_'+side].index,obj.vertex_groups['ball_'+side].index}
                heights=[mesh.vertices[v.index].co.z for v in obj.data.vertices if any(g.group in groups and g.weight>.5 for g in v.groups)]
                sole_heights.append(min(heights));assert -.005<=min(heights)<=.025,(i,side,state,min(heights))
            evaluated.to_mesh_clear()
        if i in (1,len(data['frames'])//2,len(data['frames'])-1):
            mesh=bpy.data.objects['BoneProxy'].evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
            meshes.append([tuple(v.co) for v in mesh.vertices])
            assert all(math.isfinite(c) for v in mesh.vertices for c in v.co)
            bpy.data.objects['BoneProxy'].evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
        for j,name in enumerate(names):
            q=solved['local_quaternions_wxyz'][j]
            if q is None:previous.pop(name,None);continue
            assert abs(sum(v*v for v in q)-1)<1e-5
            if name in previous:assert sum(a*b for a,b in zip(previous[name],q))>=-1e-6
            previous[name]=q
            actual=arm.pose.bones[name]
            max_error=max(max_error,(actual.head-Vector(row['positions'][j])).length)
            assert max(abs(a-b) for a,b in zip(actual.rotation_quaternion,q))<1e-5
            count+=1
    assert max_error<1e-4 and max_slide<1e-4
    mesh_moves=len(meshes)>1 and any(abs(a-b)>1e-4 for arow,brow in zip(meshes[0],meshes[-1]) for a,b in zip(arow,brow))
    if len(data['frames'])>10:assert mesh_moves
    return {'file':str(folder/'animation.blend'),'frames':len(data['frames']),
            'evaluated_bone_keys':count,'max_reopened_head_error_m':max_error,'skin_mesh_moves':mesh_moves,
            'max_reopened_contact_step_m':max_slide,'minimum_contact_proxy_sole_z_m':min(sole_heights) if sole_heights else None,
            'passed':True}

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:]
    result=verify(Path(args[0]),Path(args[1]))
    Path(args[2]).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('M4_REOPEN_PASS',json.dumps(result),flush=True)
