import json,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for label in ('dance','LongSword'):
    folder=ROOT/'validation/root-v077-release'/f'{label}-example'
    data=json.loads((folder/'corrected-motion.json').read_text(encoding='utf-8'))
    anim=json.loads((folder/'animation.json').read_text(encoding='utf-8'))
    names=[b['name'] for b in data['skeleton']['bones']]
    p=np.asarray([r['positions'] for r in data['frames']]);q=np.asarray([r['local_quaternions_wxyz'] for r in anim['frames']])
    print(label)
    for a,b in ((0,60),(0,len(p))):
        print('window',a,b,'root_second_mm',np.mean(np.linalg.norm(np.diff(p[a:b,0],n=2,axis=0),axis=1))*1000)
        metrics=[]
        for j,name in enumerate(names):
            steps=2*np.arccos(np.clip(np.abs(np.sum(q[a+1:b,j]*q[a:b-1,j],axis=1)),0,1))
            metrics.append((name,round(float(np.degrees(steps).mean()),3),round(float(np.degrees(np.abs(np.diff(steps))).mean()),3)))
        print(sorted(metrics,key=lambda x:x[2],reverse=True)[:10])
