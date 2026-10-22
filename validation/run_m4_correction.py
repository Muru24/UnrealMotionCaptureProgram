"""No inference: save corrected LongSword, reopen Blender and make comparison evidence."""
from pathlib import Path
import json,subprocess,hashlib
import numpy as np
import cv2
from app.animation_job import ROOT,export_animation,find_blender

e=ROOT/'validation/m4-correction';e.mkdir(exist_ok=True)
motion=ROOT/'outputs/LongSword_sam3d_20261020_133149_13dbea63/motion/motion.json'
original=motion.read_bytes();raw=json.loads(original);blend=export_animation(motion)
corrected=blend.parent/'corrected-motion.json';data=json.loads(corrected.read_text(encoding='utf-8'))
with (e/'blender-reopen.log').open('w',encoding='utf-8') as log:
    subprocess.run([find_blender(),'--background','--factory-startup','--python-exit-code','1','--python',
        str(ROOT/'validation/verify_m4_blender.py'),'--',str(blend.parent),str(corrected),str(e/'reopen.json')],
        stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=180,check=True)
names=[b['name'] for b in data['skeleton']['bones']];parents=[None if b['parent'] is None else names.index(b['parent']) for b in data['skeleton']['bones']]
before=np.array([r['positions'] for r in raw['frames']],float);after=np.array([r['positions'] for r in data['frames']],float)
contacts=data['correction']['frames'];stats=[]
for side,s in (('l',0),('r',1)):
    ankle=names.index('foot_'+side);toe=names.index('ball_'+side)
    mask=np.array([r['feet'][s]=='inferred_contact' for r in contacts]);steps=mask[1:]&mask[:-1]
    error_before=np.linalg.norm(np.diff(before[:,ankle],axis=0),axis=1)[steps]
    error_after=np.linalg.norm(np.diff(after[:,ankle],axis=0),axis=1)[steps]
    # Exclude contact run boundaries, not actual within-run motion.
    stats.append({'side':side,'inferred_contact_frames':int(mask.sum()),'contact_height_error_m':float(np.max(np.abs(after[mask,ankle,2]-.07))),
        'contact_step_before_mean_m':float(np.mean(error_before)),'contact_step_after_mean_m':float(np.mean(error_after)),
        'minimum_ankle_z_m':float(np.min(after[:,ankle,2])),'minimum_toe_z_m':float(np.min(after[:,toe,2]))})
    assert stats[-1]['contact_height_error_m']<1e-6
    assert stats[-1]['minimum_ankle_z_m']>=.07-1e-6 and stats[-1]['minimum_toe_z_m']>=.03-1e-6
    assert stats[-1]['contact_step_after_mean_m']<stats[-1]['contact_step_before_mean_m']
arms=[]
for side in ('l','r'):
    hand=names.index('hand_'+side);shoulder=names.index('upperarm_'+side)
    metric=lambda q:float(np.mean(np.linalg.norm(np.diff(q[:,hand]-q[:,shoulder],n=2,axis=0),axis=1)))
    arms.append({'side':side,'relative_wrist_second_difference_before_m':metric(before),'after_m':metric(after)})
    assert arms[-1]['after_m']<arms[-1]['relative_wrist_second_difference_before_m']
report={'version':'0.7.1','blend':str(blend),'corrected_motion':str(corrected),'frames':len(before),'feet':stats,'arms':arms,
        'original_motion_unchanged':original==motion.read_bytes(),'raw_motion_sha256':hashlib.sha256(original).hexdigest(),
        'not_accuracy_metric':True,'world_trajectory_is_contact_estimate':True,
        'unresolved_ground_collisions':sum('unresolved_ground_collision' in r['feet'] for r in contacts)}
assert report['original_motion_unchanged'] and report['unresolved_ground_collisions']==0
(e/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
writer=cv2.VideoWriter(str(e/'before-after.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),float(data['video']['fps']),(1280,720))
assert writer.isOpened()
view_center=np.zeros(2)
def project(p,offset):
    x,y,z=p;x-=view_center[0];y-=view_center[1]
    return (round(offset+340+(x*.94-y*.34)*200),round(645-z*260))
for i in range(len(before)):
    frame=np.full((720,1280,3),(20,14,9),np.uint8)
    for q,offset,label in ((before[i],0,'Before: M3 positions / fixed pelvis'),(after[i],640,'After: SLERP + inferred ground contact')):
        view_center=q[0,:2].copy()
        cv2.putText(frame,label,(offset+15,30),cv2.FONT_HERSHEY_SIMPLEX,.52,(220,225,230),1,cv2.LINE_AA)
        for x in np.arange(-5,5.1,.5):cv2.line(frame,project((x,-2,0),offset),project((x,2,0),offset),(55,48,38),1)
        for y in np.arange(-2,2.1,.5):cv2.line(frame,project((-5,y,0),offset),project((5,y,0),offset),(55,48,38),1)
        for j,parent in enumerate(parents):
            if parent in (None,0) or not np.isfinite(q[[parent,j]]).all():continue
            color=(220,170,90) if names[j].endswith('_l') else (70,165,230) if names[j].endswith('_r') else (150,220,110)
            cv2.line(frame,project(q[parent],offset),project(q[j],offset),color,4,cv2.LINE_AA)
        for s,side in enumerate(('l','r')):
            p=q[names.index('foot_'+side)]
            if np.isfinite(p).all():cv2.circle(frame,project(p,offset),6,(100,240,100) if offset and contacts[i]['feet'][s]=='inferred_contact' else (190,190,190),-1)
    cv2.putText(frame,f'Frame {i} / {len(before)}',(20,695),cv2.FONT_HERSHEY_SIMPLEX,.6,(220,225,230),1)
    writer.write(frame)
    if i==100:
        ok,encoded=cv2.imencode('.jpg',frame);assert ok;(e/'comparison-frame100.jpg').write_bytes(encoded.tobytes())
writer.release()
cap=cv2.VideoCapture(str(e/'before-after.mp4'));count=0
while cap.read()[0]:count+=1
cap.release();assert count==len(before)
with (e/'render.log').open('w',encoding='utf-8') as log:
    subprocess.run([find_blender(),'--background','--factory-startup','--python-exit-code','1','--python',
        str(ROOT/'validation/render_m4_preview.py'),'--',str(blend),str(e/'preview')],stdout=log,stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=180,check=True)
print(json.dumps(report,ensure_ascii=False),flush=True)
