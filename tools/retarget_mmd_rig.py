"""Profile-based FK transfer preserving an imported MMD deformation rig."""
import sys,json,math,hashlib
from pathlib import Path
import bpy
from mathutils import Matrix,Vector,Quaternion
sys.path.insert(0,str(Path(__file__).resolve().parent))
from hand_retarget import palm_frame,curl_axis,transfer_direction
from finger_limits import guard_rotation


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(model,source,profile_path,out):
    model,source,profile_path,out=map(lambda p:Path(p).resolve(),(model,source,profile_path,out))
    profile=json.loads(profile_path.read_text(encoding='utf-8'));mapping=profile['mapping'];hashes={str(p):digest(p) for p in (model,source,profile_path)}
    imported=json.loads(model.with_name('import.json').read_text(encoding='utf-8'))
    if imported['source_sha256']!=profile['pmx_sha256']:raise ValueError('Model profile hash differs')
    out.mkdir(parents=True,exist_ok=False);bpy.ops.wm.open_mainfile(filepath=str(model))
    arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
    with bpy.data.libraries.load(str(source),link=False) as (a,b):b.objects=['MotionSkeleton']
    src=b.objects[0];bpy.context.collection.objects.link(src);src.hide_set(True);src.hide_render=True
    assert all(t in arm.pose.bones and row['source'] in src.pose.bones for t,row in mapping.items())
    hand_frames={};hand_local=profile.get('hand_transfer')=='palm_local_bends_v1'
    if hand_local:
        for side,jp in [('l','左'),('r','右')]:
            hand_frames[side]=(palm_frame(src,'hand_'+side,'index_01_'+side,'middle_01_'+side,'pinky_01_'+side),palm_frame(arm,jp+'手首',jp+'人指１',jp+'中指１',jp+'小指１'))
    original_constraints={(p.name,c.name):(c.type,c.mute,c.influence) for p in arm.pose.bones for c in p.constraints};muted=[]
    for name in profile['fk_legs']:
        for c in arm.pose.bones[name].constraints:
            if c.type=='IK' or c.name=='mmd_ik_limit_override':c.mute=True;muted.append([name,c.name])
    for p in arm.pose.bones:p.rotation_mode='QUATERNION'
    arm.animation_data_clear();calibration={};groups={}
    for target,row in mapping.items():
        pb=arm.pose.bones[target];tr=pb.bone.matrix_local.to_3x3();sr=src.data.bones[row['source']].matrix_local.to_3x3()
        align=tr.col[1].normalized().rotation_difference(sr.col[1].normalized()).to_matrix() if row['mode']=='direction' else Matrix.Identity(3)
        calibration[target]=sr.transposed()@align@tr
        if hand_local and row['source'].startswith('hand_'):
            source_palm,target_palm=hand_frames[row['source'][-1]]
            calibration[target]=sr.transposed()@source_palm@target_palm.transposed()@tr
        depth=0;parent=pb.parent
        while parent is not None:depth+=1;parent=parent.parent
        groups.setdefault(depth,[]).append(target)
    scene=bpy.context.scene;data=json.loads(source.with_name('animation.json').read_text(encoding='utf-8'));fps=float(data['fps']);scene.render.fps=round(fps);scene.render.fps_base=round(fps)/fps;scene.frame_start=1;scene.frame_end=len(data['frames'])
    scale=arm.data.bones['下半身'].head_local.z/src.data.bones['pelvis'].head_local.z
    root=arm.pose.bones['全ての親'];previous={};max_error=0.;errors={};finger_checks={};hand_events=[];scene_key=None
    for i in range(scene.frame_end):
        scene.frame_set(i+1)
        frame_data=data['frames'][i];key=(frame_data.get('tracking_segment'),frame_data.get('scene_index'))
        if key!=scene_key:previous={};scene_key=key
        source_root=src.pose.bones['root'];source_root_rest=src.data.bones['root'].matrix_local
        source_delta=source_root.matrix@source_root_rest.inverted()
        offset=src.pose.bones['pelvis'].head-source_delta@src.data.bones['pelvis'].head_local
        desired_root=(source_delta.to_3x3()@root.bone.matrix_local.to_3x3()).to_4x4()
        desired_root.translation=root.bone.head_local+(source_delta.translation+offset)*scale
        root_basis=root.bone.convert_local_to_pose(desired_root,root.bone.matrix_local,invert=True)
        root.location=root_basis.translation;root.rotation_quaternion=root_basis.to_quaternion()
        root.keyframe_insert('location',frame=i+1);root.keyframe_insert('rotation_quaternion',frame=i+1);bpy.context.view_layer.update()
        desired_rotations={}
        for depth in sorted(groups):
            for target in groups[depth]:
                pb=arm.pose.bones[target];rest=pb.bone.matrix_local;parent=pb.parent
                parent_matrix=Matrix.Identity(4) if parent is None else parent.matrix.copy();parent_rest=Matrix.Identity(4) if parent is None else parent.bone.matrix_local
                anchor=rest.copy() if parent is None else parent_matrix@parent_rest.inverted()@rest
                source_name=mapping[target]['source']
                if hand_local and source_name.startswith(('thumb_','index_','middle_','ring_','pinky_')):
                    side=source_name[-1];segment=int(source_name.split('_')[1]);source_palm,target_palm=hand_frames[side]
                    source_curl=curl_axis(src.data.bones[source_name].matrix_local,source_palm,side);target_curl=curl_axis(rest,target_palm,side)
                    direction=transfer_direction(src.pose.bones[source_name].rotation_quaternion,source_curl,target_curl)
                    q=Vector((0,1,0)).rotation_difference(direction)
                    prior=previous.get(target)
                    limited,reasons=guard_rotation((q.x,q.y,q.z,q.w),tuple(target_curl),segment,fps,None if prior is None else (prior.x,prior.y,prior.z,prior.w),source_name.startswith('thumb_'))
                    q=Quaternion((limited[3],limited[0],limited[1],limited[2]))
                    if prior is not None and q.dot(prior)<0:q.negate()
                    previous[target]=q.copy();pb.rotation_quaternion=q;pb.keyframe_insert('rotation_quaternion',frame=i+1,group=target)
                    error=math.degrees((q@Vector((0,1,0))).angle(direction));finger_checks[target]=max(finger_checks.get(target,0),error)
                    if reasons:hand_events.append({'frame':i,'bone':target,'reasons':reasons})
                    continue
                reference=src.pose.bones[mapping[target]['source']].matrix.to_3x3().normalized()
                if mapping[target]['mode']=='swing':
                    # A clavicle's axial roll is unobserved; do not spin attached garments.
                    anchored=anchor.to_3x3().normalized()
                    rotation=anchored.col[1].normalized().rotation_difference(reference.col[1]).to_matrix()@anchored
                else:rotation=reference@calibration[target]
                desired_rotations[target]=rotation
                desired=rotation.to_4x4();desired.translation=anchor.translation
                basis=pb.bone.convert_local_to_pose(desired,rest,parent_matrix=parent_matrix,parent_matrix_local=parent_rest,invert=True)
                q=basis.to_quaternion().normalized()
                if target in previous and q.dot(previous[target])<0:q.negate()
                twist_target=profile.get('twist_controls',{}).get(target)
                if twist_target is not None:
                    q,angle=q.to_swing_twist('Y')
                    twist=arm.pose.bones[twist_target];twist.rotation_quaternion=Quaternion((0,1,0),angle)
                    twist.keyframe_insert('rotation_quaternion',frame=i+1,group=twist_target)
                previous[target]=q.copy();pb.rotation_quaternion=q;pb.keyframe_insert('rotation_quaternion',frame=i+1,group=target)
            bpy.context.view_layer.update()
        for target,rotation in desired_rotations.items():
            actual=arm.pose.bones[target].matrix.to_quaternion()
            if target in profile.get('twist_controls',{}):angle=math.degrees((actual@Vector((0,1,0))).angle(rotation.col[1]))
            else:angle=math.degrees(actual.rotation_difference(rotation.to_quaternion()).angle);angle=min(angle,360-angle)
            errors[target]=max(errors.get(target,0),angle)
        for pb in arm.pose.bones:
            assert all(math.isfinite(v) for row in pb.matrix for v in row)
            max_error=max(max_error,abs((pb.tail-pb.head).length-pb.bone.length))
        if i%50==0:print('MMD_FRAME',i,scene.frame_end,flush=True)
    for layer in arm.animation_data.action.layers:
        for strip in layer.strips:
            for slot in arm.animation_data.action.slots:
                bag=strip.channelbag(slot)
                if bag:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:key.interpolation='LINEAR'
    remaining={(p.name,c.name):(c.type,c.mute,c.influence) for p in arm.pose.bones for c in p.constraints}
    assert remaining.keys()==original_constraints.keys()
    for key,value in original_constraints.items():
        if list(key) not in muted:assert remaining[key]==value
    assert max(errors.values())<.2,errors
    assert max_error<1e-4,max_error
    bpy.data.objects.remove(src,do_unlink=True);scene.frame_set(1)
    arm.hide_set(True);meshes=[o for o in scene.objects if o.type=='MESH']
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                v=area.spaces.active;v.region_3d.view_location=(0,0,1);v.region_3d.view_distance=3;v.region_3d.view_rotation=Vector((0,-1,.15)).to_track_quat('Z','Y');v.shading.type='SOLID';v.shading.color_type='TEXTURE'
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'animation.blend'))
    assert all(digest(p)==h for p,h in hashes.items())
    report={'status':'completed','model_profile':str(profile_path),'input_sha256':hashes,'hand_transfer':profile.get('hand_transfer','legacy_world_directions'),'finger_direction_errors_degrees':finger_checks,'finger_guard_events':hand_events,'frames':scene.frame_end,'fps':fps,'mapped_primary_bones':len(mapping),'constraint_count':len(remaining),'muted_for_FK':muted,'other_constraints_preserved':True,'bone_rest_and_weights_unchanged':True,'root_motion_scale':scale,'max_bone_length_error_m':max_error,'max_orientation_error_degrees':errors,'limitations':['no_clothing_collision_simulation','face_and_hair_have_no_observations','reference_motion_is_estimated_not_ground_truth','no_object_contact_or_grip_solver']}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('MMD_RIG_PASS',len(mapping),len(remaining),max(errors.values()),flush=True)


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
