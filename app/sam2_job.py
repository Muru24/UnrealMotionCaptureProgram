"""CPU-side selection and cancellable SAM 2 child; no desktop Torch import."""
from pathlib import Path
import hashlib
import json
import subprocess
import time
import shutil
import cv2
import numpy as np
from app.gui_jobs import ROOT


def validate_runtime():
    directory=ROOT/'models/sam2'
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    path=directory/'sam2.1_hiera_small.pt'
    with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    if digest!=manifest['sha256'] or digest!='6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38':
        raise ValueError('SAM 2 checkpoint integrity check failed.')
    if not (ROOT/'.validation/sam2/source/sam2/build_sam.py').is_file():raise ValueError('SAM 2 source is missing.')
    python=ROOT/'.validation/sam3d/env/Scripts/python.exe'
    if not python.is_file():raise ValueError('SAM 2 shared CUDA runtime is missing.')
    return python


def build_sam2_plan(source,metadata,settings,cancelled,progress,backend_factory,output):
    from app.sam3d_job import terminate_worker
    if cancelled():raise KeyboardInterrupt
    python=validate_runtime()
    from app.target_start import find_target_start
    start,frame,boxes=find_target_start(source,settings,cancelled,backend_factory)
    index=settings.target_index
    if not len(boxes):raise ValueError(f'{start}프레임에 인물 후보가 없습니다. 다른 위치에서 대상 확인을 해 주세요.')
    if index is None:
        if len(boxes)!=1:raise ValueError(f'{start}프레임의 대상 확인 후 인물 번호를 선택해 주세요.')
        index=0
    if index>=len(boxes):raise ValueError('선택한 대상이 없습니다.')
    initial=np.asarray(boxes[index],dtype=float)
    if initial.shape!=(4,) or not np.isfinite(initial).all() or np.any(initial[2:]<=initial[:2]):raise ValueError('Invalid initial person box.')
    if cancelled():raise KeyboardInterrupt
    output=Path(output)
    request={'source':str(Path(source).resolve()),'initial_box':initial.tolist(),'target_index':index,'initial_frame_index':start,
             'video':{'width':metadata.width,'height':metadata.height,'fps':metadata.fps,'frame_count':metadata.frame_count}}
    (output/'sam2-request.json').write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8')
    with (output/'sam2-runtime.log').open('w',encoding='utf-8') as log:
        child=subprocess.Popen([str(python),'-u',str(ROOT/'app/sam2_worker.py'),str(output)],cwd=ROOT,
            stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            while child.poll() is None:
                if cancelled():raise KeyboardInterrupt
                try:
                    status=json.loads((output/'sam2-progress.json').read_text(encoding='utf-8'))
                    progress(status['done'] if status['phase']=='mask' else 0,metadata.frame_count*2)
                except (OSError,ValueError,KeyError):pass
                time.sleep(.15)
            if child.returncode:raise ValueError(f'SAM 2 추적 실패. 로그 확인: {output / "sam2-runtime.log"}')
        finally:
            if child.poll() is None:terminate_worker(child)
            # Only temporary folders inside this newly created output belong to us.
            base=output.resolve()
            for folder in output.glob('sam2-frames-*'):
                if folder.is_dir() and not folder.is_symlink() and folder.resolve().is_relative_to(base):
                    shutil.rmtree(folder)
    if cancelled():raise KeyboardInterrupt
    plan=json.loads((output/'sam2-plan.json').read_text(encoding='utf-8'))
    if plan['status']!='completed' or not plan['frames']:raise ValueError('Incomplete SAM 2 plan.')
    return plan


def main():
    import argparse
    from app.gui_jobs import JobSettings,make_backend,read_source
    from core.pose2d.metrics import tracking_metrics
    parser=argparse.ArgumentParser(description='SAM 2 tracking-only comparison; no SAM3D inference')
    parser.add_argument('source',type=Path);parser.add_argument('--target-index',type=int);parser.add_argument('--target-frame',type=int);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();metadata,_=read_source(args.source)
    args.output.mkdir(parents=True,exist_ok=False)
    settings=JobSettings(stage='sam3d',target_index=args.target_index,tracking_method='sam2',target_frame=args.target_frame)
    try:
        plan=build_sam2_plan(args.source,metadata,settings,lambda:False,lambda *a:None,make_backend,args.output)
        metrics=tracking_metrics(plan,metadata.fps)
        (args.output/'tracking-metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
        (args.output/'report.json').write_text(json.dumps({'status':'completed','stage':'tracking_only',
            'sam3d_inferred':False,'tracking_metrics':metrics},indent=2),encoding='utf-8')
        print(json.dumps({'frames':len(plan['frames']),'tracked':len(plan['frames'])-metrics['missing_frames'],
                         'max_gap_seconds':metrics['max_gap_seconds']}))
    except BaseException as error:
        (args.output/'report.json').write_text(json.dumps({'status':'cancelled' if isinstance(error,KeyboardInterrupt) else 'failed',
            'stage':'tracking_only'}),encoding='utf-8');raise


if __name__=='__main__':main()
