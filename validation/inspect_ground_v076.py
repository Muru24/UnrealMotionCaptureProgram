import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
status=json.loads((ROOT/'validation/dance-v074/status.json').read_text(encoding='utf-8'))
folder=Path(status['output'])
report=json.loads((folder/'automatic-report.json').read_text(encoding='utf-8'))
selected=Path(report['reconnection_directory'])/'reconnected-joints.json'
packet=json.loads(selected.read_text(encoding='utf-8'))
motion=json.loads((folder/'motion/motion.json').read_text(encoding='utf-8'))
old=json.loads((Path(status['blend']).parent/'corrected-motion.json').read_text(encoding='utf-8'))
names=[b['name'] for b in motion['skeleton']['bones']]
for i in (0,100,140,150,160,165,170,175,180,185,190,200,210,240):
    row=packet['frames'][i];p=np.asarray(row['image_joints']);q=np.asarray(motion['frames'][i]['positions'])
    angles=[]
    for side in ('l','r'):
        hip,knee,ankle=[q[names.index(n+'_'+side)] for n in ('thigh','calf','foot')]
        u=hip-knee;v=ankle-knee
        angles.append(round(float(np.degrees(np.arccos(np.clip(u@v/np.linalg.norm(u)/np.linalg.norm(v),-1,1)))),1))
    print(i,'image ankle',p[[13,14]].round(1).tolist(),'toe',p[[15,18]].round(1).tolist(),'hip',p[[9,10],1].round(1).tolist(),'bend',angles,'state',old['correction']['frames'][i]['feet'],'z',np.asarray(old['frames'][i]['positions'])[[names.index('foot_l'),names.index('foot_r')],2].round(3).tolist())
print('row keys',packet['frames'][0].keys())
