"""Check the user-requested video artifacts after the existing pipeline completes."""
from pathlib import Path
import json,subprocess
import cv2,numpy as np
from app.animation_job import ROOT,find_blender
from app.knee_job import digest

e=ROOT/'validation/dance-v074';state=json.loads((e/'status.json').read_text(encoding='utf-8'))
assert state['status']=='completed';out=Path(state['output']);blend=Path(state['blend']);source=Path(state['source'])
assert digest(source)==state['source_sha256']
raw=json.loads((out/'sam3d.json').read_text(encoding='utf-8'));motion=json.loads(Path(state['motion']).read_text(encoding='utf-8'))
corrected=json.loads((blend.parent/'corrected-motion.json').read_text(encoding='utf-8'))
count=len(raw['frames']);assert len(motion['frames'])==len(corrected['frames'])==count
for frames in (raw['frames'],motion['frames'],corrected['frames']):assert [r['frame_index'] for r in frames]==list(range(count))
def decode(path,samples=False):
    cap=cv2.VideoCapture(str(path));assert cap.isOpened();i=0;images=[]
    chosen=set(np.linspace(0,count-1,8,dtype=int).tolist())
    while True:
        ok,frame=cap.read()
        if not ok:break
        if samples and i in chosen:
            image=cv2.resize(frame,(270,480));cv2.putText(image,f'Frame {i}',(10,25),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,255),2);images.append(image)
        i+=1
    cap.release();return i,images
decoded={};sheets=[]
paths=[('source',source),('mask',out/'mask-tracking.mp4'),('raw_overlay',out/'overlay.mp4')]
post=state['automatic_postprocess']
if post.get('reconnection_directory'):paths.append(('reconnected',Path(post['reconnection_directory'])/'reconnection-overlay.mp4'))
for label,path in paths:
    n,images=decode(path,label=='raw_overlay');decoded[label]=n;assert n==count
    if images:
        sheet=np.concatenate([np.concatenate(images[:4],axis=1),np.concatenate(images[4:],axis=1)],axis=0)
        ok,encoded=cv2.imencode('.jpg',sheet);assert ok;(e/'review.jpg').write_bytes(encoded.tobytes())
for script,args,kind in (
    ('verify_m4_blender.py',[str(blend.parent),str(blend.parent/'corrected-motion.json')],'blender-reopen'),
    ('verify_m4_interpolation.py',[str(blend.parent)],'blender-fractional')):
    with (e/f'{kind}.log').open('w') as log:
        subprocess.run([find_blender(),'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'validation'/script),
            '--',*args,str(e/f'{kind}.json')],stdout=log,stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=240,check=True)
report={'version':'0.7.4','frames':count,'decoded':decoded,'input_sha256_unchanged':True,
        'tracking_observations':sum(r.get('tracking',{}).get('state')=='tracked' for r in raw['frames']),
        'automatic_status':post['automatic_postprocess']['status'],'source_kind':motion['source_kind'],
        'output':str(out),'blend':str(blend),'not_ground_truth_pose_accuracy':True}
(e/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False),flush=True)
