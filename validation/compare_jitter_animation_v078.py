"""Check keyed Quaternion changes as well as joint-position metrics."""
import json,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];report=[]
for label in ('dance','LongSword'):
    old=json.loads((ROOT/f'validation/root-v077-release/{label}-example/animation.json').read_text(encoding='utf-8'))
    new=json.loads((ROOT/f'validation/jitter-v078/{label}-example/animation.json').read_text(encoding='utf-8'))
    a=np.asarray([r['local_quaternions_wxyz'] for r in old['frames']]);b=np.asarray([r['local_quaternions_wxyz'] for r in new['frames']]);metrics=[]
    for name in ('upperarm_l','upperarm_r','lowerarm_l','lowerarm_r','calf_l','calf_r'):
        j=new['bone_names'].index(name)
        def measure(q):
            steps=np.degrees(2*np.arccos(np.clip(np.abs(np.sum(q[1:,j]*q[:-1,j],axis=1)),0,1)))
            return {'angular_speed_change_degrees':float(np.abs(np.diff(steps)).mean()),'maximum_frame_angle_degrees':float(steps.max())}
        before,after=measure(a),measure(b)
        assert after['maximum_frame_angle_degrees']<before['maximum_frame_angle_degrees']+1
        assert after['angular_speed_change_degrees']<before['angular_speed_change_degrees']
        metrics.append({'bone':name,'before':before,'after':after})
    report.append({'label':label,'metrics':metrics});print(json.dumps(report[-1]))
(ROOT/'validation/jitter-v078/quaternion-comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
