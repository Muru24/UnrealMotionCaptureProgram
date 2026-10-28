"""Model-specific two-hand sword grip bake; explicit capsule contact approximation."""
import sys,json,math,hashlib
from pathlib import Path
import bpy
from mathutils import Matrix,Vector,Quaternion
sys.path.insert(0,str(Path(__file__).resolve().parent))
from hand_retarget import palm_frame,curl_axis
from grip_stability import smooth_quaternions,limit_wrist


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def joint_q(curl,flex,spread):
    f,a=map(math.radians,(flex,spread));y=Vector((0,1,0));s=curl.cross(y).normalized()
    d=math.cos(a)*(math.cos(f)*y+math.sin(f)*curl)+math.sin(a)*s
    return y.rotation_difference(d)


def solve_finger(arm,names,palm,side,center,radius,thumb=False,pad=.006,index_bone=None):
    bones=[arm.data.bones[n] for n in names];curls=[curl_axis(b.matrix_local,palm,side) for b in bones]
    axial=palm.col[0];forward=palm.col[1];curl=palm.col[2]*(-1 if side=='l' else 1)
    # Tip contact lies on the opposite sides for thumb opposition and four fingers.
    along=(bones[0].head_local-center).dot(axial)
    if thumb:along=(arm.data.bones[index_bone or ('左' if side=='l' else '右')+'人指１'].head_local-center).dot(axial)
    target=center+axial*along+forward*(radius+pad)*(.9 if thumb else -.8)+curl*(radius+pad)*(-.435 if thumb else .6)
    bounds=[(-90,110),(-85,85),(-40,110),(-50,50),(-25,90),(-25,25)] if thumb else [(-20,100),(-35,35),(-10,110),(-12,12),(-10,90),(-10,10)]
    initial=[35,0,75,0,55,0]
    def chain(params):
        parent=bones[0].parent.matrix_local;parent_rest=parent;points=[bones[0].head_local.copy()];quats=[]
        for k,b in enumerate(bones):
            q=joint_q(curls[k],params[k*2],params[k*2+1]);m=parent@parent_rest.inverted()@b.matrix_local@q.to_matrix().to_4x4()
            points.append(m@Vector((0,b.length,0)));parent=m;parent_rest=b.matrix_local;quats.append(q)
        return points,quats
    def evaluate(params,details=False):
        points,qs=chain(params);pen=0.;worst=0.
        for a,b in zip(points,points[1:]):
            for t in (.25,.5,.75,1.):
                p=a.lerp(b,t)-center;distance=(p-axial*p.dot(axial)).length
                overlap=max(0,radius+pad*.65-distance);pen+=overlap**2;worst=max(worst,overlap)
        tip=points[-1]-center;tip_distance=(tip-axial*tip.dot(axial)).length
        loss=(points[-1]-target).length_squared+pen*20+sum((a-b)**2 for a,b in zip(params,initial))*1e-9
        return (loss,qs,abs(tip_distance-radius-pad),worst) if details else loss
    best=None
    for start in [initial,[65,0,90,0,65,0],[15,25,50,0,30,0],[-15,-35,60,0,45,0]]:
        p=start[:];score=evaluate(p)
        for step in [25,12,6,3,1,.5]:
            for _ in range(5):
                improved=False
                for k,(lo,hi) in enumerate(bounds):
                    for delta in [-step,step]:
                        trial=p[:];trial[k]=max(lo,min(hi,p[k]+delta));v=evaluate(trial)
                        if v<score:p=trial;score=v;improved=True
                if not improved:break
        if best is None or score<best[0]:best=(score,p)
    loss,qs,gap,overlap=evaluate(best[1],True)
    return qs,{'tip_surface_gap_m':gap,'max_capsule_overlap_m':overlap,'angles_degrees':best[1],'approximate_contact':gap<.006 and overlap<.003}


def set_world(arm,pb,rotation):
    parent=pb.parent;rest=pb.bone.matrix_local;pm=Matrix.Identity(4) if parent is None else parent.matrix.copy();pr=Matrix.Identity(4) if parent is None else parent.bone.matrix_local
    desired=rotation.to_4x4();desired.translation=(rest if parent is None else pm@pr.inverted()@rest).translation
    q=pb.bone.convert_local_to_pose(desired,rest,parent_matrix=pm,parent_matrix_local=pr,invert=True).to_quaternion().normalized()
    if q.dot(pb.rotation_quaternion)<0:q.negate()
    pb.rotation_quaternion=q;bpy.context.view_layer.update()


def reach(arm,target,jp):
    upper=arm.pose.bones[jp+'腕'];lower=arm.pose.bones[jp+'ひじ'];wrist=arm.pose.bones[jp+'手首']
    s,e,w=[p.head.copy() for p in (upper,lower,wrist)];a=(e-s).length;b=(w-e).length;direction=target-s;distance=direction.length
    if distance<abs(a-b)+.0001 or distance>a+b-.0001:return False
    y=direction.normalized();pole=e-s-y*(e-s).dot(y)
    if pole.length<1e-6:pole=upper.matrix.to_3x3().col[0]-y*upper.matrix.to_3x3().col[0].dot(y)
    along=(a*a-b*b+distance*distance)/(2*distance);new_e=s+y*along+pole.normalized()*math.sqrt(max(0,a*a-along*along))
    old_lower=lower.matrix.to_3x3().normalized();old_upper=upper.matrix.to_3x3().normalized()
    rotation=(e-s).normalized().rotation_difference((new_e-s).normalized()).to_matrix()@old_upper;set_world(arm,upper,rotation)
    rotation=(w-e).normalized().rotation_difference((target-new_e).normalized()).to_matrix()@old_lower;set_world(arm,lower,rotation)
    return (wrist.head-target).length<.003


def run(source,obj_path,textures,out,raw_path=None):
    source,obj_path,textures,out=map(lambda p:Path(p).resolve(),(source,obj_path,textures,out));out.mkdir(parents=True,exist_ok=False)
    inputs={str(p):digest(p) for p in [source,obj_path,*textures.glob('*.jpg')]}
    raw=None if raw_path is None else json.loads(Path(raw_path).read_text(encoding='utf-8'))
    if raw_path is not None:inputs[str(Path(raw_path).resolve())]=digest(raw_path)
    bpy.ops.wm.open_mainfile(filepath=str(source));arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');scene=bpy.context.scene
    baseline=arm.copy();baseline.data=arm.data.copy();baseline.animation_data.action=arm.animation_data.action.copy();bpy.context.collection.objects.link(baseline)
    for pb in baseline.pose.bones:
        for c in pb.constraints:
            if getattr(c,'target',None)==arm:c.target=baseline
            if getattr(c,'pole_target',None)==arm:c.pole_target=baseline
    baseline.hide_set(True);baseline.hide_render=True
    assert baseline.animation_data.action!=arm.animation_data.action
    stable_names=['左腕','左ひじ','右腕','右ひじ','左腕捩','右腕捩','左手捩','右手捩']
    fps=scene.render.fps/scene.render.fps_base;tracks={n:[] for n in stable_names}
    for f in range(1,scene.frame_end+1):
        scene.frame_set(f)
        for n in stable_names:tracks[n].append(baseline.pose.bones[n].rotation_quaternion.copy())
    for n,values in tracks.items():
        for f,q in enumerate(smooth_quaternions(values,fps,.065,300),1):
            baseline.pose.bones[n].rotation_quaternion=q;baseline.pose.bones[n].keyframe_insert('rotation_quaternion',frame=f,group=n)
    palms={side:palm_frame(arm,jp+'手首',jp+'人指１',jp+'中指１',jp+'小指１') for side,jp in [('l','左'),('r','右')]}
    # OBJ geometry was inspected: long blade lies on this diagonal; shaft center is z=-7.358.
    basis=Matrix(((.889284551,-.457354334,0),(0,0,1),(-.457354334,-.889284551,0)))
    before=set(bpy.data.objects);bpy.ops.wm.obj_import(filepath=str(obj_path));objects=[o for o in bpy.data.objects if o not in before and o.type=='MESH']
    if len(objects)!=1:raise ValueError('Expected one sword mesh')
    sword=objects[0];sword.name='GripSword';scale=1.5/24.94430095;slot=-6.5
    origin=Vector((0,-.56025,slot))
    for v in sword.data.vertices:v.co=(basis@v.co-origin)*scale
    sword.matrix_world=Matrix.Identity(4);radius=.118*scale
    mat=bpy.data.materials.new('ArtoriasSwordTexture');mat.use_nodes=True;nodes=mat.node_tree.nodes;tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(textures/'DefaultMaterial_albedo.jpg'));tex.image.pack();nodes.active=tex;mat.node_tree.links.new(tex.outputs['Color'],nodes.get('Principled BSDF').inputs['Base Color']);nodes.get('Principled BSDF').inputs['Metallic'].default_value=.8;sword.data.materials.clear();sword.data.materials.append(mat)
    poses={};contact={};offsets={};names_by_side={}
    for side,jp in [('l','左'),('r','右')]:
        palm=palms[side];curl=palm.col[2]*(-1 if side=='l' else 1);offset=palm.col[1]*.065+curl*.016;offsets[side]=offset
        center=arm.data.bones[jp+'手首'].head_local+offset;poses[side]={};contact[side]={};names_by_side[side]=[]
        for finger,prefix in [('thumb','親指'),('index','人指'),('middle','中指'),('ring','薬指'),('pinky','小指')]:
            names=[jp+prefix+k for k in ('０１２' if finger=='thumb' else '１２３')];qs,stats=solve_finger(arm,names,palm,side,center,radius,finger=='thumb');contact[side][finger]=stats
            for name,q in zip(names,qs):poses[side][name]=q;names_by_side[side].append(name)
    rows=[];prior_axis=None;prior_sword=None;prior_forwards={};prior_wrists={};prior_midpoint=None;fps=scene.render.fps/scene.render.fps_base
    times=[1+k/4 for k in range((scene.frame_end-1)*4+1)]
    animated=['左腕','左ひじ','右腕','右ひじ','左手首','右手首','左腕捩','右腕捩','左手捩','右手捩',*poses['l'],*poses['r']]
    for frame in times:
        scene.frame_set(int(frame),subframe=frame%1)
        for name in animated:arm.pose.bones[name].rotation_quaternion=baseline.pose.bones[name].rotation_quaternion.copy()
        bpy.context.view_layer.update();right=arm.pose.bones['右手首'];left=arm.pose.bones['左手首'];rw=right.head.copy();lw=left.head.copy();separation=(rw-lw).length
        rp=right.matrix.to_3x3()@right.bone.matrix_local.to_3x3().transposed()@palms['r']
        axis=(rw-lw).normalized() if separation>.04 else rp.col[0].normalized()
        if raw is not None:
            i=int(frame)-1;t=frame%1;pixels=(raw['frames'][i].get('outputs') or {}).get('pred_keypoints_2d');next_pixels=(raw['frames'][min(i+1,len(raw['frames'])-1)].get('outputs') or {}).get('pred_keypoints_2d')
            if pixels:
                dx=pixels[41][0]-pixels[62][0];dz=pixels[62][1]-pixels[41][1];length=math.hypot(dx,dz)
                if next_pixels:
                    dx=dx*(1-t)+(next_pixels[41][0]-next_pixels[62][0])*t;dz=dz*(1-t)+(next_pixels[62][1]-next_pixels[41][1])*t;length=math.hypot(dx,dz)
                if math.isfinite(length) and length>6:
                    depth=max(-.35,min(.35,axis.y));planar=math.sqrt(1-depth*depth);axis=Vector((dx/length*planar,depth,dz/length*planar))
        if prior_axis is not None:
            # A blade direction is signed; flipping it like a quaternion reverses the sword.
            delta=prior_axis.rotation_difference(axis);angle=delta.angle
            factor=min(1-math.exp(-1/(fps*4*.04)),math.radians(720)/(fps*4)/max(angle,1e-6))
            axis=Quaternion().slerp(delta,factor)@prior_axis
        neutral={}
        for side,jp in [('r','右'),('l','左')]:
            pb=arm.pose.bones[jp+'手首'];parent=pb.parent
            anchor=parent.matrix@parent.bone.matrix_local.inverted()@pb.bone.matrix_local
            neutral[side]=anchor.to_3x3().normalized()@pb.bone.matrix_local.to_3x3().transposed()@palms[side]
        # A shaft nearly parallel to the forearm would require an excessive wrist bend.
        for _ in range(3):
            for p in neutral.values():
                f=p.col[1].normalized();dot=axis.dot(f);bound=math.sin(math.radians(30))
                if abs(dot)>bound:
                    perpendicular=axis-f*dot
                    if perpendicular.length>1e-5:axis=perpendicular.normalized()*math.sqrt(1-bound*bound)+f*math.copysign(bound,dot)
        axis.normalize();prior_axis=axis.copy();world_palms={};world_offsets={}
        for side,jp in [('r','右'),('l','左')]:
            f=neutral[side].col[1]-axis*neutral[side].col[1].dot(axis)
            if f.length<1e-4:f=neutral[side].col[2]-axis*neutral[side].col[2].dot(axis)
            f.normalize()
            if side in prior_forwards:
                old=prior_forwards[side]-axis*prior_forwards[side].dot(axis)
                if old.length>1e-4:
                    old.normalize();roll=math.atan2(axis.dot(old.cross(f)),old.dot(f));step=max(-math.radians(180)/(fps*4),min(math.radians(180)/(fps*4),roll*(1-math.exp(-1/(fps*4*.10)))));f=Quaternion(axis,step)@old
            prior_forwards[side]=f.copy();normal_side=axis.cross(f).normalized();world_palms[side]=Matrix((axis,f,normal_side)).transposed();world_offsets[side]=f*.065+normal_side*(.016 if side=='r' else -.016)
        world_palm=world_palms['r'];forward=world_palm.col[1];normal=world_palm.col[2]
        # Fit a rigid two-hand interval, sharing corrections between the two arms.
        candidates=[]
        for grip_distance in [.12,.125,.13,.135,.14,.145,.15,.155,.16,.165]:
            midpoint=(rw+world_offsets['r']+lw+world_offsets['l'])*.5
            if prior_midpoint is not None:midpoint=prior_midpoint.lerp(midpoint,1-math.exp(-1/(fps*4*.055)))
            for _ in range(12):
                for jp,slot_offset in [('右',axis*(grip_distance/2)),('左',-axis*(grip_distance/2))]:
                    shoulder=arm.pose.bones[jp+'腕'].head;elbow=arm.pose.bones[jp+'ひじ'].head;wrist=arm.pose.bones[jp+'手首'].head
                    offset=world_offsets['r' if jp=='右' else 'l'];reach_radius=(elbow-shoulder).length+(wrist-elbow).length-.008;delta=midpoint+slot_offset-offset-shoulder
                    if delta.length>reach_radius:midpoint=shoulder+delta.normalized()*reach_radius-slot_offset+offset
            rt=midpoint+axis*(grip_distance/2)-world_offsets['r'];lt=midpoint-axis*(grip_distance/2)-world_offsets['l'];edit=max((rt-rw).length,(lt-lw).length);candidates.append((edit,grip_distance,rt,lt))
            if edit<=.2005:break
        edits,grip_distance,right_target,left_target=min(candidates,key=lambda c:c[0])
        prior_midpoint=(right_target+world_offsets['r']+left_target+world_offsets['l'])*.5
        original={n:arm.pose.bones[n].rotation_quaternion.copy() for n in ['右腕','右ひじ','左腕','左ひじ']}
        connected=edits<=.2005 and reach(arm,right_target,'右') and reach(arm,left_target,'左')
        if not connected:
            for n,q in original.items():arm.pose.bones[n].rotation_quaternion=q
            bpy.context.view_layer.update()
        rw=right.head.copy()
        for side,jp in [('r','右'),('l','左')]:
            if side=='l' and not connected:continue
            pb=arm.pose.bones[jp+'手首'];desired=world_palms[side]@palms[side].transposed()@pb.bone.matrix_local.to_3x3();set_world(arm,pb,desired)
            _,twist=pb.rotation_quaternion.to_swing_twist('Y');extra=twist-max(-math.radians(40),min(math.radians(40),twist));helper=arm.pose.bones[jp+'手捩'];helper.rotation_quaternion=helper.rotation_quaternion@Quaternion((0,1,0),max(-math.radians(90),min(math.radians(90),extra)));bpy.context.view_layer.update();set_world(arm,pb,desired)
            q=limit_wrist(pb.rotation_quaternion)
            if side in prior_wrists:
                prior=prior_wrists[side]
                if q.dot(prior)<0:q.negate()
                delta=prior.rotation_difference(q).angle;delta=min(delta,2*math.pi-delta);q=prior.slerp(q,min(1-math.exp(-1/(fps*4*.08)),math.radians(180)/(fps*4)/max(delta,1e-8)))
            q=limit_wrist(q);prior_wrists[side]=q.copy();pb.rotation_quaternion=q;bpy.context.view_layer.update()
        actual_palm=right.matrix.to_3x3()@right.bone.matrix_local.to_3x3().transposed()@palms['r'];center=right.head+right.matrix.to_3x3()@right.bone.matrix_local.to_3x3().transposed()@offsets['r'];forward=actual_palm.col[1];normal=actual_palm.col[2];axis=actual_palm.col[0]
        matrix=Matrix((forward,normal,axis)).transposed().to_4x4();matrix.translation=center;sword.matrix_world=matrix
        sword.rotation_mode='QUATERNION'
        if prior_sword is not None and sword.rotation_quaternion.dot(prior_sword)<0:sword.rotation_quaternion.negate()
        prior_sword=sword.rotation_quaternion.copy();sword.keyframe_insert('location',frame=frame);sword.keyframe_insert('rotation_quaternion',frame=frame)
        left_palm=world_palms['l']
        secondary_center=center-axis*grip_distance;target=secondary_center-left_palm@palms['l'].transposed()@offsets['l'];correction=(target-lw).length
        sides=['r','l'] if connected else ['r']
        for side,jp in [('r','右'),('l','左')]:
            if side not in sides:continue
            for name,q in poses[side].items():arm.pose.bones[name].rotation_quaternion=q;arm.pose.bones[name].keyframe_insert('rotation_quaternion',frame=frame,group=name)
            arm.pose.bones[jp+'手首'].keyframe_insert('rotation_quaternion',frame=frame,group=jp+'手首')
        if connected:
            for name in ['左腕','左ひじ','右腕','右ひじ']:arm.pose.bones[name].keyframe_insert('rotation_quaternion',frame=frame,group=name)
        for name in ['左手捩','右手捩']:arm.pose.bones[name].keyframe_insert('rotation_quaternion',frame=frame,group=name)
        bpy.context.view_layer.update();actual_right=right.head+(right.matrix.to_3x3()@right.bone.matrix_local.to_3x3().transposed())@offsets['r'];error=(actual_right-center).length
        left_center=left.head+(left.matrix.to_3x3()@left.bone.matrix_local.to_3x3().transposed())@offsets['l']
        rows.append({'frame':frame,'grip_distance_m':grip_distance,'secondary_connected':connected,'secondary_requested_arm_shift_m':correction,'max_requested_arm_shift_m':edits,'right_grip_center_error_m':error,'left_grip_center_error_m':(left_center-secondary_center).length if connected else None})
        if frame%100==0:print('GRIP_FRAME',frame,flush=True)
    # Equivalent +/- quaternions must share a hemisphere before component interpolation.
    priors={}
    for frame in times:
        scene.frame_set(int(frame),subframe=frame%1)
        for name in animated:
            pb=arm.pose.bones[name];q=pb.rotation_quaternion.normalized()
            if name in priors and q.dot(priors[name])<0:q.negate()
            priors[name]=q.copy();pb.rotation_quaternion=q;pb.keyframe_insert('rotation_quaternion',frame=frame,group=name)
    for obj in [arm,sword]:
        for layer in obj.animation_data.action.layers:
            for strip in layer.strips:
                for slot_data in obj.animation_data.action.slots:
                    bag=strip.channelbag(slot_data)
                    if bag:
                        for curve in bag.fcurves:
                            for k in curve.keyframe_points:k.interpolation='LINEAR'
    scene.frame_set(1);world=sword.matrix_world.copy();sword.animation_data_clear();sword.parent=arm;sword.parent_type='BONE';sword.parent_bone='右手首';bpy.context.view_layer.update();sword.matrix_world=world;bpy.context.view_layer.update()
    bpy.data.objects.remove(baseline,do_unlink=True);bpy.ops.wm.save_as_mainfile(filepath=str(out/'animation.blend'))
    assert all(digest(p)==h for p,h in inputs.items())
    keys=[r for r in rows if r['frame']%1==0]
    report={'status':'completed','input_sha256':inputs,'frames':scene.frame_end,'baked_samples':len(rows),'fps':fps,'object_scale_m_per_obj_unit':scale,'shaft_radius_m':radius,'contact':contact,'secondary_connected_frames':sum(r['secondary_connected'] for r in keys),'frame_results':keys,'baked_sample_results':rows,'policy':{'continuous_grip_assumed_for_selected_LongSword_clip':True,'primary_hand':'right','primary_object_bone_parent':True,'bake_samples_per_frame':4,'secondary_sliding_distance_m':[.12,.165],'max_arm_shift_m':.20,'arm_shift_numeric_tolerance_m':.0005,'contact':'bone_capsule_approximation_not_mesh_collision','object_scale':'estimated_1.5m_total_length_no_source_units','axis':'2D_wrist_line_with_capped_estimated_depth','no_video_object_pose_tracking':True,'not_verified_exact_reconstruction':True}}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('GRIP_DONE',report['secondary_connected_frames'],len(rows),contact,flush=True)


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
