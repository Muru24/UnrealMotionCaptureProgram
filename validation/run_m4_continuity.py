"""CPU-only replay and fractional-time Blender validation, preserving earlier evidence."""
from pathlib import Path
import json,subprocess,shutil
import numpy as np
from app.animation_job import ROOT,export_animation,find_blender

e=ROOT/'validation/m4-continuity';e.mkdir(exist_ok=True)
real=ROOT/'outputs/LongSword_sam3d_20261020_133149_13dbea63/motion/motion.json'
synthetic=e/'synthetic/motion/motion.json';synthetic.parent.mkdir(parents=True,exist_ok=True)
shutil.copyfile(ROOT/'validation/m4-correction/synthetic/motion/motion.json',synthetic)
results=[]
for label,motion in (('LongSword',real),('synthetic',synthetic)):
    before=motion.read_bytes();blend=export_animation(motion)
    for script,args,suffix in (
        ('verify_m4_blender.py',[str(blend.parent),str(blend.parent/'corrected-motion.json')],'reopen'),
        ('verify_m4_interpolation.py',[str(blend.parent)],'fractional')):
        report=e/f'{label}-{suffix}.json'
        with (e/f'{label}-{suffix}.log').open('w') as log:
            subprocess.run([find_blender(),'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'validation'/script),
                '--',*args,str(report)],stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=True,timeout=240)
    assert before==motion.read_bytes()
    results.append({'label':label,'blend':str(blend),'input_unchanged':True})
    if label=='LongSword':
        old=json.loads((ROOT/'validation/m4-correction/LongSword-example/corrected-motion.json').read_text(encoding='utf-8'))
        new=json.loads((blend.parent/'corrected-motion.json').read_text(encoding='utf-8'))
        names=[b['name'] for b in old['skeleton']['bones']]
        oldq=np.array([r['positions'] for r in old['frames']]);newq=np.array([r['positions'] for r in new['frames']])
        checks=[]
        for name in ('pelvis','foot_l','foot_r'):
            j=names.index(name);a=np.linalg.norm(np.diff(oldq[:,j],axis=0),axis=1);b=np.linalg.norm(np.diff(newq[:,j],axis=0),axis=1)
            checks.append({'joint':name,'old_max_step_m':float(a.max()),'new_max_step_m':float(b.max()),
                'frame377_before_m':float(a[376]),'frame377_after_m':float(b[376])})
        assert all(c['frame377_after_m']<c['frame377_before_m'] for c in checks if c['joint'].startswith('foot'))
        assert all(c['new_max_step_m']<c['old_max_step_m']*.6 for c in checks if c['joint'].startswith('foot'))
        (e/'transition-comparison.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
(e/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False),flush=True)
