"""Reuse the custom model's quaternion filters on Manny's arm/hand channels."""
import sys,json,math,hashlib
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from grip_stability import smooth_quaternions
from adaptive_deform import pose as pose_helpers


def angular_acceleration(values):
    increments=[]
    for a,b in zip(values,values[1:]):
        if a.dot(b)<0:b=-b
        increments.append((a.conjugated()@b).to_exponential_map())
    return math.degrees(math.sqrt(sum((b-a).length_squared for a,b in zip(increments,increments[1:]))/max(1,len(increments)-1)))


def run(source,out):
    source=Path(source).resolve();out=Path(out).resolve();out.mkdir(exist_ok=False)
    signature=hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(source));arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');scene=bpy.context.scene
    fps=scene.render.fps/scene.render.fps_base;frames=list(range(scene.frame_start,scene.frame_end+1))
    policy={}
    for side in ('l','r'):
        for name in (f'upperarm_{side}',f'lowerarm_{side}'):policy[name]=(.065,240)
        policy[f'hand_{side}']=(.08,180)
        for name in arm.pose.bones.keys():
            if name.endswith('_'+side) and 'twist' in name and ('upperarm' in name or 'lowerarm' in name):policy[name]=(.10,120)
            if name.endswith('_'+side) and any(name.startswith(f+'_') for f in ('thumb','index','middle','ring','pinky')):policy[name]=(.05,360)
    policy={n:p for n,p in policy.items() if n in arm.pose.bones}
    unchanged=[n for n in arm.pose.bones.keys() if n not in policy and not any(p.name in policy for p in arm.pose.bones[n].parent_recursive)]
    before={n:[] for n in policy};world={f'{part}_{side}':[] for side in ('l','r') for part in ('upperarm','lowerarm','hand')};protected=[]
    for f in frames:
        scene.frame_set(f)
        for n in policy:before[n].append(arm.pose.bones[n].rotation_quaternion.copy())
        for n in world:world[n].append(arm.pose.bones[n].matrix.to_quaternion())
        protected.append({n:arm.pose.bones[n].matrix.copy() for n in unchanged})
    filtered={n:smooth_quaternions(v,fps,*policy[n]) for n,v in before.items()}
    # Preserve arm/wrist counter-rotation by filtering the final hand frame.
    world_filtered={n:smooth_quaternions(v,fps,.08 if n.startswith('hand_') else .065,360 if n.startswith('hand_') else 540) for n,v in world.items()}
    for i,f in enumerate(frames):
        for n in policy:
            pb=arm.pose.bones[n];pb.rotation_mode='QUATERNION';pb.rotation_quaternion=filtered[n][i]
            pb.keyframe_insert('rotation_quaternion',frame=f,group=n)
    for i,f in enumerate(frames):
        scene.frame_set(f)
        solved={}
        for n,values in world_filtered.items():
            pb=arm.pose.bones[n];parent=pb.parent;parent_matrix=solved.get(parent.name,parent.matrix.copy())
            anchor=pb.bone.convert_local_to_pose(pb.matrix_basis.copy(),pb.bone.matrix_local,parent_matrix=parent_matrix,
                parent_matrix_local=parent.bone.matrix_local)
            desired=values[i].to_matrix().to_4x4();desired.translation=anchor.translation
            basis=pb.bone.convert_local_to_pose(desired,pb.bone.matrix_local,parent_matrix=parent_matrix,
                parent_matrix_local=parent.bone.matrix_local,invert=True)
            q=basis.to_quaternion().normalized()
            if i and filtered[n][i-1].dot(q)<0:q.negate()
            filtered[n][i]=q;pb.rotation_quaternion=q;pb.keyframe_insert('rotation_quaternion',frame=f,group=n)
            solved[n]=desired
        bpy.context.view_layer.update();pose_helpers(arm,f);bpy.context.view_layer.update()
    after={n:[] for n in world};max_protected=0.
    for i,f in enumerate(frames):
        scene.frame_set(f)
        for n in after:after[n].append(arm.pose.bones[n].matrix.to_quaternion())
        for n,m in protected[i].items():
            max_protected=max(max_protected,max(abs(arm.pose.bones[n].matrix[a][b]-m[a][b]) for a in range(4) for b in range(4)))
    metrics={n:{'world_angular_acceleration_before_deg_frame2':angular_acceleration(world[n]),
                'world_angular_acceleration_after_deg_frame2':angular_acceleration(after[n]),
                'max_world_step_after_degrees':max((math.degrees(min(a.rotation_difference(b).angle,2*math.pi-a.rotation_difference(b).angle)) for a,b in zip(after[n],after[n][1:])),default=0),
                'max_local_step_after_degrees':max((math.degrees(min(a.rotation_difference(b).angle,2*math.pi-a.rotation_difference(b).angle)) for a,b in zip(filtered[n],filtered[n][1:])),default=0)} for n in ('hand_l','hand_r')}
    assert max_protected<1e-5,max_protected
    assert all(m['world_angular_acceleration_after_deg_frame2']<=m['world_angular_acceleration_before_deg_frame2']+1e-5 for m in metrics.values()),metrics
    assert all(m['max_world_step_after_degrees']<=360/fps+.02 for m in metrics.values()),metrics
    scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'animation.blend'))
    assert hashlib.sha256(source.read_bytes()).hexdigest()==signature
    (out/'hand-stability.json').write_text(json.dumps({'status':'completed','source':str(source),'source_sha256':signature,
        'frames':len(frames),'fps':fps,'metrics':metrics,'protected_body_max_matrix_change':max_protected,
        'filter_seconds_speed_degrees':policy,'wrist_filter_space':'arm_and_hand_world_then_filtered_parent_local','revision':3,
        'wrist_world_filter_seconds':.08,'wrist_world_speed_degrees_per_second':360,
        'limits':['temporal_filter_not_sword_contact_solver','PMX_anatomical_axis_limits_not_copied_to_Manny']},indent=2),encoding='utf-8')


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
