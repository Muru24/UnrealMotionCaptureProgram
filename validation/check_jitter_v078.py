"""Compare saved v0.7.7 poses with small-curvature filtering, without new GPU inference."""
import json,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.animation_job import ground_evidence
from app.root_motion_job import root_observations
from core.motion.correction import prepare_motion
root=ROOT/'validation/jitter-v078';root.mkdir(exist_ok=True)
status=json.loads((ROOT/'validation/dance-v074/status.json').read_text(encoding='utf-8'))
cases=[('dance',Path(status['motion'])),('LongSword',ROOT/'outputs/LongSword_sam3d_20261020_133149_13dbea63/motion/motion.json')]
reports=[]
for label,motion in cases:
    old=json.loads((ROOT/f'validation/root-v077-release/{label}-example/corrected-motion.json').read_text(encoding='utf-8'))
    data=json.loads(motion.read_text(encoding='utf-8'));pixels,_=ground_evidence(motion,data);obs,info=root_observations(motion,data,pixels)
    new=prepare_motion(data,ground_evidence=pixels,root_observations=obs)
    names=[b['name'] for b in data['skeleton']['bones']];a=np.array([r['positions'] for r in old['frames']]);b=np.array([r['positions'] for r in new['frames']])
    metrics=[]
    for child,parent in (('hand_l','upperarm_l'),('hand_r','upperarm_r'),('calf_l','thigh_l'),('calf_r','thigh_r'),('root','root')):
        def metric(q):
            v=q[:,names.index(child)] if child=='root' else q[:,names.index(child)]-q[:,names.index(parent)]
            return float(np.mean(np.linalg.norm(np.diff(v,n=2,axis=0),axis=1)))
        before,after=metric(a),metric(b);metrics.append({'joint':child,'before_second_difference_m':before,'after_second_difference_m':after,'reduction_fraction':1-after/before})
    result={'label':label,'metrics':metrics,'airborne_before':[r['frame_index'] for r in old['correction']['frames'] if r['estimated_airborne']],
        'airborne_after':[r['frame_index'] for r in new['correction']['frames'] if r['estimated_airborne']],
        'old_jump_height_m':float(a[:,0,2].max()),'new_jump_height_m':float(b[:,0,2].max())}
    (root/f'{label}-corrected-motion.json').write_text(json.dumps(new,allow_nan=False),encoding='utf-8')
    reports.append(result);print(json.dumps(result),flush=True)
(root/'comparison.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
