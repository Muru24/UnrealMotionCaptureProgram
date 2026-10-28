"""Run the GUI's default worker sequence from a fresh video, then check delivery."""
import argparse,json,time,traceback
from pathlib import Path
import cv2
from app.gui_jobs import JobSettings,new_output,run_job
from app.automatic_postprocess import process_sam_result
from app.motion_job import add_motion_result
from app.builtin_models import automatic_preview
from app.model_preview import metadata
from app.final_results import list_final_results
from app.user_models import selected

def run(source):
    source=Path(source).resolve();out=new_output(source,'sam3d');settings=JobSettings(stage='sam3d',single_person=True,tracking_method='sam2')
    started=time.monotonic();last=[0.];result={'source':str(source),'output':str(out),'model_id':selected(),'settings':'GUI default SAM3D + SAM2, full candidates','stages':{},'status':'running'}
    def progress(done,total):
        now=time.monotonic()
        if now-last[0]>20:
            print('PROGRESS',done,total,round(now-started,1),flush=True);last[0]=now
    def stage(name,fn):
        print('STAGE',name,flush=True);start=time.monotonic();value=fn();result['stages'][name]={'seconds':time.monotonic()-start};return value
    print('FRESH_OUTPUT',out,flush=True)
    try:
        report=stage('tracking_and_sam3d',lambda:run_job(source,out,settings,lambda:False,progress))
        report.update(stage('automatic_postprocess',lambda:process_sam_result(out,source,lambda:False,progress,lambda text:print('PHASE',text,flush=True))))
        report.update(stage('motion',lambda:add_motion_result(out,source,report)))
        report.update(stage('model',lambda:automatic_preview(out,progress=progress)))
        if report.get('motion_error') or report.get('model_preview_error'):raise RuntimeError(report.get('motion_error') or report['model_preview_error'])
        preview=Path(report['model_preview']);info=metadata(preview);raw=json.loads((out/'sam3d.json').read_text(encoding='utf-8'));tracking=json.loads((out/'sam-tracking.json').read_text(encoding='utf-8'))
        count=len(raw['frames']);assert count==len(tracking['frames'])==info['frames']
        for video in (out/'overlay.mp4',preview):
            cap=cv2.VideoCapture(str(video));assert cap.isOpened() and round(cap.get(cv2.CAP_PROP_FRAME_COUNT))==count,str(video)
            for index in (0,count//4,count//2,count-1):
                cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,image=cap.read();assert ok and image is not None,(video,index)
            cap.release()
        assert (preview.parent/'Model_Animation.fbx').is_file() and (preview.parent/'Model_Animation.blend').is_file()
        assert any(row.root==out and row.preview==preview for row in list_final_results(out.parent))
        result.update(frames=count,preview=str(preview),tracking_metrics=report.get('tracking_metrics'),postprocess=report['automatic_postprocess'],model_metadata=info,
            fresh_tracking=True,source_cache_reused=False,status='completed_with_warnings' if report.get('model_quality_warnings') or report['automatic_postprocess']['status']=='partial' else 'completed')
    except BaseException as exc:
        result.update(status='failed',error=str(exc),traceback=traceback.format_exc());raise
    finally:
        result['elapsed_seconds']=time.monotonic()-started
        if out.is_dir():(out/'full-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print('VALIDATION_RESULT',result['status'],round(result['elapsed_seconds'],1),out,flush=True)
    return out

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source');args=parser.parse_args();run(args.source)
