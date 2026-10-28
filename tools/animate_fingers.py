"""Blender: append 30 animated finger bones to an immutable 22-bone animation."""
import sys,json,math
from pathlib import Path
import bpy
from mathutils import Vector,Matrix,Quaternion
sys.path.insert(0,str(Path(__file__).resolve().parent))
from animate_reference_rig import oriented,transport_roll,missing_spans
from finger_limits import guard_rotation,LIMITS


def run(source,raw_path,out,selection_path=None):
    data=json.loads((source.parent/'animation.json').read_text(encoding='utf-8'))
    corrected=json.loads((source.parent/'corrected-motion.json').read_text(encoding='utf-8'))
    raw=json.loads(raw_path.read_text(encoding='utf-8'));frames=data['frames'];fps=float(data['fps'])
    if len(data['bone_names'])!=22 or len(raw['frames'])!=len(frames):raise ValueError('Expected matching 22-bone source.')
    selection=None if selection_path is None else json.loads(selection_path.read_text(encoding='utf-8'))
    if selection is not None and (selection.get('schema')!='selected_hand_shapes_v1' or len(selection['frames'])!=len(frames) or any(r['frame_index']!=i for i,r in enumerate(selection['frames']))):raise ValueError('Hand selection timeline differs.')
    hands=corrected.get('hand_orientation_observations')
    if hands is None or len(hands)!=len(frames):raise ValueError('Generate palm/wrist observations first.')
    idx={n:i for i,n in enumerate(raw['joint_names'])};spec=data['skeleton'];original_names=list(data['bone_names'])
    bpy.ops.wm.open_mainfile(filepath=str(source));arm=bpy.data.objects['MotionSkeleton'];bpy.context.view_layer.objects.active=arm
    bpy.ops.object.select_all(action='DESELECT');arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    definitions=[];chains={};canonical={}
    config={'thumb':(.05,.04,(.035,.025,.025),.6),'index':(.028,.085,(.04,.025,.02),.12),'middle':(.006,.095,(.045,.03,.025),0.),'ring':(-.016,.09,(.042,.028,.022),-.08),'pinky':(-.036,.075,(.032,.022,.018),-.16)}
    for side,full,sign in [('l','left',1),('r','right',-1)]:
        hand=arm.data.edit_bones['hand_'+side];frame=oriented(Vector((sign,0,0)),Vector((0,-1,0)));canonical[side]=frame
        for finger,(x,y,lengths,spread) in config.items():
            base=hand.head+frame@Vector((x,y,0));direction=(frame@Vector((spread,1,0))).normalized();parent=hand.name;chain=[]
            for k,length in enumerate(lengths,1):
                name=f'{finger}_{k:02d}_{side}';bone=arm.data.edit_bones.new(name);bone.head=base;bone.tail=base+direction*length;bone.parent=arm.data.edit_bones[parent];bone.use_connect=k>1;bone.use_deform=True
                definitions.append({'name':name,'parent':parent,'head':list(bone.head),'tail':list(bone.tail),'deform':True,'unity_role':None});chain.append(name);base=bone.tail.copy();parent=name
            source_ids=[idx[f'{full}-{finger}-{joint}'] for joint in ['third-joint','second-joint','first-joint','tip']]
            chains[side,finger]=(chain,source_ids)
    bpy.ops.object.mode_set(mode='OBJECT');spec['name']='MotionHumanoid52';spec['bones'].extend(definitions);data['bone_names'].extend(b['name'] for b in definitions)
    # Separate proxy in .blend; merged into the existing proxy only in FBX export memory.
    vertices=[];faces=[];groups=[]
    for b in definitions:
        head,tail=Vector(b['head']),Vector(b['tail']);axis=(tail-head).normalized();u=axis.cross(Vector((0,0,1))).normalized()*.006;v=axis.cross(u).normalized()*.006;mid=head.lerp(tail,.45);base=len(vertices)
        vertices.extend(map(tuple,[head,tail,mid+u,mid+v,mid-u,mid-v]))
        for k in range(4):a=base+2+k;c=base+2+(k+1)%4;faces.extend([(base,a,c),(base+1,c,a)])
        groups.append((b['name'],list(range(base,base+6))))
    mesh=bpy.data.meshes.new('FingerProxyMesh');mesh.from_pydata(vertices,[],faces);mesh.update();proxy=bpy.data.objects.new('FingerProxy',mesh);bpy.context.collection.objects.link(proxy);proxy.parent=arm;proxy.modifiers.new('FingerSkin','ARMATURE').object=arm
    for name,ids in groups:proxy.vertex_groups.new(name=name).add(ids,1,'REPLACE')
    oldmesh=bpy.data.objects['BoneProxy']
    if oldmesh.animation_data:proxy.animation_data_create();proxy.animation_data.action=oldmesh.animation_data.action
    previous={};segment=None;observed={b['name']:0 for b in definitions};body_error=0.;guard_events=[]
    axis_map=Matrix(((1,0,0),(0,0,1),(0,-1,0)))
    crop_counts={'l':0,'r':0}
    for i,row in enumerate(frames):
        bpy.context.scene.frame_set(i+1);key=(row.get('tracking_segment'),row.get('scene_index'))
        if key!=segment:previous={};segment=key
        solved={n:arm.pose.bones[n].matrix.copy() for n in original_names};baseline={n:solved[n].copy() for n in original_names}
        outputs=raw['frames'][i].get('outputs') or {};native=outputs.get('pred_keypoints_3d')
        directions={};finger_sources={};crop_sides=set()
        for (side,finger),(chain,ids) in chains.items():
            observation=hands[i].get(side);valid=observation is not None and native is not None and row['bone_status'][original_names.index('hand_'+side)]!='missing'
            choice=None if selection is None else selection['frames'][i]['hands'].get(side)
            use_crop=choice is not None and finger in choice['valid_fingers'] and row['bone_status'][original_names.index('hand_'+side)]!='missing'
            if use_crop:
                crop_points=[axis_map@Vector(p) for p in choice['world_joints']]
                f=('thumb','index','middle','ring','pinky').index(finger);pts=crop_points[1+f*4:5+f*4];edges=[b-a for a,b in zip(pts,pts[1:])]
                source_frame=oriented(crop_points[9]-crop_points[0],crop_points[5]-crop_points[17]);valid=True
            elif valid:
                pts=[axis_map@Vector(native[j]) for j in ids];edges=[b-a for a,b in zip(pts,pts[1:])]
                valid=all(all(math.isfinite(v) for v in p) for p in pts) and all(1e-5<e.length<.15 for e in edges)
            if valid:
                if not use_crop:source_frame=oriented(Vector(observation['forward']),Vector(observation['lateral']))
                hand=arm.pose.bones['hand_'+side];target_frame=hand.matrix.to_3x3()@hand.bone.matrix_local.to_3x3().transposed()@canonical[side]
                for name,edge in zip(chain,edges):directions[name]=target_frame@source_frame.transposed()@edge
                if use_crop:crop_sides.add(side)
            finger_sources[f'{finger}_{side}']='crop_model_shape' if use_crop else 'SAM' if valid else 'missing'
        for side in crop_sides:crop_counts[side]+=1
        row['finger_input_sources']=finger_sources
        frame_guards=[]
        for item in definitions:
            name=item['name'];parent=item['parent'];pb=arm.pose.bones[name];rest=pb.bone.matrix_local;parent_rest=arm.data.bones[parent].matrix_local
            anchor=solved[parent]@parent_rest.inverted()@rest;direction=directions.get(name)
            rotation=transport_roll(anchor.to_3x3(),direction) if direction is not None else anchor.to_3x3()
            desired=rotation.to_4x4();desired.translation=anchor.translation
            basis=pb.bone.convert_local_to_pose(desired,rest,parent_matrix=solved[parent],parent_matrix_local=parent_rest,invert=True);q=basis.to_quaternion().normalized()
            prior=previous.get(name)
            if prior is not None:
                if previous[name].dot(q)<0:q.negate()
                q=previous[name].slerp(q,1-math.exp(-1/(fps*.035)))
            curl=rest.to_3x3().transposed()@Vector((0,0,-1))
            limited,reasons=guard_rotation((q.x,q.y,q.z,q.w),tuple(curl),int(name.split('_')[1]),fps,
                None if prior is None else (prior.x,prior.y,prior.z,prior.w),name.startswith('thumb'))
            q=Quaternion((limited[3],limited[0],limited[1],limited[2]))
            if reasons:frame_guards.append({'bone':name,'reasons':reasons,'source_available':direction is not None})
            previous[name]=q.copy();pb.rotation_mode='QUATERNION';pb.location=(0,0,0);pb.scale=(1,1,1);pb.rotation_quaternion=q;pb.keyframe_insert('rotation_quaternion',frame=i+1,group=name)
            solved[name]=pb.bone.convert_local_to_pose(q.to_matrix().to_4x4(),rest,parent_matrix=solved[parent],parent_matrix_local=parent_rest)
            row['local_quaternions_wxyz'].append(list(q));row['local_locations_m'].append([0,0,0]);row['bone_status'].append('solved' if direction is not None else 'missing');observed[name]+=int(direction is not None)
        bpy.context.view_layer.update()
        for n in original_names:body_error=max(body_error,(arm.pose.bones[n].head-baseline[n].translation).length)
        guard_events.append({'frame_index':i,'corrections':frame_guards})
    # SLERP subkeys on finger curves only, with no interpolation across cuts/missing evidence.
    subframe_guard_adjustments=0
    for i in range(len(frames)-1):
        a,b=frames[i:i+2]
        for j,name in enumerate(data['bone_names'][22:],22):
            connected=(a['tracking_segment'],a['scene_index'])==(b['tracking_segment'],b['scene_index']) and a['bone_status'][j]==b['bone_status'][j]=='solved'
            if not connected:continue
            qa,qb=Quaternion(a['local_quaternions_wxyz'][j]),Quaternion(b['local_quaternions_wxyz'][j]);pb=arm.pose.bones[name]
            curl=pb.bone.matrix_local.to_3x3().transposed()@Vector((0,0,-1))
            for t in [.25,.5,.75]:
                q=qa.slerp(qb,t)
                limited,reasons=guard_rotation((q.x,q.y,q.z,q.w),tuple(curl),int(name.split('_')[1]),fps*4,None,name.startswith('thumb'))
                subframe_guard_adjustments+=bool(reasons)
                pb.rotation_quaternion=Quaternion((limited[3],limited[0],limited[1],limited[2]));pb.keyframe_insert('rotation_quaternion',frame=i+1+t,group=name)
    finger_paths={f'pose.bones["{b["name"]}"].rotation_quaternion':22+k for k,b in enumerate(definitions)}
    for layer in arm.animation_data.action.layers:
        for strip in layer.strips:
            for slot in arm.animation_data.action.slots:
                bag=strip.channelbag(slot)
                if bag:
                    for curve in bag.fcurves:
                        if curve.data_path not in finger_paths:continue
                        j=finger_paths[curve.data_path]
                        for point in curve.keyframe_points:
                            i=int(math.floor(point.co.x+1e-6))-1
                            valid=0<=i<len(frames)-1 and frames[i]['bone_status'][j]==frames[i+1]['bone_status'][j]=='solved' and (frames[i]['tracking_segment'],frames[i]['scene_index'])==(frames[i+1]['tracking_segment'],frames[i+1]['scene_index'])
                            point.interpolation='LINEAR' if valid else 'CONSTANT'
    if len(arm.data.bones)!=52 or body_error>1e-5:raise ValueError('Finger extension changed body geometry.')
    data['finger_policy']={'revision':3,'observed_frames':observed,'source':'SAM_with_selected_crop_shapes' if selection is not None else 'native_SAM_MHR70','crop_hand_frames_applied':crop_counts,'crop_transfer':'palm_relative_finger_directions_only_no_world_position_merge','fixed_reference_finger_lengths':True,'missing':'parent_rest_fallback_not_reconstruction','anatomical_limits_verified':False,'max_original_body_head_change_m':body_error,
        'rotation_guard':{'kind':'conservative_reference_priors_not_measured_anatomy','segment_flexion_spread_degrees':LIMITS,'thumb_swing_cone_degrees':115,
            'angular_speed_soft_limit_degrees_per_second':720,'thumb_angular_speed_soft_limit_degrees_per_second':1080,'joint_range_takes_precedence':True},
        'guard_frames':guard_events,'subframe_guard_adjustments':subframe_guard_adjustments}
    data['orientation_policy']['missing_spans']=missing_spans(frames,data['bone_names'],fps)
    data['limits'].extend(['finger_positions_are_model_estimates','no_grip_or_anatomical_limit_solver','finger_skin_twist_unobserved'])
    out.mkdir(exist_ok=False);bpy.context.scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'animation.blend'));(out/'animation.json').write_text(json.dumps(data,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print('FINGERS_VERIFIED',52,body_error,flush=True)


if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:];run(*map(Path,args))
