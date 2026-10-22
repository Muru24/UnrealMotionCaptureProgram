"""Compare stronger smoothing with v0.7.3; no inference or previous evidence changes."""
import json,subprocess,shutil
import numpy as np
from app.animation_job import ROOT,export_animation,find_blender

e=ROOT/'validation/m4-smooth';e.mkdir(exist_ok=True)
motion=ROOT/'outputs/LongSword_sam3d_20261020_133149_13dbea63/motion/motion.json'
synthetic=e/'synthetic/motion/motion.json';synthetic.parent.mkdir(parents=True,exist_ok=True)
shutil.copyfile(ROOT/'validation/m4-correction/synthetic/motion/motion.json',synthetic)
results=[]
for label,path in (('LongSword',motion),('synthetic',synthetic)):
    original=path.read_bytes();blend=export_animation(path)
    for script,args,kind in (
        ('verify_m4_blender.py',[str(blend.parent),str(blend.parent/'corrected-motion.json')],'reopen'),
        ('verify_m4_interpolation.py',[str(blend.parent)],'fractional')):
        with (e/f'{label}-{kind}.log').open('w') as log:
            subprocess.run([find_blender(),'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'validation'/script),
                '--',*args,str(e/f'{label}-{kind}.json')],stdout=log,stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=True,timeout=240)
    assert original==path.read_bytes()
    results.append({'label':label,'blend':str(blend),'input_unchanged':True})
    if label=='LongSword':
        old=json.loads((ROOT/'validation/m4-jitter/LongSword-example/corrected-motion.json').read_text(encoding='utf-8'))
        new=json.loads((blend.parent/'corrected-motion.json').read_text(encoding='utf-8'))
        names=[b['name'] for b in new['skeleton']['bones']]
        a=np.array([r['positions'] for r in old['frames']]);b=np.array([r['positions'] for r in new['frames']]);metrics=[]
        for child,parent in (('hand_l','upperarm_l'),('hand_r','upperarm_r'),('calf_l','thigh_l'),('calf_r','thigh_r')):
            def metric(q):return float(np.mean(np.linalg.norm(np.diff(q[:,names.index(child)]-q[:,names.index(parent)],n=2,axis=0),axis=1)))
            v1,v2=metric(a),metric(b)
            metrics.append({'joint':child,'v073_second_difference_m':v1,'v074_second_difference_m':v2,'reduction_fraction':1-v2/v1})
            assert v2<v1
        feet=[]
        for side in ('l','r'):
            j=names.index('foot_'+side);step=float(np.linalg.norm(np.diff(b[:,j],axis=0),axis=1).max());assert step<.3
            feet.append({'side':side,'maximum_step_m':step})
        (e/'comparison.json').write_text(json.dumps({'metrics':metrics,'feet':feet,'not_ground_truth_accuracy':True},indent=2),encoding='utf-8')
(e/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False),flush=True)
