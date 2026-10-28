"""Local built-in model registrations and cancellable Blender preview jobs."""
import json,subprocess,time,uuid,logging,os,shutil
from pathlib import Path
from app.gui_jobs import ROOT
from app.animation_job import find_blender

MODELS={
    'unreal_manny':{'name':'Unreal · Manny','source':'Epic UE5.8 Third Person template'},
}


def model_folder(key):
    if key not in MODELS:raise ValueError('Unknown built-in model')
    return ROOT/'assets/builtin_models'/key


def installed(key):
    return (model_folder(key)/'model.blend').is_file() and (model_folder(key)/'profile.json').is_file()


def finalize_model(source,animation,profile,out,auto_rigged,cancelled=lambda:False):
    """Retry only model finalization; publish the editor source after checks pass."""
    errors=[];out=Path(out)
    for attempt,gain in enumerate((1.,.5),1):
        if cancelled():raise KeyboardInterrupt
        candidate=out/f'model-check-{attempt}'
        try:
            blender_job('finalize_model_motion.py',[source,Path(animation).with_name('corrected-motion.json'),profile,
                candidate,'1' if auto_rigged else '0',str(gain)],out/f'model-check-{attempt}.log',cancelled)
            quality=json.loads((candidate/'model-quality.json').read_text(encoding='utf-8'))
            if quality.get('status')!='completed':raise ValueError('모델 자동 검수 실패')
            break
        except Exception as exc:
            errors.append(str(exc))
            if attempt==2:raise RuntimeError('모델 검수·재시도 실패: '+' / '.join(errors)) from exc
    if cancelled():raise KeyboardInterrupt
    stable=out/'hand-stable';stable.mkdir(exist_ok=False)
    for name in ('animation.blend','model-quality.json','leg-repair.json'):
        if (candidate/name).is_file():shutil.copyfile(candidate/name,stable/name)
    quality.update(attempts=attempt,previous_errors=errors)
    (stable/'model-quality.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2),encoding='utf-8')
    return stable


def blender_job(script,args,log,cancelled=lambda:False,timeout=1800):
    if cancelled():raise KeyboardInterrupt
    with Path(log).open('w',encoding='utf-8') as stream:
        process=subprocess.Popen([find_blender(),'--background','--factory-startup','--python-exit-code','1',
            '--python',str(ROOT/'tools'/script),'--',*map(str,args)],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        start=time.monotonic()
        try:
            while process.poll() is None:
                if cancelled():raise KeyboardInterrupt
                if time.monotonic()-start>timeout:raise TimeoutError('모델 처리 제한시간 초과')
                time.sleep(.1)
            if process.returncode:raise RuntimeError('모델 처리 실패 · 로그: '+str(log))
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


def install_model(key,source,cancelled=lambda:False):
    if cancelled():raise KeyboardInterrupt
    folder=model_folder(key);source=Path(source).resolve()
    if installed(key):raise ValueError('이미 설치된 기본 모델입니다.')
    folder.mkdir(parents=True,exist_ok=True)
    if source.suffix.lower()!='.fbx':raise ValueError('FBX 파일을 선택해 주세요.')
    fbx=source
    blender_job('prepare_builtin_model.py',[fbx,key,folder],folder/'install.log',cancelled)
    if not installed(key):raise ValueError('기본 모델 설치가 완료되지 않았습니다.')
    return folder


def apply_model(folder,key,cancelled=lambda:False,progress=lambda *args:None):
    if cancelled():raise KeyboardInterrupt
    if key!='unreal_manny':
        from app.user_models import apply_custom
        return apply_custom(folder,key,cancelled,progress)
    if not installed(key):raise ValueError('기본 모델 파일을 먼저 연결해 주세요.')
    folder=Path(folder).resolve()
    if not (folder/'sam3d.json').is_file():raise ValueError('완료된 SAM3D 추출 결과를 선택해 주세요.')
    from app.motion_job import ensure_motion
    from app.animation_job import export_animation
    source=Path(json.loads((folder/'sam-request.json').read_text(encoding='utf-8'))['source'])
    auto=folder/'automatic-report.json';post=json.loads(auto.read_text(encoding='utf-8')) if auto.is_file() else {}
    progress(0,3)
    motion,_=ensure_motion(folder,source,post,cancelled)
    blend=export_animation(motion,cancelled)
    from app.finger_job import export_automatic_fingers
    blend=export_automatic_fingers(blend,folder/'sam3d.json',cancelled,progress)
    out=folder/(f'model-{key}-'+uuid.uuid4().hex[:10]);out.mkdir()
    progress(1,3)
    unreal_preview(blend,out,cancelled)
    blender_job('bake_unreal_manny.py',[model_folder(key)/'model.blend',out/'unreal-poses.json',out],out/'bake.log',cancelled)
    filtered=out/'hand-filtered'
    blender_job('stabilize_manny_hands.py',[out/'animation.blend',filtered],out/'hand-stability.log',cancelled)
    stable=finalize_model(filtered/'animation.blend',blend,model_folder(key)/'profile.json',out,False,cancelled)
    blender_job('export_model_animation.py',[stable/'animation.blend',out],out/'delivery.log',cancelled)
    blender_job('render_model_preview.py',[stable/'animation.blend',out/'frames','all'],out/'render.log',cancelled)
    progress(2,3)
    from app.model_preview import encode_model_frames,cleanup_model_frames
    result=encode_model_frames(source,folder/'overlay.mp4',out/'frames',out/'model-preview.mp4',cancelled)
    attach_quality(result,stable,blend)
    from app.animation_edit_job import prepare_scene
    try:prepare_scene(result,cancelled)
    except Exception:logging.exception('Editor cache preparation failed; it will retry when opened')
    cleanup_model_frames(out/'frames',result)
    progress(3,3)
    return result


def attach_quality(preview,stable,animation):
    quality=json.loads((Path(stable)/'model-quality.json').read_text(encoding='utf-8'))
    hands=json.loads(Path(animation).with_name('automatic-hands.json').read_text(encoding='utf-8'))
    warnings=list(quality.get('warnings',[]))
    if hands.get('status')!='completed':warnings.append('손 재추정 실패 · 원본 손 추정 사용')
    report=Path(preview).parent.parent/'automatic-report.json'
    if report.is_file():
        post=json.loads(report.read_text(encoding='utf-8'))
        if post.get('status')=='partial':warnings.append('추적 보정 일부 실패 · 결과 확인 필요')
    path=Path(preview).with_suffix('.json');meta=json.loads(path.read_text(encoding='utf-8'))
    meta.update(model_quality_warnings=warnings,automatic_hand_refinement=hands,
                automatic_model_quality=quality,weapon_grip_applied=False)
    path.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')


def unreal_preview(blend,out,cancelled=lambda:False):
    from app.engine_export_job import export_engine_fbx
    engine=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
    project=ROOT/'UnrealProjects/MotionCheckUE58/MotionCheckUE58.uproject'
    if not engine.is_file() or not project.is_file():raise FileNotFoundError('Manny 미리보기에는 로컬 Unreal 5.8 프로젝트가 필요합니다.')
    exported=export_engine_fbx(blend,cancelled)
    animation=json.loads(blend.with_name('animation.json').read_text(encoding='utf-8'))
    request=out/'unreal-request.json';token='Run_'+uuid.uuid4().hex
    request.write_text(json.dumps({'fbx':str(exported/'Motion_Unreal.fbx'),
        'destination':'/Game/AutomaticManny/'+token+'/Source','target':'/Game/AutomaticManny/'+token+'/Target',
        'expected':json.loads((exported/'export.json').read_text(encoding='utf-8')),
        'report':str(out/'import-report.json'),'out':str(out),
        'preview_frames':len(animation['frames']),'preview_fps':animation['fps']}),encoding='utf-8')
    args=[str(engine),str(project),'-unattended','-nop4','-nosplash','-RenderOffscreen','-AllowCommandletRendering',
          '-run=pythonscript',f'-script={ROOT/"tools/unreal_builtin_preview.py"}',f'-MotionRequest="{request}"',
          '-stdout','-FullStdOutLogOutput']
    if cancelled():raise KeyboardInterrupt
    with (out/'unreal.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen(args,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        start=time.monotonic()
        try:
            while process.poll() is None:
                if cancelled():raise KeyboardInterrupt
                if time.monotonic()-start>1800:raise TimeoutError('Unreal Manny 처리 시간 초과')
                time.sleep(.1)
            status=out/'engine-status.json'
            if process.returncode or not status.is_file() or json.loads(status.read_text(encoding='utf-8')).get('status')!='completed':
                raise RuntimeError('Unreal Manny 처리 실패 · 로그: '+str(out/'unreal.log'))
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


def automatic_preview(folder,cancelled=lambda:False,progress=lambda *args:None):
    """Keep successful tracking/bones usable when the optional render fails."""
    if cancelled():raise KeyboardInterrupt
    try:
        from app.user_models import selected
        preview=apply_model(folder,selected(),cancelled,progress)
        meta=json.loads(Path(preview).with_suffix('.json').read_text(encoding='utf-8'))
        return {'model_preview':str(preview),'model_quality_warnings':meta.get('model_quality_warnings',[])}
    except Exception as exc:
        logging.exception('Automatic Manny preview failed')
        return {'model_preview_error':str(exc)}
