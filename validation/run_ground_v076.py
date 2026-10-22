"""CPU-only saved-motion exports and independent Blender reopening."""
import json,sys,subprocess,shutil,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.animation_job import export_animation,find_blender
folder=ROOT/'validation/ground-v076';folder.mkdir(exist_ok=True)
status=json.loads((ROOT/'validation/dance-v074/status.json').read_text(encoding='utf-8'))
motions=[('dance',Path(status['motion'])),('LongSword',ROOT/'outputs/LongSword_sam3d_20261020_133149_13dbea63/motion/motion.json'),
         ('synthetic',ROOT/'validation/m4-correction/synthetic/motion/motion.json')]
results=[]
for label,motion in motions:
    before=hashlib.sha256(motion.read_bytes()).hexdigest();example=folder/f'{label}-example'
    if example.is_dir():
        previous=json.loads((example/'report.json').read_text(encoding='utf-8'))
        assert previous['motion_sha256']==before
        assert previous['correction_sha256']==hashlib.sha256((ROOT/'core/motion/correction.py').read_bytes()).hexdigest()
        assert previous['solver_sha256']==hashlib.sha256((ROOT/'tools/animate_reference_rig.py').read_bytes()).hexdigest()
        blend=example/'animation.blend'
    else:blend=export_animation(motion)
    for script,kind,args in [('verify_m4_blender.py','reopen',[str(blend.parent),str(blend.parent/'corrected-motion.json')]),
                            ('verify_m4_interpolation.py','fractional',[str(blend.parent)])]:
        with (folder/f'{label}-{kind}.log').open('w',encoding='utf-8') as log:
            subprocess.run([find_blender(),'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'validation'/script),'--',*args,str(folder/f'{label}-{kind}.json')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    assert hashlib.sha256(motion.read_bytes()).hexdigest()==before
    if not example.is_dir():
        example.mkdir(exist_ok=False)
        for name in ('animation.blend','animation.json','corrected-motion.json','report.json'):shutil.copyfile(blend.parent/name,example/name)
    data=json.loads((blend.parent/'corrected-motion.json').read_text(encoding='utf-8'))
    names=[b['name'] for b in data['skeleton']['bones']];feet=[names.index('foot_'+s) for s in ('l','r')]
    q=np.array([[[np.nan]*3 if p is None else p for p in r['positions']] for r in data['frames']],dtype=float)
    if label=='dance':
        np.testing.assert_allclose(q[175:186,feet,2],.07,atol=1e-5)
        assert all(any(r['image_ground_support']) for r in data['correction']['frames'][175:186])
        assert max(q[175:186,names.index('pelvis'),2])<.85
    result={'label':label,'blend':str(blend),'frames':len(q),'original_motion_sha256':before,'original_unchanged':True,
            'image_ground_evidence_used':data['correction']['image_ground_evidence_used'],
            'maximum_ankle_step_m':float(np.nanmax(np.linalg.norm(np.diff(q[:,feet],axis=0),axis=2)))}
    results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
(folder/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
