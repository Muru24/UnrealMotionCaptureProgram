"""Read saved Blender curves and evaluate between source frames, including discontinuities."""
import sys,json,math
from pathlib import Path
import bpy
from mathutils import Quaternion,Vector

args=sys.argv[sys.argv.index('--')+1:];folder=Path(args[0]);target=Path(args[1])
data=json.loads((folder/'animation.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=str(folder/'animation.blend'))
arm=bpy.data.objects['MotionSkeleton'];scene=bpy.context.scene
curves={}
for layer in arm.animation_data.action.layers:
    for strip in layer.strips:
        for slot in arm.animation_data.action.slots:
            bag=strip.channelbag(slot)
            if bag:
                for curve in bag.fcurves:curves[(curve.data_path,curve.array_index)]=curve
valid_samples=0;boundary_samples=0;max_error=0.;changed=0
for i in range(len(data['frames'])-1):
    a,b=data['frames'][i:i+2]
    same=(a['tracking_segment'],a['scene_index'])==(b['tracking_segment'],b['scene_index'])
    evaluated={}
    for t in (.25,.5,.75):
        scene.frame_set(i+1,subframe=t);bpy.context.view_layer.update()
        evaluated[t]={name:arm.pose.bones[name].rotation_quaternion.copy() for name in data['bone_names']}
    for j,name in enumerate(data['bone_names']):
        qa=a['local_quaternions_wxyz'][j];qb=b['local_quaternions_wxyz'][j]
        path=f'pose.bones["{name}"].rotation_quaternion'
        if qa is None:continue
        if not same or qb is None:
            q=[curves[(path,c)].evaluate(i+1.5) for c in range(4)]
            assert max(abs(x-y) for x,y in zip(q,qa))<1e-5
            boundary_samples+=1;continue
        qa=Quaternion(qa);qb=Quaternion(qb)
        if qa.dot(qb)<0:qb.negate()
        for t in (.25,.5,.75):
            actual=evaluated[t][name]
            expected=qa.slerp(qb,t)
            error=max(abs(x-y) for x,y in zip(actual,expected));max_error=max(max_error,error)
            assert error<2e-5
            valid_samples+=1
        if abs(qa.dot(qb))<.9999:changed+=1
assert valid_samples and changed and max_error<2e-5
result={'file':str(folder/'animation.blend'),'valid_fractional_quaternion_samples':valid_samples,
    'discontinuity_hold_samples':boundary_samples,'moving_intervals':changed,'max_quaternion_component_error':max_error,'passed':True}
target.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
