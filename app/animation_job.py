"""Optional local Blender animation export; no GPU/model work."""
import json,os,shutil,subprocess,time,uuid
from pathlib import Path
from app.knee_job import digest
from core.motion.correction import prepare_motion

ROOT=Path(__file__).resolve().parents[1]


def find_blender():
    candidates=[shutil.which('blender')]
    base=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Blender Foundation'
    if base.is_dir():candidates.extend(str(p/'blender.exe') for p in sorted(base.glob('Blender *'),reverse=True))
    for item in candidates:
        if item and Path(item).is_file():return str(Path(item).resolve())
    raise FileNotFoundError('Blender를 설치하거나 PATH에 blender.exe를 추가해 주세요.')


def ground_evidence(motion,data,cancelled=lambda:False):
    """Use only the exact inference packet that produced this immutable M3 motion."""
    import numpy as np
    signature=data.get('input_sha256')
    if not signature:return None,None
    folder=Path(motion).parent.parent
    patterns={'checked_reconnection':'reconnect_*/reconnected-joints.json','part_estimates':'parts_*/part-joints.json',
              'selected_candidates':'candidates_*/selected-joints.json','raw_sam3d':'sam3d.json'}
    pattern=patterns.get(data.get('source_kind'))
    if pattern is None:return None,None
    for path in folder.glob(pattern):
        if cancelled():raise KeyboardInterrupt
        if path.is_symlink() or path.parent.is_symlink() or not path.resolve().is_relative_to(folder.resolve()):continue
        if digest(path)!=signature:continue
        packet=json.loads(path.read_text(encoding='utf-8'));rows=packet['frames']
        if len(rows)!=len(data['frames']) or any(row['frame_index']!=i for i,row in enumerate(rows)):
            raise ValueError('Ground evidence timeline differs.')
        pixels=[]
        for i,row in enumerate(rows):
            if i%128==0 and cancelled():raise KeyboardInterrupt
            points=(row.get('outputs') or {}).get('pred_keypoints_2d') if data['source_kind']=='raw_sam3d' else row.get('image_joints')
            if points is None:pixels.append([[float('nan')]*2]*5);continue
            p=np.asarray(points,float)
            if p.shape!=(70,2) or np.isinf(p).any():raise ValueError('Invalid ground evidence coordinates.')
            pixels.append(np.stack((p[13],p[14],p[[15,16]].mean(axis=0),p[[18,19]].mean(axis=0),p[[9,10]].mean(axis=0))).tolist())
        return pixels,path
    return None,None


def export_animation(motion,cancelled=lambda:False,*,executable=None,corrections=True):
    motion=Path(motion).resolve()
    if cancelled():raise KeyboardInterrupt
    if motion.name!='motion.json' or motion.parent.name!='motion':raise ValueError('표준 스켈레톤 결과를 먼저 변환해 주세요.')
    before=digest(motion)
    script=ROOT/'tools/animate_reference_rig.py';rig=ROOT/'assets/skeletons/MotionHumanoid22.blend'
    processor=ROOT/'core/motion/correction.py'
    hinge_solver=ROOT/'tools/manny_leg_alignment.py'
    hand_solver=ROOT/'core/motion/hand_orientation.py'
    signature={'motion_sha256':before,'solver_sha256':digest(script),'rig_sha256':digest(rig),
               'corrections':corrections,'correction_sha256':digest(processor),'hinge_solver_sha256':digest(hinge_solver),
               'hand_solver_sha256':digest(hand_solver)}
    root_dependencies={ROOT/'core/motion/root_motion.py':'root_solver_sha256',ROOT/'app/root_motion_job.py':'root_camera_job_sha256'}
    if corrections:signature.update({name:digest(path) for path,name in root_dependencies.items()})
    from app.artifact_cache import lookup,publish,identity
    binary=executable or find_blender()
    cache_signature={'revision':1,'settings':signature.copy(),'blender':identity(binary),'exporter_sha256':digest(Path(__file__)),
        'motion_code':{p.name:digest(p) for p in (ROOT/'core/motion').glob('*.py')}}
    source_data=json.loads(motion.read_text(encoding='utf-8'))
    if corrections:
        raw_path=motion.parent.parent/'sam3d.json'
        if source_data.get('raw_sha256'):
            actual=digest(raw_path)
            if actual!=source_data['raw_sha256']:raise ValueError('손 회전 근거의 원본 해시가 다릅니다.')
            cache_signature['raw_sha256']=actual
        request=motion.parent.parent/'sam-request.json'
        if request.is_file():
            source=Path(json.loads(request.read_text(encoding='utf-8'))['source'])
            cache_signature['source_sha256']=digest(source)
            if source_data.get('source_sha256') and cache_signature['source_sha256']!=source_data['source_sha256']:raise ValueError('원본 영상의 해시가 다릅니다.')
        evidence,evidence_path=ground_evidence(motion,source_data,cancelled)
        cache_signature['ground_evidence_sha256']=None if evidence_path is None else digest(evidence_path)
    cached=lookup(motion.parent,'body',cache_signature,cancelled)
    if cached is not None:return cached
    out=motion.parent/('animation-'+uuid.uuid4().hex[:12])
    log=motion.parent/(out.name+'.log')
    input_path=motion
    if not corrections:evidence_path=None
    if corrections:
        signature['ground_evidence_sha256']=source_data['input_sha256'] if evidence_path is not None else None
        from app.root_motion_job import root_observations
        observations,root_info=root_observations(motion,source_data,evidence,cancelled)
        signature['root_motion_analysis']=root_info
        data=prepare_motion(source_data,cancelled,ground_evidence=evidence,root_observations=observations)
        raw_path=motion.parent.parent/'sam3d.json'
        if source_data.get('raw_sha256'):
            if digest(raw_path)!=source_data['raw_sha256']:raise ValueError('손 회전 근거의 원본 해시가 다릅니다.')
            from core.motion.hand_orientation import palm_observations
            raw=json.loads(raw_path.read_text(encoding='utf-8'))
            if len(raw['frames'])!=len(data['frames']) or any(r['frame_index']!=i for i,r in enumerate(raw['frames'])):
                raise ValueError('손 회전 근거의 프레임이 다릅니다.')
            data['hand_orientation_observations']=palm_observations(raw)
            signature['hand_raw_sha256']=source_data['raw_sha256']
        input_path=motion.parent/(out.name+'.input.json')
        input_path.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    if cancelled():raise KeyboardInterrupt
    args=[binary,'--background','--factory-startup','--python-exit-code','1','--python',str(script),'--',str(input_path),str(out)]
    started=time.monotonic()
    with log.open('w',encoding='utf-8') as stream:
        process=subprocess.Popen(args,stdout=stream,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            while process.poll() is None:
                if cancelled():raise KeyboardInterrupt
                if time.monotonic()-started>1800:raise TimeoutError('Blender 애니메이션 생성 시간 초과')
                time.sleep(.1)
            if process.returncode:raise RuntimeError(f'Blender 변환 실패 · 로그: {log.name}')
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
    if cancelled():raise KeyboardInterrupt
    if digest(motion)!=before or digest(script)!=signature['solver_sha256'] or digest(rig)!=signature['rig_sha256'] or digest(processor)!=signature['correction_sha256'] or digest(hinge_solver)!=signature['hinge_solver_sha256'] or digest(hand_solver)!=signature['hand_solver_sha256']:
        raise ValueError('애니메이션 생성 중 입력이 변경되었습니다.')
    if evidence_path is not None and digest(evidence_path)!=signature['ground_evidence_sha256']:
        raise ValueError('애니메이션 생성 중 접지 근거가 변경되었습니다.')
    if signature.get('hand_raw_sha256') and digest(raw_path)!=signature['hand_raw_sha256']:
        raise ValueError('애니메이션 생성 중 손 회전 근거가 변경되었습니다.')
    if corrections and any(digest(path)!=signature[name] for path,name in root_dependencies.items()):
        raise ValueError('애니메이션 생성 중 이동 보정 코드가 변경되었습니다.')
    if corrections and signature['root_motion_analysis']['status']=='estimated' and digest(motion.parent.parent/'sam3d.json')!=source_data['raw_sha256']:
        raise ValueError('애니메이션 생성 중 이동 근거가 변경되었습니다.')
    data=json.loads((out/'animation.json').read_text(encoding='utf-8'))
    if not (out/'animation.blend').is_file() or data['max_solved_head_error_m']>1e-4:raise ValueError('Blender 결과 검증 실패')
    if corrections:
        shutil.copyfile(input_path,out/'corrected-motion.json')
        input_path.unlink()
    (out/'report.json').write_text(json.dumps({'status':'completed',**signature,'frames':len(data['frames']),
        'corrected_motion_sha256':digest(out/'corrected-motion.json') if corrections else None,
        'frames_with_pose':data['frames_with_pose'],'elapsed_seconds':time.monotonic()-started},indent=2),encoding='utf-8')
    publish(motion.parent,'body',cache_signature,out/'animation.blend',
        ['animation.blend','animation.json','report.json']+(['corrected-motion.json'] if corrections else []))
    return out/'animation.blend'


def latest_corrected_motion(motion):
    motion=Path(motion).resolve();motion_hash=None
    for folder in sorted(motion.parent.glob('animation-*'),key=lambda p:p.stat().st_mtime_ns,reverse=True):
        if not folder.is_dir() or folder.is_symlink():continue
        try:
            report=json.loads((folder/'report.json').read_text(encoding='utf-8'));path=folder/'corrected-motion.json'
            if path.is_symlink() or not report.get('corrections') or report.get('status')!='completed':continue
            if motion_hash is None:motion_hash=digest(motion)
            if report.get('motion_sha256')==motion_hash and report.get('corrected_motion_sha256')==digest(path):return path
        except (OSError,ValueError):continue
    return motion
