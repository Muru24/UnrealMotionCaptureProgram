"""Inspect camera acceptance and saved-motion root changes without GPU inference."""
import json,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.animation_job import ground_evidence
from app.root_motion_job import root_observations
from core.motion.correction import prepare_motion
status=json.loads((ROOT/'validation/dance-v074/status.json').read_text(encoding='utf-8'))
motion=Path(status['motion']);data=json.loads(motion.read_text(encoding='utf-8'))
pixels,_=ground_evidence(motion,data);start=time.perf_counter();observations,info=root_observations(motion,data,pixels)
out=prepare_motion(data,ground_evidence=pixels,root_observations=observations)
old=json.loads((ROOT/'validation/ground-v076/dance-example/corrected-motion.json').read_text(encoding='utf-8'))
a=np.asarray([r['positions'] for r in old['frames']]);b=np.asarray([r['positions'] for r in out['frames']]);names=[x['name'] for x in data['skeleton']['bones']]
report={'camera':info,'seconds':time.perf_counter()-start,'driven_frames':sum(r['image_root_drive'] for r in out['correction']['frames']),
        'airborne_frames':[i for i,r in enumerate(out['correction']['frames']) if r['estimated_airborne']],
        'root_xyz_range_m':np.ptp(b[:,0],axis=0).tolist(),'old_root_xyz_range_m':np.ptp(a[:,0],axis=0).tolist()}
for i in (0,60,120,140,145,150,155,160,175,180,185,240,300,410):
    print(i,'root',b[i,0].round(3).tolist(),'pelvis',b[i,1].round(3).tolist(),out['correction']['frames'][i]['feet'])
folder=ROOT/'validation/root-v077';folder.mkdir(exist_ok=True)
if observations is not None:np.savez_compressed(folder/'observations.npz',**observations)
(folder/'comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(folder/'corrected-motion.json').write_text(json.dumps(out,allow_nan=False),encoding='utf-8')
print(json.dumps(report))
