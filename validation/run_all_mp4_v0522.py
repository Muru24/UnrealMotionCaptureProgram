"""Local batch using the unchanged GUI SAM2/SAM3D and automatic pipeline."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import json
import time
import traceback
import cv2
from app.gui_jobs import JobSettings, make_backend, new_output, read_source, run_job
from app.automatic_postprocess import process_sam_result
from app.knee_job import digest

EVIDENCE = ROOT/'validation/all-mp4-v0522'
EVIDENCE.mkdir(exist_ok=True)
MANIFEST = EVIDENCE/'batch.json'

def save(data):
    tmp = MANIFEST.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(MANIFEST)

def decode_count(path):
    cap = cv2.VideoCapture(str(path))
    count = 0
    try:
        while cap.read()[0]:
            count += 1
    finally:
        cap.release()
    return count

def main():
    if MANIFEST.exists():
        raise RuntimeError('Existing batch manifest: do not overwrite or rerun completed outputs.')
    sources = sorted(Path(r'C:\Users\user1\Desktop\애니메이션추출').glob('*.mp4'))
    batch = {'version':'v0.5.22', 'pipeline':'GUI SAM2 + SAM3D + automatic postprocess',
             'started':time.strftime('%Y-%m-%d %H:%M:%S'), 'status':'running', 'videos':[]}
    for source in sources:
        batch['videos'].append({'source':str(source),'status':'pending'})
    save(batch)
    for item in batch['videos']:
        source = Path(item['source'])
        try:
            item.update(status='preflight',started=time.time())
            save(batch)
            meta, frame = read_source(source)
            item.update(video=meta.to_dict(),source_sha256=digest(source))
            settings = JobSettings(stage='sam3d',tracking_method='sam2')
            backend = make_backend(settings)
            try:
                boxes = backend.detect(frame)
            finally:
                backend.close()
            if not len(boxes):
                raise ValueError('No first-frame person detected.')
            index = max(range(len(boxes)),key=lambda i:float((boxes[i][2]-boxes[i][0])*(boxes[i][3]-boxes[i][1])))
            item.update(target_index=index,first_frame_boxes=[list(map(float,b)) for b in boxes],
                        selection_policy='largest first-frame person; verify target in initial preview',
                        decoded_source_frames=decode_count(source))
            for i,b in enumerate(boxes):
                x1,y1,x2,y2=map(int,b)
                cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,0) if i==index else (0,180,255),2)
                cv2.putText(frame,f'TARGET {i}'+(' SELECTED' if i==index else ''),(x1,max(22,y1-8)),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,0),2)
            preview=EVIDENCE/f'target-{len([v for v in batch["videos"] if v.get("finished")])+1}.jpg'
            preview.write_bytes(cv2.imencode('.jpg',frame)[1].tobytes())
            item['initial_target_preview']=str(preview)
            settings=JobSettings(stage='sam3d',target_index=index,tracking_method='sam2')
            output=new_output(source,'sam3d');item.update(output=str(output),status='extracting',phase='SAM2 tracking / SAM3D')
            save(batch)
            last=[0.0]
            def progress(done,total):
                if time.monotonic()-last[0]>3:
                    item['progress']={'done':int(done),'total':int(total)}
                    save(batch);last[0]=time.monotonic()
            def phase(text):
                item['phase']=text;item.pop('progress',None);save(batch)
            print('START',source.name,flush=True)
            report=run_job(source,output,settings,lambda:False,progress)
            item.update(status='postprocessing',extraction_report=report);save(batch)
            post=process_sam_result(output,source,lambda:False,progress,phase)
            item['automatic_report']=post['automatic_postprocess']
            primary=Path(post['reconnection_directory'])/'reconnection-overlay.mp4' if 'reconnection_directory' in post else output/'overlay.mp4'
            item.update(primary_preview=str(primary),raw_preview=str(output/'overlay.mp4'),mask_preview=str(output/'mask-tracking.mp4'))
            item['verified_preview_frames']={str(p):decode_count(p) for p in (primary,output/'overlay.mp4',output/'mask-tracking.mp4')}
            expected=item['decoded_source_frames']
            if any(n!=expected for n in item['verified_preview_frames'].values()):
                raise ValueError('Preview decoded frame count differs from source; see manifest.')
            if digest(source)!=item['source_sha256']:
                raise ValueError('Source hash changed.')
            item['status']='completed' if item['automatic_report']['status']=='completed_with_estimates' else 'partial'
            metrics=output/'tracking-metrics.json'
            if metrics.exists():item['tracking_metrics']=json.loads(metrics.read_text(encoding='utf-8'))
            print('DONE',source.name,item['status'],flush=True)
        except Exception as exc:
            item.update(status='failed',error=str(exc),traceback=traceback.format_exc())
            print('FAILED',source.name,str(exc),flush=True)
        finally:
            item['finished']=time.time();save(batch)
    batch.update(status='finished',finished=time.strftime('%Y-%m-%d %H:%M:%S'))
    save(batch)
    print('BATCH FINISHED',flush=True)

if __name__=='__main__':main()
