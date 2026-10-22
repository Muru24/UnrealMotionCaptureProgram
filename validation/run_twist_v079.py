"""Use immutable saved inference; independently reopen new Blender exports."""
import json,sys,subprocess,hashlib,shutil,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.animation_job import export_animation,find_blender
from core.motion.skeleton import definition
folder=ROOT/'validation/twist-v079';folder.mkdir(exist_ok=True)
def blender(script,args,log):
    with (folder/log).open('w',encoding='utf-8') as stream:
        subprocess.run([find_blender(),'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'validation'/script),'--',*map(str,args)],stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=240,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
blender('test_twist_v079_blender.py',[folder/'properties.json'],'properties.log')
status=json.loads((ROOT/'validation/dance-v074/status.json').read_text(encoding='utf-8'))
fixture=folder/'fixture/motion';fixture.mkdir(parents=True,exist_ok=True);spec=definition();rows=[]
for i in range(150):
    a=i*.03;c=math.cos(a);s=math.sin(a)
    points=[[c*b['head'][0]-s*b['head'][1],s*b['head'][0]+c*b['head'][1],b['head'][2]] for b in spec['bones']]
    if 24<=i<=26 or 60<=i<=80:
        for name in ('lowerarm_l','hand_l'):points[[b['name'] for b in spec['bones']].index(name)]=None
    if 100<=i<=110:points=[None]*22
    rows.append({'frame_index':i,'tracking_segment':int(i>=120),'scene_index':int(i>=120),'positions':points})
p=fixture/'motion.json';p.write_text(json.dumps({'schema':'standard_motion_positions_v1','skeleton':spec,'video':{'fps':30},'frames':rows}),encoding='utf-8')
motions=[('dance',Path(status['motion'])),('LongSword',ROOT/'outputs/LongSword_sam3d_20261020_133149_13dbea63/motion/motion.json'),('synthetic',ROOT/'validation/m4-correction/synthetic/motion/motion.json'),('gaps',p)]
results=[]
for label,motion in motions:
    before=hashlib.sha256(motion.read_bytes()).hexdigest();blend=export_animation(motion)
    for script,kind,args in [('verify_m4_blender.py','reopen',[blend.parent,blend.parent/'corrected-motion.json']),('verify_m4_interpolation.py','fractional',[blend.parent])]:
        blender(script,[*args,folder/f'{label}-{kind}.json'],f'{label}-{kind}.log')
    assert hashlib.sha256(motion.read_bytes()).hexdigest()==before
    data=json.loads((blend.parent/'animation.json').read_text(encoding='utf-8'));policy=data['orientation_policy']
    assert policy['max_applied_twist_step_degrees']<=120/data['fps']+1e-5
    corrected=json.loads((blend.parent/'corrected-motion.json').read_text(encoding='utf-8'))
    if label in ('dance','LongSword','synthetic'):
        prior=json.loads((ROOT/f'validation/jitter-v078/{label}-example/corrected-motion.json').read_text(encoding='utf-8'))
        assert corrected==prior,'Twist solver must not alter correction/ground/root positions'
    if label=='gaps':
        assert policy['short_roll_reconnections']>0 and policy['long_roll_restarts']>0
        assert any(s['kind']=='long_missing' and s['bone']=='lowerarm_l' for s in policy['missing_spans'])
        j=data['bone_names'].index('lowerarm_l')
        for i in [24,25,26,*range(60,81),*range(100,111)]:assert data['frames'][i]['local_quaternions_wxyz'][j] is None
    example=folder/f'{label}-example';example.mkdir(exist_ok=False)
    for name in ('animation.blend','animation.json','corrected-motion.json','report.json'):shutil.copyfile(blend.parent/name,example/name)
    result={'label':label,'blend':str(blend),'frames':len(data['frames']),'motion_sha256':before,'original_unchanged':True,'policy':policy}
    results.append(result);print(json.dumps({k:v for k,v in result.items() if k!='policy'},ensure_ascii=False),flush=True)
(folder/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
