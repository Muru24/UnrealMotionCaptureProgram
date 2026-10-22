"""Compare the saved dance without repeating GPU inference or editing its M3 input."""
from pathlib import Path
import json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.animation_job import ground_evidence
from core.motion.correction import prepare_motion
status=json.loads((ROOT/'validation/dance-v074/status.json').read_text(encoding='utf-8'))
motion=Path(status['motion']);data=json.loads(motion.read_text(encoding='utf-8'))
evidence,path=ground_evidence(motion,data);out=prepare_motion(data,ground_evidence=evidence)
old=json.loads((Path(status['blend']).parent/'corrected-motion.json').read_text(encoding='utf-8'))
names=[b['name'] for b in data['skeleton']['bones']];feet=[names.index('foot_'+side) for side in ('l','r')]
a=np.array([r['positions'] for r in old['frames']]);b=np.array([r['positions'] for r in out['frames']])
report={'evidence':str(path),'frames':len(b),'support_frames':sum(any(r['image_ground_support']) for r in out['correction']['frames']),
        'baseline_maximum_ankle_step_m':float(np.linalg.norm(np.diff(a[:,feet],axis=0),axis=2).max()),
        'crouch_old_ankle_z_m':a[175:186,feet,2].tolist(),'crouch_new_ankle_z_m':b[175:186,feet,2].tolist(),
        'maximum_ankle_step_m':float(np.linalg.norm(np.diff(b[:,feet],axis=0),axis=2).max())}
steps=np.linalg.norm(np.diff(b[:,feet],axis=0),axis=2);worst=int(np.unravel_index(np.argmax(steps),steps.shape)[0])+1
for i in range(max(0,worst-3),min(len(b),worst+3)):
    print('worst',i,out['correction']['frames'][i],b[i,feet].round(3).tolist())
for i in (140,150,160,165,170,175,180,185,190,200,210):
    print(i,out['correction']['frames'][i]['feet'],np.round(b[i,feet,2],3).tolist(),out['correction']['frames'][i]['image_ground_support'])
folder=ROOT/'validation/ground-v076';folder.mkdir(exist_ok=True)
(folder/'comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(folder/'corrected-motion.json').write_text(json.dumps(out,allow_nan=False),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if not k.startswith('crouch')},ensure_ascii=False))
