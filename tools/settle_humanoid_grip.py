"""Close remaining support-hand gaps while retaining bounded wrist contact."""
import json,math,sys,hashlib
from pathlib import Path
import bpy
from mathutils import Vector,Matrix,Quaternion
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fit_humanoid_sword_grip import reach,wrist_world
from grip_sword import set_world
from hand_retarget import palm_frame
from grip_stability import limit_wrist
from adaptive_deform import pose as pose_helpers


def align_support(arm,side,palm,desired):
    lower=arm.pose.bones['lowerarm_'+side];hand=arm.pose.bones['hand_'+side]
    base=lower.matrix.copy();axis=(lower.tail-lower.head).normalized();best=None
    target=desired@palm.transposed()@hand.bone.matrix_local.to_3x3()
    for degrees in range(-180,181,15):
        rot=Quaternion(axis,math.radians(degrees)).to_matrix()@base.to_3x3()
        parent=rot.to_4x4();parent.translation=base.translation
        wanted=target.to_4x4();wanted.translation=(parent@lower.bone.matrix_local.inverted()@hand.bone.matrix_local).translation
        q=hand.bone.convert_local_to_pose(wanted,hand.bone.matrix_local,parent_matrix=parent,parent_matrix_local=lower.bone.matrix_local,invert=True).to_quaternion().normalized()
        limited=limit_wrist(q,50,65);error=min(q.rotation_difference(limited).angle,2*math.pi-q.rotation_difference(limited).angle)
        score=error*error+math.radians(degrees)**2*.00005
        if best is None or score<best[0]:best=(score,rot)
    set_world(arm,lower,best[1]);set_world(arm,hand,target)
    hand.rotation_quaternion=limit_wrist(hand.rotation_quaternion,50,65);bpy.context.view_layer.update()


def run(source,out,mode='all'):
    source,out=Path(source).resolve(),Path(out).resolve();report=json.loads(source.with_name('grip-report.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(source));scene=bpy.context.scene;arm=next(o for o in scene.objects if o.type=='ARMATURE');sword=bpy.data.objects['GripSword']
    palms={s:palm_frame(arm,*[f'{n}_{s}' for n in ('hand','index_01','middle_01','pinky_01')]) for s in ('l','r')}
    widths={s:(arm.data.bones['index_01_'+s].head_local-arm.data.bones['pinky_01_'+s].head_local).length for s in palms}
    lengths={s:(arm.data.bones['middle_01_'+s].head_local-arm.data.bones['hand_'+s].head_local).length for s in palms}
    offsets={s:palms[s].col[1]*lengths[s]*.8+palms[s].col[2]*(-1 if s=='l' else 1)*report['shaft_radius_m']*1.4 for s in palms}
    rows=[];frames=range(1,scene.frame_end+1) if mode=='all' else [1,31,111,201,301,401,445]
    for index,f in enumerate(frames):
        scene.frame_set(f);right=arm.pose.bones['hand_r'];left=arm.pose.bones['hand_l'];starts={s:arm.pose.bones['hand_'+s].head.copy() for s in palms}
        right_rotation=right.matrix.to_3x3().normalized();initial_sword=sword.matrix_world.copy();axis=initial_sword.to_3x3().col[2].normalized()
        before=None;best_error=float('inf');best=None
        for iteration in range(16):
            world=sword.matrix_world;target=world.translation-axis*report['grip_distance_m']
            parent=left.parent;neutral=(parent.matrix@parent.bone.matrix_local.inverted()@left.bone.matrix_local).to_3x3()@left.bone.matrix_local.to_3x3().transposed()@palms['l']
            forward=neutral.col[1]-axis*neutral.col[1].dot(axis);forward.normalize();desired=Matrix((axis,forward,axis.cross(forward))).transposed()
            rotation=left.matrix.to_3x3()@left.bone.matrix_local.to_3x3().transposed();off=rotation@offsets['l'];error=(left.head+off-target).length
            if before is None:before=error
            if error<best_error:
                best_error=error;best={n:arm.pose.bones[n].rotation_quaternion.copy() for n in ['upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r']}
            if error<.001:break
            reach(arm,'l',target-off);align_support(arm,'l',palms['l'],desired)
            rotation=left.matrix.to_3x3()@left.bone.matrix_local.to_3x3().transposed();residual=left.head+rotation@offsets['l']-target
            if residual.length>.01:
                proposed=right.head+residual*.6;shift=proposed-starts['r']
                if shift.length>.10:proposed=starts['r']+shift.normalized()*.10
                reach(arm,'r',proposed);set_world(arm,right,right_rotation)
                right.rotation_quaternion=limit_wrist(right.rotation_quaternion,50,65);bpy.context.view_layer.update()
                axis=sword.matrix_world.to_3x3().col[2].normalized()
        # Keep the best feasible iteration, including the unchanged pose.
        for n,q in best.items():arm.pose.bones[n].rotation_quaternion=q
        bpy.context.view_layer.update();target=sword.matrix_world.translation-sword.matrix_world.to_3x3().col[2]*report['grip_distance_m']
        rotation=left.matrix.to_3x3()@left.bone.matrix_local.to_3x3().transposed();error=(left.head+rotation@offsets['l']-target).length
        for n in best:arm.pose.bones[n].keyframe_insert('rotation_quaternion',frame=f,group=n)
        pose_helpers(arm,f);bpy.context.view_layer.update()
        rows.append({'frame':f,'before_m':before,'after_m':error,'primary_shift_m':(right.head-starts['r']).length})
        if mode!='all' or index%100==0:print('SUPPORT_REFINE',f,before,error,flush=True)
    if mode=='all':
        out.mkdir(exist_ok=False);scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'animation.blend'))
        report['support_refinement']=rows;report['support_contact_frames']=sum(r['after_m']<.025 for r in rows)
        report['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
        (out/'grip-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('SUPPORT_FINAL',report['support_contact_frames'],len(rows),flush=True)


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
