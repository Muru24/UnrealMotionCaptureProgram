"""Keep bounded wrist curves, adjusting only the support arm toward the handle."""
import sys,json,math,hashlib
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from grip_sword import reach
from hand_retarget import palm_frame


def run(source,out,mode='strict'):
    if mode not in ('strict','project'):raise ValueError('Unknown support reach mode')
    source=Path(source).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False);signature=hashlib.sha256(source.read_bytes()).hexdigest()
    report=json.loads(source.with_name('report.json').read_text(encoding='utf-8'));bpy.ops.wm.open_mainfile(filepath=str(source));arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');scene=bpy.context.scene;sword=bpy.data.objects['GripSword']
    baseline=arm.copy();baseline.data=arm.data.copy();baseline.animation_data.action=arm.animation_data.action.copy();bpy.context.collection.objects.link(baseline);baseline.hide_set(True);baseline.hide_render=True
    for pb in baseline.pose.bones:
        for c in pb.constraints:
            if getattr(c,'target',None)==arm:c.target=baseline
    palm=palm_frame(arm,'左手首','左人指１','左中指１','左小指１');offset=palm.col[1]*.065-palm.col[2]*.016;results=[];prior={}
    for k,row in enumerate(report['baked_sample_results']):
        frame=row['frame'];scene.frame_set(int(frame),subframe=frame%1)
        for n in ['左腕','左ひじ']:arm.pose.bones[n].rotation_quaternion=baseline.pose.bones[n].rotation_quaternion.copy()
        bpy.context.view_layer.update();left=arm.pose.bones['左手首'];start=left.head.copy();wrist_q=left.rotation_quaternion.copy();target=sword.matrix_world.translation-sword.matrix_world.to_3x3().col[2]*row['grip_distance_m'];reached=True
        best_error=float('inf');best_pose=None
        for _ in range(24 if mode=='project' else 8):
            off=left.matrix.to_3x3()@left.bone.matrix_local.to_3x3().transposed()@offset;wanted=target-off
            current_error=(left.head+off-target).length
            if current_error<best_error:
                best_error=current_error;best_pose={n:arm.pose.bones[n].rotation_quaternion.copy() for n in ['左腕','左ひじ']}
            if current_error<.001:break
            if mode=='project':
                # Unreachable wrist goals previously discarded the entire solve.
                # Use the closest point inside the existing two-bone reach shell,
                # without stretching bones or changing the wrist orientation.
                upper=arm.pose.bones['左腕'];lower=arm.pose.bones['左ひじ']
                a=(lower.head-upper.head).length;b=(left.head-lower.head).length
                direction=wanted-upper.head;distance=direction.length
                if distance>1e-8:
                    wanted=upper.head+direction.normalized()*max(abs(a-b)+.001,min(a+b-.001,distance))
            if (wanted-start).length>.20 or not reach(arm,wanted,'左'):reached=False;break
        if mode=='project' and best_pose is not None:
            off=left.matrix.to_3x3()@left.bone.matrix_local.to_3x3().transposed()@offset
            if (left.head+off-target).length>best_error:
                for n,q in best_pose.items():arm.pose.bones[n].rotation_quaternion=q
                bpy.context.view_layer.update()
        assert abs(left.rotation_quaternion.dot(wrist_q))>1-1e-6
        off=left.matrix.to_3x3()@left.bone.matrix_local.to_3x3().transposed()@offset;error=(left.head+off-target).length
        for n in ['左腕','左ひじ']:
            pb=arm.pose.bones[n];q=pb.rotation_quaternion.normalized()
            if n in prior and q.dot(prior[n])<0:q.negate()
            prior[n]=q.copy();pb.rotation_quaternion=q;pb.keyframe_insert('rotation_quaternion',frame=frame,group=n)
        new={**row,'secondary_arm_reach_solved':reached,'secondary_connected':error<=.015,'left_grip_center_error_m':error,'secondary_extra_wrist_shift_m':(left.head-start).length};results.append(new)
        if k%400==0:print('SUPPORT_ARM',k,error,flush=True)
    bpy.data.objects.remove(baseline,do_unlink=True);scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'animation.blend'))
    assert hashlib.sha256(source.read_bytes()).hexdigest()==signature
    report['baked_sample_results']=results;report['frame_results']=[r for r in results if r['frame']%1==0];report['secondary_connected_frames']=sum(r['secondary_connected'] for r in report['frame_results']);report['input_sha256'][str(source)]=signature
    report['policy'].update(wrist_swing_limit_degrees=40,wrist_twist_limit_degrees=50,wrist_angular_speed_degrees_per_second=180,source_arm_filter_seconds=.065,wrist_filter_seconds=.08,neutral_forearm_based_grip=True,contact_may_relax_to_preserve_wrist_limits=True)
    report['policy']['secondary_reach_mode']=mode
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('SUPPORT_DONE',report['secondary_connected_frames'],report['frames'],max(r['left_grip_center_error_m'] for r in results),flush=True)


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
