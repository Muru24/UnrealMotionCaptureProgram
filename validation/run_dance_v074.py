"""User-requested single-video extraction, using the unchanged GUI pipeline."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,time,traceback
from app.gui_jobs import ROOT,JobSettings,new_output,run_job
from app.knee_job import digest
from app.automatic_postprocess import process_sam_result
from app.motion_job import ensure_motion
from app.animation_job import export_animation

source=Path('C:/Users/user1/Desktop/애니메이션추출/이게 실제로 가능한 춤이였다고_ #부리부리마신소환춤.mp4')
e=ROOT/'validation/dance-v074';e.mkdir(exist_ok=True)
if (e/'status.json').exists():raise FileExistsError('Existing run manifest; inspect and resume completed stages instead of rerunning blindly.')
output=new_output(source,'sam3d');source_hash=digest(source)
state={'version':'0.7.4','source':str(source),'source_sha256':source_hash,'output':str(output),
       'status':'running','phase':'SAM2 person tracking / SAM3D','done':0,'total':414}
started=time.monotonic();last_write=0.;last_print=0.
def save():
    state['elapsed_seconds']=round(time.monotonic()-started,1)
    state['updated_at']=datetime.now(timezone(timedelta(hours=9))).isoformat()
    temporary=e/'status.pending.json';temporary.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(e/'status.json')
def progress(done,total):
    global last_write,last_print
    state.update(done=int(done),total=int(total));now=time.monotonic()
    if now-last_write>1:save();last_write=now
    if now-last_print>15:print(state['phase'],done,total,flush=True);last_print=now
def phase(text):
    state.update(phase=text,done=0,total=0);save();print(text,flush=True)
save()
try:
    settings=JobSettings(stage='sam3d',tracking_method='sam2',target_index=0,target_frame=0)
    report=run_job(source,output,settings,lambda:False,progress)
    state['raw_report']=report;save()
    post=process_sam_result(output,source,lambda:False,progress,phase)
    state['automatic_postprocess']=post;save()
    phase('standard skeleton conversion')
    motion,cache=ensure_motion(output,source,post)
    state.update(motion=str(motion),motion_status=cache);save()
    phase('v0.7.4 ground/smoothing + Blender animation')
    blend=export_animation(motion);state['blend']=str(blend)
    assert digest(source)==source_hash
    state.update(status='completed',phase='completed',input_unchanged=True);save()
    print(json.dumps({'output':str(output),'blend':str(blend),'automatic_status':post['automatic_postprocess']['status']},ensure_ascii=False),flush=True)
except BaseException as error:
    state.update(status='cancelled' if isinstance(error,KeyboardInterrupt) else 'failed',error=str(error));save()
    traceback.print_exc();raise
