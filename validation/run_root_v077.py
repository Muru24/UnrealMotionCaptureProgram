"""Verify root/airborne animation through saved inference and the real Blender pipeline."""
import json,sys,subprocess,shutil,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.animation_job import export_animation,find_blender
folder=ROOT/'validation/root-v077-release';folder.mkdir(exist_ok=True)
status=json.loads((ROOT/'validation/dance-v074/status.json').read_text(encoding='utf-8'))
motions=[('dance',Path(status['motion'])),('LongSword',ROOT/'outputs/LongSword_sam3d_20261020_133149_13dbea63/motion/motion.json'),
         ('synthetic',ROOT/'validation/m4-correction/synthetic/motion/motion.json')]
results=[]
for label,motion in motions:
    before=hashlib.sha256(motion.read_bytes()).hexdigest();blend=export_animation(motion)
    for script,kind,args in [('verify_m4_blender.py','reopen',[str(blend.parent),str(blend.parent/'corrected-motion.json')]),
                            ('verify_m4_interpolation.py','fractional',[str(blend.parent)])]:
        with (folder/f'{label}-{kind}.log').open('w',encoding='utf-8') as log:
            subprocess.run([find_blender(),'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'validation'/script),'--',*args,str(folder/f'{label}-{kind}.json')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    assert hashlib.sha256(motion.read_bytes()).hexdigest()==before
    example=folder/f'{label}-example';example.mkdir(exist_ok=False)
    for name in ('animation.blend','animation.json','corrected-motion.json','report.json'):shutil.copyfile(blend.parent/name,example/name)
    data=json.loads((blend.parent/'corrected-motion.json').read_text(encoding='utf-8'));names=[b['name'] for b in data['skeleton']['bones']]
    q=np.array([[[np.nan]*3 if p is None else p for p in r['positions']] for r in data['frames']],dtype=float)
    if label=='dance':
        np.testing.assert_allclose(q[175:186,[names.index('foot_l'),names.index('foot_r')],2],.07,atol=1e-5)
        assert q[:,0,2].max()>.1
    report=json.loads((blend.parent/'report.json').read_text(encoding='utf-8'))
    result={'label':label,'blend':str(blend),'frames':len(q),'original_motion_sha256':before,'original_unchanged':True,
        'root_motion_kind':data['root_motion_kind'],'root_motion_analysis':report['root_motion_analysis'],
        'driven_frames':sum(r['image_root_drive'] for r in data['correction']['frames']),
        'airborne_frames':sum(r['estimated_airborne'] for r in data['correction']['frames']),
        'root_xyz_range_m':(np.nanmax(q[:,0],axis=0)-np.nanmin(q[:,0],axis=0)).tolist()}
    results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
(folder/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
