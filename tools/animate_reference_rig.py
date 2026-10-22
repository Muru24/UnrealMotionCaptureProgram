"""Blender-only M4 solver. Arguments after --: motion.json output_directory."""
import sys,json,math
from pathlib import Path
import bpy
from mathutils import Vector,Matrix,Quaternion


def oriented(direction,lateral):
    y=direction.normalized()
    x=lateral-y*lateral.dot(y)
    if x.length<1e-6:
        helper=Vector((0,0,1)) if abs(y.z)<.9 else Vector((0,1,0))
        x=helper-y*helper.dot(y)
    x.normalize();z=x.cross(y).normalized()
    return Matrix((x,y,z)).transposed()


def transport_roll(old,direction):
    """Preserve axial roll while exactly matching the observed bone direction."""
    old_y=old.col[1].normalized();new_y=direction.normalized()
    delta=Quaternion(old.col[0],math.pi) if old_y.dot(new_y)<-1+1e-7 else old_y.rotation_difference(new_y)
    return delta.to_matrix()@old


def follow_parent_twist(transported,anchor,fps):
    """Only change roll: no Euler clamping or slowing of the observed swing."""
    axis=transported.col[1].normalized()
    a=transported.col[0].normalized();b=anchor.col[0].normalized()
    error=math.atan2(axis.dot(a.cross(b)),max(-1.,min(1.,a.dot(b))))
    step=max(-math.radians(120)/fps,min(math.radians(120)/fps,error*(1-math.exp(-1/(fps*.18)))))
    return Quaternion(axis,step).to_matrix()@transported,step


def missing_spans(records,names,fps):
    spans=[]
    for j,name in enumerate(names):
        start=None
        for i in range(len(records)+1):
            missing=i<len(records) and records[i]['bone_status'][j]=='missing'
            boundary=i>0 and i<len(records) and (records[i]['tracking_segment'],records[i]['scene_index'])!=(records[i-1]['tracking_segment'],records[i-1]['scene_index'])
            if start is not None and (not missing or boundary):
                spans.append({'bone':name,'start_frame':start,'end_frame':i-1,'seconds':(i-start)/fps,
                              'kind':'long_missing' if (i-start)/fps>.25 else 'short_missing','filled':False})
                start=None
            if missing and start is None:start=i
    return spans


def run(source,out):
    root=Path(__file__).resolve().parents[1]
    data=json.loads(source.read_text(encoding='utf-8'))
    spec=json.loads((root/'assets/skeletons/humanoid_v1.json').read_text(encoding='utf-8'))
    if data.get('schema')!='standard_motion_positions_v1' or data['skeleton']!=spec:
        raise ValueError('Animation requires the unchanged MotionHumanoid22 definition.')
    frames=data['frames'];fps=float(data['video']['fps'])
    if not 0<len(frames)<=18000 or not math.isfinite(fps) or not 1<=fps<=240:
        raise ValueError('Invalid animation timeline.')
    out.mkdir(parents=True,exist_ok=False)
    bpy.ops.wm.open_mainfile(filepath=str(root/'assets/skeletons/MotionHumanoid22.blend'))
    arm=bpy.data.objects['MotionSkeleton'];scene=bpy.context.scene
    scene.render.fps=round(fps);scene.render.fps_base=round(fps)/fps
    scene.frame_start=1;scene.frame_end=len(frames)
    correction=data.get('correction')
    if correction:
        bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.002))
        ground=bpy.context.object;ground.name='Ground (estimated Z=0)'
        material=bpy.data.materials.new('Ground');material.diffuse_color=(.09,.12,.16,1)
        ground.data.materials.append(material)
    names=[b['name'] for b in spec['bones']];indices={n:i for i,n in enumerate(names)}
    targets={'pelvis':'spine_01','spine_01':'spine_02','spine_02':'neck_01','neck_01':'head'}
    for side in ('l','r'):
        for a,b in (('clavicle','upperarm'),('upperarm','lowerarm'),('lowerarm','hand'),('thigh','calf'),('calf','foot'),('foot','ball')):
            targets[f'{a}_{side}']=f'{b}_{side}'
    previous={};previous_world={};last_seen={};segment=None;records=[];max_error=0.;max_direction_error=0.;valid_frames=0
    twist_bones={f'{part}_{side}' for part in ('upperarm','lowerarm','thigh','calf') for side in ('l','r')}
    twist_steps=[];short_reconnections=0;long_restarts=0
    for i,row in enumerate(frames):
        if row['frame_index']!=i:raise ValueError('Animation frame order differs.')
        scene.frame_set(i+1)
        points={n:None if p is None else Vector(p) for n,p in zip(names,row['positions'])}
        if len(row['positions'])!=22 or any(p is not None and (len(p)!=3 or not all(math.isfinite(v) for v in p)) for p in row['positions']):
            raise ValueError('Invalid animation positions.')
        key=(row.get('tracking_segment'),row.get('scene_index'))
        if key!=segment:previous={};previous_world={};last_seen={};segment=key
        available=points['pelvis'] is not None
        for obj in (arm,bpy.data.objects['BoneProxy']):
            obj.hide_viewport=not available;obj.hide_render=not available
        bpy.context.view_layer.update()
        if not available:previous={};previous_world={};last_seen={}
        lateral=None
        for left,right in (('thigh_l','thigh_r'),('upperarm_l','upperarm_r')):
            if points[left] is not None and points[right] is not None:
                value=points[left]-points[right]
                if value.length>1e-6:lateral=value.normalized();break
        lateral=lateral or Vector((1,0,0))
        solved={};states={};local=[];locations=[]
        for item in spec['bones']:
            name=item['name'];pb=arm.pose.bones[name];pb.rotation_mode='QUATERNION'
            pb.matrix_basis=Matrix.Identity(4)
            parent=item['parent'];target=targets.get(name)
            valid=available and points[name] is not None and (parent is None or states[parent]!='missing')
            direction=None if target is None or points[target] is None or points[name] is None else points[target]-points[name]
            if target and (direction is None or direction.length<1e-6):valid=False
            if name=='root':rotation=pb.bone.matrix_local.to_3x3()
            elif valid and direction is not None:
                # Rest roll is explicitly matched, so the T-pose produces identity local rotations.
                rest_direction=Vector(item['tail'])-Vector(item['head'])
                rest_frame=oriented(rest_direction,Vector((1,0,0)))
                planted=bool(correction and name in ('foot_l','foot_r') and
                    correction['frames'][i]['feet'][0 if name.endswith('_l') else 1] in ('inferred_contact','ground_collision','inferred_ground_support'))
                roll_axis=Vector((0,0,1)).cross(direction) if planted else lateral
                rotation=oriented(direction,roll_axis)@rest_frame.transposed()@pb.bone.matrix_local.to_3x3()
                anchor=None
                if name in twist_bones:
                    parent_rest=arm.data.bones[parent].matrix_local.to_3x3()
                    # A parent-relative prior, not an observation of skin/forearm twist.
                    anchor=transport_roll(solved[parent].to_3x3()@parent_rest.transposed()@pb.bone.matrix_local.to_3x3(),direction)
                gap=i-last_seen.get(name,i)-1
                if name in previous_world and gap/fps<=.25 and not planted and name.endswith(('_l','_r')):
                    rotation=transport_roll(previous_world[name],direction)
                    if gap>0:short_reconnections+=1
                    if anchor is not None:
                        rotation,step=follow_parent_twist(rotation,anchor,fps);twist_steps.append(abs(step))
                elif anchor is not None:
                    rotation=anchor
                    if name in last_seen and gap>0:long_restarts+=1
            else:
                # Leaf twist is unobservable: inherit the parent transform relative to rest.
                rotation=(solved[parent].to_3x3()@arm.data.bones[parent].matrix_local.to_3x3().transposed()@pb.bone.matrix_local.to_3x3()) if parent else pb.bone.matrix_local.to_3x3()
            desired=rotation.to_4x4()
            desired.translation=points[name] if valid else (solved[parent]@arm.data.bones[parent].matrix_local.inverted()@pb.bone.matrix_local).translation if parent else Vector(item['head'])
            if parent:
                basis=pb.bone.convert_local_to_pose(desired,pb.bone.matrix_local,parent_matrix=solved[parent],parent_matrix_local=pb.parent.bone.matrix_local,invert=True)
            else:basis=pb.bone.convert_local_to_pose(desired,pb.bone.matrix_local,invert=True)
            q=basis.to_quaternion().normalized()
            if name in previous and q.dot(previous[name])<0:q.negate()
            if valid:previous[name]=q.copy();previous_world[name]=rotation.copy();last_seen[name]=i
            else:
                previous.pop(name,None)
                # Keep roll only briefly; positions and missing status are never synthesized.
                if i-last_seen.get(name,i)>math.ceil(fps*.25):previous_world.pop(name,None)
            pb.location=basis.to_translation();pb.rotation_quaternion=q;pb.scale=(1,1,1)
            pb.keyframe_insert('rotation_quaternion',frame=i+1,group=name)
            pb.keyframe_insert('location',frame=i+1,group=name)
            solved[name]=desired;states[name]='solved' if valid else 'missing'
            local.append(list(q) if valid else None);locations.append(list(pb.location) if valid else None)
        bpy.context.view_layer.update()
        for name in names:
            if states[name]=='solved':
                pb=arm.pose.bones[name];error=(pb.head-points[name]).length
                max_error=max(max_error,error)
                if name in targets:
                    expected=(points[targets[name]]-points[name]).normalized()
                    max_direction_error=max(max_direction_error,((pb.tail-pb.head).normalized()-expected).length)
        # Missing frames stay on the original timeline and are visibly hidden, never interpolated.
        for obj in (arm,bpy.data.objects['BoneProxy']):
            obj.hide_viewport=not available;obj.hide_render=not available
            obj.keyframe_insert('hide_viewport',frame=i+1);obj.keyframe_insert('hide_render',frame=i+1)
        valid_frames+=int(available)
        records.append({'frame_index':i,'timestamp':i/fps,'tracking_segment':key[0],'scene_index':key[1],
                        'local_quaternions_wxyz':local,'local_locations_m':locations,'bone_status':[states[n] for n in names]})
    # Bake true shortest-path SLERP at quarter frames, then interpolate the dense keys.
    # Missing/cut boundaries retain step keys and visibility is always discrete.
    for i in range(len(records)-1):
        a,b=records[i],records[i+1]
        if (a['tracking_segment'],a['scene_index'])!=(b['tracking_segment'],b['scene_index']):continue
        for j,name in enumerate(names):
            qa=a['local_quaternions_wxyz'][j];qb=b['local_quaternions_wxyz'][j]
            if qa is None or qb is None:continue
            pb=arm.pose.bones[name];qa=Quaternion(qa);qb=Quaternion(qb)
            if qa.dot(qb)<0:qb.negate()
            for t in (.25,.5,.75):
                pb.rotation_quaternion=qa.slerp(qb,t)
                pb.location=Vector(a['local_locations_m'][j]).lerp(Vector(b['local_locations_m'][j]),t)
                pb.keyframe_insert('rotation_quaternion',frame=i+1+t,group=name)
                pb.keyframe_insert('location',frame=i+1+t,group=name)
    channel_bones={f'pose.bones["{name}"].{channel}':j for j,name in enumerate(names) for channel in ('rotation_quaternion','location')}
    for obj in (arm,bpy.data.objects['BoneProxy']):
        action=obj.animation_data.action if obj.animation_data else None
        if action:
            for layer in action.layers:
                for strip in layer.strips:
                    for slot in action.slots:
                        bag=strip.channelbag(slot)
                        if bag:
                            for curve in bag.fcurves:
                                j=channel_bones.get(curve.data_path)
                                for point in curve.keyframe_points:
                                    i=int(math.floor(point.co.x+1e-6))-1
                                    connected=(j is not None and 0<=i<len(records)-1 and
                                        records[i]['local_quaternions_wxyz'][j] is not None and records[i+1]['local_quaternions_wxyz'][j] is not None and
                                        (records[i]['tracking_segment'],records[i]['scene_index'])==(records[i+1]['tracking_segment'],records[i+1]['scene_index']))
                                    point.interpolation='LINEAR' if connected else 'CONSTANT'
    arm['animation_baked']=True;arm['root_motion']=bool(correction);arm['pose']='Animated MotionHumanoid22'
    first=next((i+1 for i,r in enumerate(records) if r['local_quaternions_wxyz'][1] is not None),1)
    scene.frame_set(first)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'animation.blend'))
    result={'schema':'standard_bone_animation_v1','fps':fps,'bone_names':names,'skeleton':spec,
        'quaternion_order':'wxyz','rotation_space':'Blender PoseBone.matrix_basis relative to rest and parent',
        'units':'meters_reference_proportions','blender_frame_start':1,
        'root_motion':bool(correction),'root_motion_kind':data.get('root_motion_kind','contact_constraint_estimate' if correction else 'in_place'),
        'smoothing':bool(correction),'correction':correction,'frames':records,'frames_with_pose':valid_frames,
        'playback_interpolation':'quarter_frame_slerp_linear_location_valid_spans_only',
        'max_solved_head_error_m':max_error,'max_direction_error':max_direction_error,
        'orientation_policy':{'revision':2,'twist_prior':'parent_relative_swing_transport','twist_bones':sorted(twist_bones),
            'twist_time_constant_seconds':.18,'max_twist_correction_degrees_per_second':120,
            'max_applied_twist_step_degrees':math.degrees(max(twist_steps,default=0)),
            'short_gap_roll_memory_seconds':.25,'short_roll_reconnections':short_reconnections,'long_roll_restarts':long_restarts,
            'missing_spans':missing_spans(records,names,fps),'missing_positions_filled':False},
        'limits':['twist_is_parent_frame_and_transport_prior_not_observed','leaf_orientation_inherited',
        'missing_bones_fallback_parent_not_recovered','disconnected_attachments_include_local_translation',
        'no_interpolation_across_missing_or_cuts','world_motion_not_measured','engine_import_not_verified']}
    (out/'animation.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    if max_error>1e-4 or max_direction_error>1e-4:raise ValueError(f'Bone reconstruction failed: {max_error}, {max_direction_error}')
    print('M4_VERIFIED',len(records),valid_frames,max_error,flush=True)


if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:];run(Path(args[0]),Path(args[1]))
