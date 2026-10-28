"""Fit the supplied Artorias sword to a canonical humanoid's actual palms.

Preserve the clip's body/feet, repair distal deformation-helper twist, and bake
bounded wrist/arm contact plus model-sized finger capsule fits into a new file.
"""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Matrix,Vector,Quaternion
sys.path.insert(0,str(Path(__file__).resolve().parent))
from grip_sword import solve_finger,set_world
from hand_retarget import palm_frame
from grip_stability import limit_wrist
from adaptive_deform import pose as pose_helpers


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def reach(arm,side,target):
    a,b,c=[arm.pose.bones[f'{n}_{side}'] for n in ('upperarm','lowerarm','hand')]
    start,joint,end=[p.head.copy() for p in (a,b,c)]
    la,lb=(joint-start).length,(end-joint).length;v=target-start;distance=v.length
    if distance<1e-8:return False
    distance=max(abs(la-lb)+.0001,min(la+lb-.0001,distance));direction=v.normalized()
    target=start+direction*distance;pole=joint-start-direction*(joint-start).dot(direction)
    if pole.length<1e-6:pole=a.matrix.to_3x3().col[0]-direction*a.matrix.to_3x3().col[0].dot(direction)
    if pole.length<1e-6:return False
    along=(la*la-lb*lb+distance*distance)/(2*distance)
    wanted=start+direction*along+pole.normalized()*math.sqrt(max(0,la*la-along*along))
    old_a=a.matrix.to_3x3().normalized();old_b=b.matrix.to_3x3().normalized()
    set_world(arm,a,(joint-start).normalized().rotation_difference((wanted-start).normalized()).to_matrix()@old_a)
    set_world(arm,b,(end-joint).normalized().rotation_difference((target-wanted).normalized()).to_matrix()@old_b)
    return (c.head-target).length<.003


def wrist_world(arm,side,palm,world_palm,prior,fps):
    pb=arm.pose.bones['hand_'+side]
    set_world(arm,pb,world_palm@palm.transposed()@pb.bone.matrix_local.to_3x3())
    q=limit_wrist(pb.rotation_quaternion,50,65)
    if prior is not None:
        if prior.dot(q)<0:q.negate()
        angle=prior.rotation_difference(q).angle;angle=min(angle,2*math.pi-angle)
        q=prior.slerp(q,min(1.,math.radians(240)/fps/max(angle,1e-8)))
    pb.rotation_quaternion=q;bpy.context.view_layer.update()
    return q.copy()


def run(source,obj,textures,output):
    source,obj,textures,output=map(lambda p:Path(p).resolve(),(source,obj,textures,output))
    if output.exists():raise FileExistsError(output)
    output.mkdir(parents=True)
    inputs={str(p):digest(p) for p in [source,obj,*textures.glob('*.jpg')]}
    bpy.ops.wm.open_mainfile(filepath=str(source));scene=bpy.context.scene
    arm=next(o for o in scene.objects if o.type=='ARMATURE');fps=scene.render.fps/scene.render.fps_base
    palms={s:palm_frame(arm,*[f'{n}_{s}' for n in ('hand','index_01','middle_01','pinky_01')]) for s in ('l','r')}
    widths={s:(arm.data.bones['index_01_'+s].head_local-arm.data.bones['pinky_01_'+s].head_local).length for s in palms}
    lengths={s:(arm.data.bones['middle_01_'+s].head_local-arm.data.bones['hand_'+s].head_local).length for s in palms}
    # Original OBJ has no declared physical units. Uniform scale is inferred
    # from the two actual palm widths and the inspected straight handle span.
    handle_raw=3.88;scale=max(1.5/24.9443,(sum(widths.values())+.035)/handle_raw)
    radius=.118*scale;grip_distance=(sum(widths.values())*.5+.012)
    basis=Matrix(((.889284551,-.457354334,0),(0,0,1),(-.457354334,-.889284551,0)))
    origin=Vector((0,-.56025,-5.85-widths['r']/(2*scale)-.12))
    before=set(scene.objects);bpy.ops.wm.obj_import(filepath=str(obj))
    objects=[o for o in scene.objects if o not in before and o.type=='MESH']
    if len(objects)!=1:raise ValueError('Expected one sword mesh')
    sword=objects[0];sword.name='GripSword'
    for v in sword.data.vertices:v.co=(basis@v.co-origin)*scale
    sword.matrix_world=Matrix.Identity(4)
    material=bpy.data.materials.new('ArtoriasSword');material.use_nodes=True
    node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(textures/'DefaultMaterial_albedo.jpg'));node.image.pack()
    material.node_tree.nodes.active=node;material.node_tree.links.new(node.outputs['Color'],material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    sword.data.materials.clear();sword.data.materials.append(material)
    offsets={};finger_poses={};contact={}
    for side in palms:
        palm=palms[side];curl=palm.col[2]*(-1 if side=='l' else 1)
        offsets[side]=palm.col[1]*lengths[side]*.8+curl*radius*1.4
        center=arm.data.bones['hand_'+side].head_local+offsets[side]
        finger_poses[side]={};contact[side]={}
        for finger in ('thumb','index','middle','ring','pinky'):
            names=[f'{finger}_{i:02d}_{side}' for i in range(1,4)]
            qs,stats=solve_finger(arm,names,palm,side,center,radius,finger=='thumb',
                pad=max(.006,widths[side]*.055),index_bone='index_01_'+side)
            contact[side][finger]=stats
            for n,q in zip(names,qs):finger_poses[side][n]=q
        print('FINGER_FIT',side,contact[side],flush=True)
    arm_names=[f'{n}_{s}' for s in palms for n in ('upperarm','lowerarm','hand')]
    fixed=[n for n in arm.pose.bones.keys() if n not in arm_names and
        not any(p.name in arm_names for p in arm.pose.bones[n].parent_recursive)]
    baseline=[]
    for f in range(scene.frame_start,scene.frame_end+1):
        scene.frame_set(f);baseline.append({n:arm.pose.bones[n].matrix.copy() for n in fixed})
    prior_axis=None;prior_wrist={};rows=[];protected_error=0.;endpoint_before=0.;endpoint_after=0.
    helpers=json.loads(arm.get('motion_deform_helpers','[]'))
    distal={}
    for r in helpers:
        if r['parent'] not in distal or distal[r['parent']]['center']<r['center']:distal[r['parent']]=r
    # Helper matrices intentionally change; they are skin influences, not body joints.
    fixed=[n for n in fixed if n not in {r['name'] for r in helpers}]
    for index,f in enumerate(range(scene.frame_start,scene.frame_end+1)):
        scene.frame_set(f)
        original={s:arm.pose.bones['hand_'+s].head.copy() for s in palms}
        axis=original['r']-original['l']
        if axis.length<.015:axis=arm.pose.bones['hand_r'].matrix.to_3x3()@arm.data.bones['hand_r'].matrix_local.to_3x3().transposed()@palms['r'].col[0]
        axis.normalize()
        if prior_axis is not None:
            turn=prior_axis.rotation_difference(axis);angle=turn.angle
            axis=Quaternion().slerp(turn,min(1.,math.radians(360)/fps/max(angle,1e-8)))@prior_axis
        prior_axis=axis.copy();world_palms={}
        for side in ('r','l'):
            hand=arm.pose.bones['hand_'+side];parent=hand.parent
            neutral=(parent.matrix@parent.bone.matrix_local.inverted()@hand.bone.matrix_local).to_3x3()@hand.bone.matrix_local.to_3x3().transposed()@palms[side]
            forward=neutral.col[1]-axis*neutral.col[1].dot(axis)
            if forward.length<1e-5:forward=axis.cross(Vector((0,0,1)))
            forward.normalize();world_palms[side]=Matrix((axis,forward,axis.cross(forward))).transposed()
        # Iterate contact positions with the bounded wrist orientations.
        for _ in range(4):
            actual={};off={}
            for side in ('r','l'):
                wrist_world(arm,side,palms[side],world_palms[side],prior_wrist.get(side),fps)
                hand=arm.pose.bones['hand_'+side]
                rotation=hand.matrix.to_3x3()@hand.bone.matrix_local.to_3x3().transposed()
                actual[side]=rotation@palms[side];off[side]=rotation@offsets[side]
            current_axis=actual['r'].col[0].normalized()
            rw=arm.pose.bones['hand_r'].head;lw=arm.pose.bones['hand_l'].head
            midpoint=(rw+off['r']+lw+off['l'])*.5
            targets={'r':midpoint+current_axis*grip_distance*.5-off['r'],
                     'l':midpoint-current_axis*grip_distance*.5-off['l']}
            for side in ('r','l'):
                delta=targets[side]-original[side]
                if delta.length>.12:targets[side]=original[side]+delta.normalized()*.12
                reach(arm,side,targets[side])
        for side in ('r','l'):
            prior_wrist[side]=wrist_world(arm,side,palms[side],world_palms[side],prior_wrist.get(side),fps)
            for n,q in finger_poses[side].items():
                arm.pose.bones[n].rotation_mode='QUATERNION';arm.pose.bones[n].rotation_quaternion=q
                arm.pose.bones[n].keyframe_insert('rotation_quaternion',frame=f,group=n)
        bpy.context.view_layer.update()
        for r in distal.values():endpoint_before=max(endpoint_before,math.degrees(arm.pose.bones[r['name']].rotation_quaternion.angle))
        pose_helpers(arm,f);bpy.context.view_layer.update()
        for r in distal.values():endpoint_after=max(endpoint_after,math.degrees(arm.pose.bones[r['name']].rotation_quaternion.angle))
        right=arm.pose.bones['hand_r'];rot=right.matrix.to_3x3()@right.bone.matrix_local.to_3x3().transposed()
        palm=rot@palms['r'];center=right.head+rot@offsets['r'];shaft=palm.col[0].normalized()
        transform=Matrix((palm.col[1],palm.col[2],shaft)).transposed().to_4x4();transform.translation=center
        sword.matrix_world=transform;sword.rotation_mode='QUATERNION'
        sword.keyframe_insert('location',frame=f);sword.keyframe_insert('rotation_quaternion',frame=f)
        left=arm.pose.bones['hand_l'];left_rot=left.matrix.to_3x3()@left.bone.matrix_local.to_3x3().transposed()
        error=(left.head+left_rot@offsets['l']-(center-shaft*grip_distance)).length
        for n in arm_names:
            arm.pose.bones[n].keyframe_insert('rotation_quaternion',frame=f,group=n)
        for n in fixed:
            protected_error=max(protected_error,max(abs(arm.pose.bones[n].matrix[a][b]-baseline[index][n][a][b]) for a in range(4) for b in range(4)))
        rows.append({'frame':f,'support_center_error_m':error,'wrist_shift_m':{s:(arm.pose.bones['hand_'+s].head-original[s]).length for s in palms}})
        if index%100==0:print('SWORD_GRIP_FRAME',f,error,flush=True)
    assert protected_error<1e-5,protected_error
    assert endpoint_after<.001,endpoint_after
    scene.frame_set(1);world=sword.matrix_world.copy();sword.animation_data_clear()
    sword.parent=arm;sword.parent_type='BONE';sword.parent_bone='hand_r';bpy.context.view_layer.update();sword.matrix_world=world
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(output/'animation.blend'))
    assert all(digest(p)==value for p,value in inputs.items())
    report={'status':'completed','frames':scene.frame_end,'fps':fps,'source_sha256':inputs[str(source)],
        'input_sha256':inputs,'finger_contact_approximation':contact,'shaft_radius_m':radius,
        'estimated_sword_length_m':24.9443*scale,'grip_distance_m':grip_distance,
        'support_contact_frames':sum(r['support_center_error_m']<.025 for r in rows),
        'distal_helper_twist_before_degrees':endpoint_before,'distal_helper_twist_after_degrees':endpoint_after,
        'protected_body_and_feet_max_matrix_error':protected_error,'frame_results':rows,
        'limits':['Finger fit uses bone capsules; not exact mesh collision','Sword uniform scale inferred from this model palms',
            'Contact can relax to preserve wrist and arm reach limits','No weapon pose inference from video']}
    (output/'grip-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('HUMANOID_GRIP_READY',report['support_contact_frames'],report['frames'],flush=True)


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
