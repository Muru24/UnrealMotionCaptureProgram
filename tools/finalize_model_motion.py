"""Automatic model/skin checks and contact-derived sole calibration, no grip edits."""
import bpy,json,sys,math,hashlib
import numpy as np
from pathlib import Path
from mathutils import Vector,Quaternion,Matrix
sys.path.insert(0,str(Path(__file__).resolve().parent))

def sole_points(scene,arm,selection,side):
    points=[]
    for name,indices in selection[side]:
        obj=bpy.data.objects[name];evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
        transform=arm.matrix_world.inverted()@obj.matrix_world
        points.extend(tuple(transform@mesh.vertices[i].co) for i in indices);evaluated.to_mesh_clear()
    return np.asarray(points,float)

def normal(points):
    if len(points)<6 or not np.isfinite(points).all():return None
    _,values,axes=np.linalg.svd(points-points.mean(0),full_matrices=False)
    if values[1]<.004 or values[2]/max(values[1],1e-8)>.25:return None
    n=Vector(axes[-1]);return n if n.z>=0 else -n

def run(source,motion,profile,out,auto_rig='0',gain='1'):
    source,motion,profile,out=map(lambda p:Path(p).resolve(),(source,motion,profile,out));gain=float(gain)
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,motion,profile)}
    if auto_rig=='1':
        from repair_leg_deformation import run as repair
        repair(source,out)
    else:
        out.mkdir(exist_ok=False);bpy.ops.wm.open_mainfile(filepath=str(source))
    scene=bpy.context.scene;arm=next(o for o in scene.objects if o.type=='ARMATURE');mapping=json.loads(profile.read_text(encoding='utf-8'))
    roles={v['source']:k for k,v in mapping['mapping'].items()};root=arm.pose.bones[mapping['root']]
    data=json.loads(motion.read_text(encoding='utf-8'));contacts=(data.get('correction') or {}).get('frames',[])
    if len(data['frames'])!=scene.frame_end-scene.frame_start+1:raise ValueError('Model/contact timelines differ')
    meshes=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==arm for m in o.modifiers)]
    selection={'l':[],'r':[]};warnings=[];checked=0;max_weight_error=0.;rest_points=[]
    if mapping.get('weighting_method')=='distance_seeded_surface_diffusion':warnings.append('본 웨이트를 대체 방식으로 추정함 · 변형 확인 필요')
    for obj in meshes:
        by_side={s:{g.index for g in obj.vertex_groups if g.name in {roles.get('foot_'+s),roles.get('ball_'+s)}} for s in selection}
        transform=arm.matrix_world.inverted()@obj.matrix_world;candidates={s:[] for s in selection}
        for v in obj.data.vertices:
            if not all(math.isfinite(x) for x in v.co):raise ValueError('Non-finite model vertex')
            total=sum(g.weight for g in v.groups);checked+=1;max_weight_error=max(max_weight_error,abs(total-1.))
            if v.index%10==0:rest_points.append(tuple(transform@v.co))
            if not math.isfinite(total) or any(g.weight<0 for g in v.groups) or abs(total-1.)>.02:raise ValueError('Invalid skin weights: '+obj.name)
            for side,groups in by_side.items():
                if groups and sum(g.weight for g in v.groups if g.group in groups)>.65:candidates[side].append((v.index,(transform@v.co).z))
        for side,rows in candidates.items():
            if len(rows)<6:continue
            zs=np.array([r[1] for r in rows]);limit=float(np.quantile(zs,.025))+.008
            ids=[i for i,z in rows if z<=limit]
            if len(ids)>=6:selection[side].append((obj.name,ids[::max(1,len(ids)//1500)]))
    cloud=np.asarray(rest_points,float)
    if len(cloud)<20:raise ValueError('Insufficient model skin geometry')
    height=float(np.ptp(cloud[:,2]));landmarks={}
    if height<.3 or height>4.:raise ValueError('Model scale outside supported humanoid range')
    for role in ('pelvis','upperarm_l','upperarm_r','thigh_l','thigh_r','calf_l','calf_r','foot_l','foot_r'):
        if role not in roles:raise ValueError('Missing humanoid role: '+role)
        head=np.asarray(arm.data.bones[roles[role]].head_local);distance=float(np.linalg.norm(cloud-head,axis=1).min());landmarks[role]=distance
        if distance>height*.18:raise ValueError('Joint is too far from model skin: '+role)
    ground_states={'inferred_contact','inferred_ground_support'};corrections={};samples={};before_angles={};baseline={}
    for s,side in enumerate(selection):
        frames=[scene.frame_start+i for i,r in enumerate(contacts) if len(r.get('feet',[]))==2 and r['feet'][s] in ground_states]
        frames=[frames[i] for i in np.linspace(0,len(frames)-1,min(8,len(frames)),dtype=int)] if frames else []
        samples[side]=frames;qs=[];angles=[];name=roles.get('foot_'+side)
        if not frames or not selection[side] or name is None:
            warnings.append('발바닥·접지 근거 부족: '+side);continue
        for f in frames:
            scene.frame_set(f);n=normal(sole_points(scene,arm,selection,side))
            if n is None:continue
            angle=math.degrees(n.angle(Vector((0,0,1))));angles.append(angle)
            if angle>20:continue
            world=arm.pose.bones[name].matrix.to_quaternion();q=world.conjugated()@n.rotation_difference(Vector((0,0,1)))@world
            if qs and qs[0].dot(q)<0:q=-q
            qs.append(q)
        before_angles[side]=float(np.median(angles)) if angles else None
        if not qs:warnings.append('발바닥 보정 근거가 불확실하여 유지: '+side);continue
        average=Quaternion(tuple(sum(q[k] for q in qs) for k in range(4))).normalized();corrections[side]=Quaternion().slerp(average,gain)
    for f in range(scene.frame_start,scene.frame_end+1):
        scene.frame_set(f)
        for side,q in corrections.items():
            p=arm.pose.bones[roles['foot_'+side]];p.rotation_quaternion=(p.rotation_quaternion@q).normalized();p.keyframe_insert('rotation_quaternion',frame=f,group=p.name)
    after_angles={};heights=[]
    for side,frames in samples.items():
        angles=[]
        for f in frames:
            scene.frame_set(f);points=sole_points(scene,arm,selection,side);n=normal(points)
            if n is not None:angles.append(math.degrees(n.angle(Vector((0,0,1)))));heights.append(float(np.quantile(points[:,2],.05)))
        after_angles[side]=float(np.median(angles)) if angles else None
        old=before_angles.get(side);new=after_angles[side]
        if old is not None and new is not None and new>old+1.:raise ValueError('Sole calibration worsened: '+side)
        if new is not None and new>5:warnings.append('발바닥 기울기 추가 확인 필요: '+side)
    shift=-float(np.median(heights)) if heights else 0.
    if abs(shift)>.2:warnings.append('접지 높이 추정 범위를 벗어나 높이 유지');shift=0.
    if shift:
        for f in range(scene.frame_start,scene.frame_end+1):
            scene.frame_set(f);wanted=root.matrix.copy();wanted.translation+=Vector((0,0,shift))
            parent=root.parent;kwargs={} if parent is None else {'parent_matrix':parent.matrix,'parent_matrix_local':parent.bone.matrix_local}
            basis=root.bone.convert_local_to_pose(wanted,root.bone.matrix_local,invert=True,**kwargs);root.location=basis.translation;root.keyframe_insert('location',frame=f,group=root.name)
    previous={};max_steps={}
    for f in range(scene.frame_start,scene.frame_end+1):
        scene.frame_set(f)
        for p in arm.pose.bones:
            if not all(math.isfinite(x) for row in p.matrix for x in row):raise ValueError('Non-finite model pose')
        for role in ('thigh_l','calf_l','foot_l','thigh_r','calf_r','foot_r','hand_l','hand_r'):
            if role not in roles:continue
            q=arm.pose.bones[roles[role]].matrix.to_quaternion()
            if role in previous:
                angle=q.rotation_difference(previous[role]).angle;max_steps[role]=max(max_steps.get(role,0.),math.degrees(min(angle,2*math.pi-angle)))
            previous[role]=q.copy()
    if any(v>100 for v in max_steps.values()):warnings.append('관절 회전 점프 추가 확인 필요')
    scene.frame_set(scene.frame_start);bpy.ops.wm.save_as_mainfile(filepath=str(out/'animation.blend'))
    if any(hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h for p,h in hashes.items()):raise ValueError('Model finalization inputs changed')
    (out/'model-quality.json').write_text(json.dumps({'status':'completed','frames':len(data['frames']),'skin_vertices_checked':checked,
        'max_weight_sum_error':max_weight_error,'input_sha256':hashes,'max_world_rotation_step_degrees':max_steps,'landmark_surface_distances_m':landmarks,'leg_repair_applied':auto_rig=='1','sole_contact_samples':samples,'sole_tilt_before_degrees':before_angles,
        'sole_tilt_after_degrees':after_angles,'root_ground_offset_m':shift,'calibration_gain':gain,'warnings':warnings,
        'limits':['Contact and floor are estimated from video','No anatomical landmark ML or mesh collision solver','No weapon grip solver']},indent=2),encoding='utf-8')

if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
