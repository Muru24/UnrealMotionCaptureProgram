"""Measure estimated axial-prior error, not anatomical accuracy, using saved local keys."""
import sys,json,importlib.util,math
from pathlib import Path
import bpy
from mathutils import Matrix,Quaternion
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'validation/twist-v079'
spec=importlib.util.spec_from_file_location('solver',ROOT/'tools/animate_reference_rig.py');solver=importlib.util.module_from_spec(spec);spec.loader.exec_module(solver)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/skeletons/MotionHumanoid22.blend'))
arm=bpy.data.objects['MotionSkeleton'];results=[]
for label in ('dance','LongSword'):
    summaries=[]
    for version in ('jitter-v078','twist-v079'):
        data=json.loads((ROOT/f'validation/{version}/{label}-example/animation.json').read_text(encoding='utf-8'))
        names=data['bone_names'];bones={b['name']:b for b in data['skeleton']['bones']};errors=[];steps=[];previous={}
        for row in data['frames']:
            world={}
            for name,q in zip(names,row['local_quaternions_wxyz']):
                if q is None:continue
                parent=bones[name]['parent'];rest=arm.data.bones[name].matrix_local.to_3x3()
                if parent and parent not in world:continue
                reference=world[parent]@arm.data.bones[parent].matrix_local.to_3x3().transposed()@rest if parent else rest
                rotation=reference@Quaternion(q).to_matrix();world[name]=rotation
                if name.startswith(('upperarm_','lowerarm_','thigh_','calf_')):
                    anchor=solver.transport_roll(reference,rotation.col[1]);axis=rotation.col[1].normalized()
                    a=rotation.col[0].normalized();b=anchor.col[0].normalized()
                    errors.append(abs(math.degrees(math.atan2(axis.dot(a.cross(b)),max(-1,min(1,a.dot(b)))))))
                    key=(row.get('tracking_segment'),row.get('scene_index'))
                    if name in previous and previous[name][0]==row['frame_index']-1 and previous[name][1]==key:
                        angle=2*math.acos(max(0,min(1,abs(Quaternion(q).normalized().dot(previous[name][2])))))
                        steps.append(math.degrees(angle))
                    previous[name]=(row['frame_index'],key,Quaternion(q).normalized())
        summaries.append({'version':version,'mean_absolute_parent_twist_prior_error_degrees':sum(errors)/len(errors),'max_degrees':max(errors),
                          'maximum_local_frame_angle_degrees':max(steps),'mean_local_frame_angle_degrees':sum(steps)/len(steps)})
    results.append({'label':label,'metrics':summaries,'not_ground_truth':True})
    assert summaries[1]['mean_absolute_parent_twist_prior_error_degrees']<summaries[0]['mean_absolute_parent_twist_prior_error_degrees']
    # Parent and child may each correct roll by <=4 degrees at 30fps.
    assert summaries[1]['maximum_local_frame_angle_degrees']<summaries[0]['maximum_local_frame_angle_degrees']+8.1
(folder/'twist-comparison.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print(json.dumps(results),flush=True)
