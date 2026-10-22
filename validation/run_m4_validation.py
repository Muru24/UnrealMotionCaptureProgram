"""CPU-only synthetic and saved LongSword animation/reopen checks; no inference."""
from pathlib import Path
import json,subprocess,copy,math
import numpy as np
from app.animation_job import export_animation,find_blender,ROOT
from core.motion.skeleton import definition

e=ROOT/'validation/m4';e.mkdir(exist_ok=True)
spec=definition();names=[b['name'] for b in spec['bones']];rest=np.array([b['head'] for b in spec['bones']])
frames=[]
for i,angle in enumerate((0,0,179,181,190,190,270,360)):
    a=math.radians(angle);r=np.array([[math.cos(a),-math.sin(a),0],[math.sin(a),math.cos(a),0],[0,0,1]])
    points=(rest-np.array([0,0,1]))@r.T+np.array([0,0,1]);points[0]=0
    values=points.tolist()
    if i in (0,5):values=[None]*22
    if i==4:values[names.index('hand_l')]=None
    frames.append({'frame_index':i,'positions':values,'tracking_segment':int(i>=6),'scene_index':int(i>=6)})
synthetic=e/'synthetic/motion';synthetic.mkdir(parents=True,exist_ok=True)
p=synthetic/'motion.json';p.write_text(json.dumps({'schema':'standard_motion_positions_v1','skeleton':spec,'video':{'fps':29.883},'frames':frames}),encoding='utf-8')
real=ROOT/'outputs/LongSword_sam3d_20261020_133149_13dbea63/motion/motion.json'
results=[]
for label,motion in (('synthetic',p),('LongSword',real)):
    blend=export_animation(motion,corrections=False)
    with (e/(label+'-reopen.log')).open('w',encoding='utf-8') as log:
        subprocess.run([find_blender(),'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'validation/verify_m4_blender.py'),
            '--',str(blend.parent),str(motion),str(e/(label+'-reopen.json'))],stdout=log,stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=True,timeout=180)
    report=json.loads((e/(label+'-reopen.json')).read_text(encoding='utf-8'))
    if label=='synthetic':
        animation=json.loads((blend.parent/'animation.json').read_text())
        # True rest frame, not the MHR-derived torso proxy, must yield identity local rotations.
        for q in animation['frames'][1]['local_quaternions_wxyz']:
            assert abs(abs(q[0])-1)<1e-5 and max(abs(v) for v in q[1:])<1e-5
    results.append(report)
(e/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False),flush=True)
