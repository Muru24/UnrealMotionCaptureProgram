"""Run the optional SAM environment without changing the desktop dependencies."""
from core.video.limits import MAX_VIDEO_FRAMES
import json
from pathlib import Path
import subprocess
import time
import os
from dataclasses import asdict
import cv2
import numpy as np

from app.gui_jobs import ROOT, read_source
from core.pose2d.tracker import TargetTracker


def terminate_worker(process):
    if process.poll() is not None:return
    if os.name=='nt':
        # Windows venv python.exe launches a real Python child. Killing only
        # the launcher leaves the CUDA worker running after GUI cancellation.
        result=subprocess.run(['taskkill.exe','/PID',str(process.pid),'/T','/F'],
                              capture_output=True,timeout=15,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode and process.poll() is None:
            raise RuntimeError('Cannot stop the SAM worker process tree.')
    else:
        process.terminate()
    process.wait(timeout=15)


def select_roi(boxes, index, width, height):
    if len(boxes) == 0:
        raise ValueError('첫 프레임에서 인물을 찾지 못했습니다. 인물이 보이는 영상으로 시작해 주세요.')
    index = max(range(len(boxes)), key=lambda i: (boxes[i][2]-boxes[i][0])*(boxes[i][3]-boxes[i][1])) if index is None else index
    if index >= len(boxes):
        raise ValueError('선택한 대상이 없습니다. 대상 확인을 다시 실행해 주세요.')
    x1,y1,x2,y2 = map(float, boxes[index])
    dx,dy = (x2-x1)*.25,(y2-y1)*.15
    return [max(0,x1-dx), max(0,y1-dy), min(width,x2+dx), min(height,y2+dy)]


def build_tracking_plan(source, metadata, settings, cancelled, progress, backend_factory, *, motion_prediction=True, regional_recovery=True, long_reidentify=True, rival_guard=True, reconnect_identity_guard=True):
    max_missing=max(5,round(metadata.fps*.4))
    tracker=TargetTracker(target_index=settings.target_index,max_missing=max_missing,
                          reconnection_iou=.25,reconnect_confirmations=2,gap_appearance_limit=.5,multi_cue=True,
                          motion_fps=metadata.fps if motion_prediction else None,fast_reconnect=motion_prediction,
                          long_reidentify=motion_prediction and long_reidentify,rival_guard=motion_prediction and rival_guard,
                          reconnect_identity_guard=motion_prediction and reconnect_identity_guard)
    backend=backend_factory(settings)
    started=time.perf_counter()
    capture=cv2.VideoCapture()
    records=[]
    from core.pose2d.motion import BodyMotion
    observer=BodyMotion(metadata.fps) if not motion_prediction else None
    try:
        if not capture.open(str(Path(source).resolve())):
            raise ValueError('Cannot reopen video for person tracking.')
        while True:
            if cancelled():raise KeyboardInterrupt
            ok,frame=capture.read()
            if not ok:break
            index=len(records)
            if index>=MAX_VIDEO_FRAMES or frame.shape[:2]!=(metadata.height,metadata.width):
                raise ValueError('Tracking video dimensions or frame limit exceeded.')
            boxes=backend.detect(frame)
            from core.pose2d.association import collapse_same_skeleton
            keypoints=backend.association_keypoints(frame,boxes) if hasattr(backend,'association_keypoints') and (not tracker.latched or tracker.can_reidentify) else None
            recovery={'attempted':False,'added':0}
            previous_reason=records[-1]['tracking']['reason'] if records else None
            if regional_recovery and previous_reason!='reconnection_pending':
                if cancelled():raise KeyboardInterrupt
                from core.pose2d.recovery import recover_candidates
                boxes,keypoints,recovery=recover_candidates(frame,tracker,backend,boxes,keypoints)
                if cancelled():raise KeyboardInterrupt
            boxes,keypoints,suppressed=collapse_same_skeleton(boxes,keypoints,enabled=tracker.box is not None)
            legacy_prediction=None if tracker.box is None else ((tracker.box[:2]+tracker.box[2:])/2+
                tracker.velocity*(tracker.missing+1)+(observer.box_offset if observer is not None else 0))
            decision=tracker.select(frame,boxes,keypoints)
            if observer is not None:
                tracker.motion_diagnostics={'predicted_center':None if legacy_prediction is None else legacy_prediction.tolist(),
                                            'observed_center':None,'prediction_only':True,'prediction_method':'legacy_bbox_velocity'}
                if decision.bbox is not None:
                    selected=next(i for i,b in enumerate(boxes) if np.allclose(b,decision.bbox))
                    z,kind,_,hip,shoulder=observer.measurement(decision.bbox,None if keypoints is None else tuple(v[selected] for v in keypoints))
                    observer.accept_offsets(decision.bbox,z,hip,shoulder)
                    tracker.motion_diagnostics.update(observed_center=z.tolist(),observation_kind=kind,prediction_only=False)
            roi=None if decision.bbox is None else select_roi([decision.bbox],0,metadata.width,metadata.height)
            records.append({'frame_index':index,'timestamp':index/metadata.fps,
                            'roi':roi,'person_bbox':decision.bbox,'tracking':asdict(decision.info),
                            'people_detected':len(boxes),'detector_diagnostics':getattr(backend,'last_detection_diagnostics',{}),
                            'skeleton_duplicates':suppressed,'association_scores':tracker.association_diagnostics,
                            'motion':tracker.motion_diagnostics})
            records[-1]['regional_recovery']=recovery
            records[-1]['tracking_segment']=tracker.segment
            if index%15==0:progress(index+1,metadata.frame_count*2)
        if not records:raise ValueError('No decoded frames for tracking.')
    finally:
        capture.release();backend.close()
    return {'version':1,'status':'completed','detector':'HumanArt YOLOX tiny',
            'association_model':'RTMPose-m COCO17','elapsed_seconds':time.perf_counter()-started,
            'selection':'detector_tracker_target_id','target_id':1,'target_index':settings.target_index,
            'policy':{'max_missing_frames':max_missing,'reconnection_iou':.25,
                      'reconnect_confirmations':2,'gap_appearance_limit':.5,
                      'fast_reconnect':bool(getattr(tracker,'fast_reconnect',False)),
                      'regional_recovery':regional_recovery and hasattr(backend,'detect_region'),
                      'long_reidentify':tracker.long_reidentify,
                      'rival_guard':tracker.other_people is not None,
                        'reconnect_identity_guard':tracker.reconnect_identity_guard,
                      'weights':{'iou':.25,'center':.25,'skeleton':.3,'appearance':.2},
                      'missing_skeleton':'renormalize_available_weights','appearance':'HSV_histograms_not_learned_ReID'},
            'motion_prediction':motion_prediction,'motion_units':'image_pixels_and_seconds',
            'motion_policy':None if not motion_prediction else {'model':'constant_velocity_Kalman',
                'sources':['hip','shoulder_with_hip_offset','box_fallback'],'innovation_gate_squared':9.21,
                'measurement_noise':getattr(tracker.motion,'transition_noise_policy','fixed_source_noise'),
                'overlap':'temporary_hold_with_confirmation','prediction_is_not_pose':True},
            'frames':records}


def run_sam3d(source, output, settings, cancelled, progress, backend_factory):
    python = ROOT/'.validation/sam3d/env/Scripts/python.exe'
    if not python.is_file():
        raise ValueError('SAM GPU 환경이 없습니다: .validation/sam3d/env')
    metadata, _ = read_source(source)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    try:
        if getattr(settings,'tracking_method','pose')=='sam2':
            from app.sam2_job import build_sam2_plan
            plan=build_sam2_plan(source,metadata,settings,cancelled,progress,backend_factory,output)
        else:
            plan=build_tracking_plan(source,metadata,settings,cancelled,progress,backend_factory)
    except BaseException as exc:
        (output/'report.json').write_text(json.dumps({'status':'cancelled' if isinstance(exc,KeyboardInterrupt) else 'failed',
                                                    'stage':'person_tracking'}),encoding='utf-8')
        raise
    (output/'sam-tracking.json').write_text(json.dumps(plan,allow_nan=False),encoding='utf-8')
    from core.pose2d.metrics import tracking_metrics
    metrics=tracking_metrics(plan,metadata.fps)
    (output/'tracking-metrics.json').write_text(json.dumps(metrics,allow_nan=False,indent=2),encoding='utf-8')
    if cancelled():
        (output/'report.json').write_text(json.dumps({'status':'cancelled','stage':'person_tracking'}),encoding='utf-8')
        raise KeyboardInterrupt
    from app.knee_job import digest
    request = {'source':str(Path(source).resolve()), 'source_sha256':digest(source), 'video':metadata.to_dict()}
    (output/'sam-request.json').write_text(json.dumps(request), encoding='utf-8')
    with (output/'sam-runtime.log').open('w',encoding='utf-8') as log:
        process = subprocess.Popen([str(python), '-u', str(ROOT/'app/sam3d_worker.py'), str(output)],
                                   cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            while process.poll() is None:
                if cancelled():
                    raise KeyboardInterrupt
                try:
                    done = int((output/'frames-progress.txt').read_text())
                    progress(metadata.frame_count+done,metadata.frame_count*2)
                except (OSError,ValueError):
                    pass
                time.sleep(.15)
            if process.returncode:
                if not (output/'report.json').is_file():
                    (output/'report.json').write_text(json.dumps({'status':'failed','stage':'sam_inference'}),encoding='utf-8')
                raise ValueError(f'SAM 실행 실패. GPU 메모리와 로그를 확인해 주세요: {output / "sam-runtime.log"}')
        finally:
            if process.poll() is None:
                terminate_worker(process)
                (output/'report.json').write_text(json.dumps({
                    'status':'cancelled' if cancelled() else 'failed',
                    'backend':'SAM 3D Body ViT-H CUDA',
                    'warnings':['부분 출력입니다. 완료 결과로 사용하지 마세요.']},ensure_ascii=False),encoding='utf-8')
    report=json.loads((output/'report.json').read_text(encoding='utf-8'))
    report['tracking_seconds']=plan['elapsed_seconds']
    report['appearance_kind']=('SAM2_visual_memory_not_identity_proof' if plan['selection']=='sam2_video_mask'
                               else 'HSV_histograms_not_learned_ReID')
    report['tracking_method']=getattr(settings,'tracking_method','pose')
    report['tracking_metrics']=metrics
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report
