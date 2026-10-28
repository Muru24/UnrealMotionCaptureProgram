"""Append finger animation in a separate output, preserving the 22-bone source."""
import json,subprocess,time,uuid,shutil,hashlib
from pathlib import Path
from app.animation_job import ROOT,find_blender
from app.knee_job import digest


def latest_hand_crop(folder):
    folder=Path(folder).resolve();raw=folder/'sam3d.json'
    if not raw.is_file():return None
    signature=digest(raw)
    for path in sorted(folder.glob('hand_crop_*/report.json'),key=lambda p:p.stat().st_mtime_ns,reverse=True):
        if path.is_symlink() or path.parent.is_symlink() or not path.resolve().is_relative_to(folder):continue
        try:
            data=json.loads(path.read_text(encoding='utf-8'))
            if data.get('schema')=='hand_crop_comparison_v1' and data.get('status')=='completed' and data.get('raw_sha256')==signature:return path
        except (OSError,ValueError):continue
    return None


def export_automatic_fingers(blend,raw,cancelled=lambda:False,progress=lambda *a:None):
    """Refine once per input, select geometrically valid candidates, report fallback."""
    if cancelled():raise KeyboardInterrupt
    from app.hand_refine_job import reestimate_hands
    folder=Path(raw).resolve().parent;crop=None;errors=[];attempts=0;state='unavailable'
    try:
        source=Path(json.loads((folder/'sam-request.json').read_text(encoding='utf-8'))['source'])
        model=ROOT/'models/hand_landmarker/hand_landmarker.task'
        signature={'raw_sha256':digest(raw),'source_sha256':digest(source),'model_sha256':digest(model),
                   'crop_solver_sha256':digest(ROOT/'app/hand_refine_job.py')}
        candidate=latest_hand_crop(folder)
        if candidate is not None:
            data=json.loads(candidate.read_text(encoding='utf-8'))
            if all(data.get(k)==v for k,v in signature.items()):crop=candidate;state='reused'
        if crop is None:
            for attempt in range(2):
                if cancelled():raise KeyboardInterrupt
                attempts=attempt+1
                try:
                    crop=reestimate_hands(folder,cancelled,progress,comparison=False);state='computed';break
                except (RuntimeError,OSError) as exc:
                    errors.append(str(exc))
                    if isinstance(exc,FileNotFoundError) or attempt:raise
    except Exception as exc:
        state='baseline_fallback';errors.append(str(exc));crop=None
    if cancelled():raise KeyboardInterrupt
    try:result=export_fingers(blend,raw,cancelled,**({} if crop is None else {'crop_report':crop}))
    except ValueError as exc:
        if crop is None:raise
        errors.append(str(exc));state='baseline_fallback';crop=None
        result=export_fingers(blend,raw,cancelled)
    selection=json.loads(result.with_name('report.json').read_text(encoding='utf-8'))
    result.with_name('automatic-hands.json').write_text(json.dumps({'status':'completed' if crop is not None else 'degraded',
        'refinement':state,'attempts':attempts,'crop_report':None if crop is None else str(crop),
        'selected_hand_frames':selection.get('selected_hand_frames'),'errors':errors,
        'grip_solver_applied':False},ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def export_fingers(blend,raw,cancelled=lambda:False,*,executable=None,crop_report=None):
    if cancelled():raise KeyboardInterrupt
    blend=Path(blend).resolve();raw=Path(raw).resolve()
    base_report=json.loads((blend.parent/'report.json').read_text(encoding='utf-8'))
    if base_report.get('status')!='completed' or base_report.get('hand_raw_sha256')!=digest(raw):raise ValueError('손목 회전 결과와 원본 SAM 데이터가 다릅니다.')
    inputs=[blend,blend.parent/'animation.json',blend.parent/'corrected-motion.json',raw,ROOT/'tools/animate_fingers.py',ROOT/'tools/animate_reference_rig.py',ROOT/'tools/finger_limits.py',ROOT/'tools/manny_leg_alignment.py']
    selection=None
    if crop_report is not None:
        crop_report=Path(crop_report).resolve()
        if not crop_report.is_relative_to(raw.parent):raise ValueError('다른 영상의 손 재추정 결과는 적용할 수 없습니다.')
        crop=json.loads(crop_report.read_text(encoding='utf-8'));corrected=json.loads((blend.parent/'corrected-motion.json').read_text(encoding='utf-8'))
        if crop.get('raw_sha256')!=digest(raw) or not corrected.get('source_sha256') or crop.get('source_sha256')!=corrected['source_sha256']:
            raise ValueError('손 재추정 후보의 원본 해시가 다릅니다.')
        from core.motion.refined_hands import select_crop_hands
        selection=select_crop_hands(json.loads(raw.read_text(encoding='utf-8')),crop)
        selection.update(crop_report=str(crop_report),crop_sha256=digest(crop_report))
        inputs.extend([crop_report,ROOT/'core/motion/refined_hands.py'])
    hashes={p:digest(p) for p in inputs}
    from app.artifact_cache import lookup,publish,identity
    binary=executable or find_blender()
    cache_signature={'revision':1,'inputs':{str(p):v for p,v in hashes.items()},'blender':identity(binary),'exporter_sha256':digest(Path(__file__)),
        'selection':None if selection is None else hashlib.sha256(json.dumps(selection,sort_keys=True,allow_nan=False).encode()).hexdigest()}
    cached=lookup(blend.parent.parent,'fingers',cache_signature,cancelled)
    if cached is not None:return cached
    out=blend.parent.parent/('animation-fingers-'+uuid.uuid4().hex[:10]);log=out.with_suffix('.log');start=time.monotonic()
    selection_path=out.with_suffix('.selection.json') if selection is not None else None
    if selection_path is not None:selection_path.write_text(json.dumps(selection,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    selection_hash=None if selection_path is None else digest(selection_path)
    args=[binary,'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'tools/animate_fingers.py'),'--',str(blend),str(raw),str(out)]
    if selection_path is not None:args.append(str(selection_path))
    with log.open('w',encoding='utf-8') as stream:
        process=subprocess.Popen(args,stdout=stream,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            while process.poll() is None:
                if cancelled():raise KeyboardInterrupt
                if time.monotonic()-start>1800:raise TimeoutError('손가락 애니메이션 생성 시간 초과')
                time.sleep(.1)
            if process.returncode:raise RuntimeError('손가락 생성 실패 · '+str(log))
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
    if cancelled():raise KeyboardInterrupt
    if any(digest(p)!=v for p,v in hashes.items()):raise ValueError('손가락 생성 중 입력이 변경되었습니다.')
    if selection_path is not None and digest(selection_path)!=selection_hash:raise ValueError('손가락 생성 중 선택한 손 후보가 변경되었습니다.')
    data=json.loads((out/'animation.json').read_text(encoding='utf-8'))
    if len(data['bone_names'])!=52 or not (out/'animation.blend').is_file():raise ValueError('손가락 리그 검증 실패')
    shutil.copyfile(blend.parent/'corrected-motion.json',out/'corrected-motion.json')
    if selection_path is not None:
        shutil.copyfile(selection_path,out/'hand-selection.json');selection_path.unlink()
    (out/'report.json').write_text(json.dumps({'status':'completed','corrections':True,'motion_sha256':base_report['motion_sha256'],'corrected_motion_sha256':digest(out/'corrected-motion.json'),'frames':len(data['frames']),'bones':52,'source_blend':str(blend),'selected_hand_frames':None if selection is None else selection['selected_hand_frames'],'input_sha256':{str(p):v for p,v in hashes.items()},'elapsed_seconds':time.monotonic()-start},ensure_ascii=False,indent=2),encoding='utf-8')
    publish(blend.parent.parent,'fingers',cache_signature,out/'animation.blend',['animation.blend','animation.json','corrected-motion.json','report.json']+(['hand-selection.json'] if selection is not None else []))
    return out/'animation.blend'
