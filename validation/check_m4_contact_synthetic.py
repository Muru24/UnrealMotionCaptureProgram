"""Blender-level regression for planted feet, lifted leg, missing frames and cuts."""
import json,math,subprocess
import numpy as np
from app.animation_job import ROOT,export_animation,find_blender
from core.motion.skeleton import definition

e=ROOT/'validation/m4-correction';folder=e/'synthetic/motion';folder.mkdir(parents=True,exist_ok=True)
spec=definition();names=[b['name'] for b in spec['bones']];rest=np.array([b['head'] for b in spec['bones']]);frames=[]
for i in range(80):
    q=rest.copy();q[names.index('hand_l'),2]+=.025*(-1)**i
    if 20<=i<40:
        hip=q[names.index('thigh_l')].copy();a=1.;r=np.array([[1,0,0],[0,math.cos(a),-math.sin(a)],[0,math.sin(a),math.cos(a)]])
        for part in ('calf','foot','ball'):
            j=names.index(part+'_l');q[j]=hip+r@(q[j]-hip)
    values=[None]*22 if i in (0,42) else q.tolist()
    frames.append({'frame_index':i,'positions':values,'tracking_segment':int(i>=50),'scene_index':int(i>=50)})
source=folder/'motion.json';source.write_text(json.dumps({'schema':'standard_motion_positions_v1','skeleton':spec,
    'source_kind':'synthetic','video':{'fps':29.883},'frames':frames}),encoding='utf-8')
blend=export_animation(source)
with (e/'synthetic-reopen.log').open('w') as log:
    subprocess.run([find_blender(),'--background','--factory-startup','--python-exit-code','1','--python',
        str(ROOT/'validation/verify_m4_blender.py'),'--',str(blend.parent),str(blend.parent/'corrected-motion.json'),str(e/'synthetic-reopen.json')],
        stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=180,check=True)
data=json.loads((blend.parent/'corrected-motion.json').read_text(encoding='utf-8'))
assert data['frames'][0]['positions']==[None]*22 and data['frames'][42]['positions']==[None]*22
assert data['correction']['frames'][30]['feet'][0]=='swing'
assert data['correction']['frames'][50]['root_offset_m'][0]==0
print((e/'synthetic-reopen.json').read_text(),flush=True)
