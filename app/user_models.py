"""Local custom-model registry; publish only fully prepared, validated rigs."""
import hashlib,json,uuid
from pathlib import Path
from app.gui_jobs import ROOT


def library():return ROOT/'assets/user_models'


def registered():
    root=library()
    if not root.is_dir():return {}
    rows={}
    for folder in root.glob('user_*'):
        try:
            if folder.is_symlink() or not folder.is_dir():continue
            row=json.loads((folder/'registry.json').read_text(encoding='utf-8'))
            if row.get('status')!='completed' or row.get('id')!=folder.name:continue
            if not (folder/'model.blend').is_file() or not (folder/'profile.json').is_file():continue
            rows[folder.name]={**row,'folder':folder}
        except (OSError,ValueError,TypeError):continue
    return rows


def selected():
    try:
        key=json.loads((library()/'selection.json').read_text(encoding='utf-8'))['id']
        if key=='unreal_manny' or key in registered():return key
    except (OSError,ValueError,KeyError,TypeError):pass
    return 'unreal_manny'


def select(key):
    if key!='unreal_manny' and key not in registered():raise ValueError('등록되지 않은 모델입니다.')
    root=library();root.mkdir(parents=True,exist_ok=True)
    temp=root/('.selection-'+uuid.uuid4().hex)
    temp.write_text(json.dumps({'id':key}),encoding='utf-8');temp.replace(root/'selection.json')


def import_model(source,cancelled=lambda:False,progress=lambda *args:None):
    from app.builtin_models import blender_job
    source=Path(source).resolve()
    if not source.is_file() or source.suffix.lower() not in ('.fbx','.glb','.gltf','.obj','.blend'):
        raise ValueError('FBX · GLB · GLTF · OBJ · BLEND 파일을 선택하세요.')
    if cancelled():raise KeyboardInterrupt
    signature=hashlib.sha256(source.read_bytes()).hexdigest()
    root=library();root.mkdir(parents=True,exist_ok=True)
    key='user_'+uuid.uuid4().hex[:12];staging=root/('.import-'+key);staging.mkdir()
    progress(0,3)
    blender_job('import_user_model.py',[source,key,staging],staging/'inspection.log',cancelled)
    plan=json.loads((staging/'inspection.json').read_text(encoding='utf-8'));ready=staging/'ready'
    progress(1,3)
    if plan['has_armature']:
        ready.mkdir()
        blender_job('prepare_builtin_model.py',[staging/'input.fbx',key,ready],staging/'prepare.log',cancelled)
        profile=json.loads((ready/'profile.json').read_text(encoding='utf-8'))
        for bone,row in profile['mapping'].items():
            if row['source'].startswith(('thumb_','index_','middle_','ring_','pinky_')):row['mode']='finger_local'
        (ready/'profile.json').write_text(json.dumps(profile,indent=2),encoding='utf-8')
    else:
        blender_job('rig_static_humanoid.py',[staging/'input.fbx',staging/'landmarks.json',ready],staging/'rig.log',cancelled)
    profile=json.loads((ready/'profile.json').read_text(encoding='utf-8'))
    if hashlib.sha256((ready/'model.blend').read_bytes()).hexdigest()!=profile['model_sha256']:
        raise ValueError('모델 검증 실패')
    if cancelled():raise KeyboardInterrupt
    if hashlib.sha256(source.read_bytes()).hexdigest()!=signature:raise ValueError('원본 모델 파일이 변경되었습니다.')
    row={'id':key,'name':source.stem,'status':'completed','source_sha256':signature,
        'auto_rigged':not plan['has_armature'],'estimated':plan['estimated'],
        'bones':profile.get('bones',len(profile['mapping'])+1+len(profile.get('deform_helpers',[]))),
        'deform_helpers':len(profile.get('deform_helpers',[])),
        'fingers':sum(x['source'].startswith(('thumb_','index_','middle_','ring_','pinky_')) for x in profile['mapping'].values())}
    (ready/'registry.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
    progress(2,3)
    ready.rename(root/key);select(key);progress(3,3)
    return key


def apply_custom(folder,key,cancelled=lambda:False,progress=lambda *args:None):
    from app.builtin_models import blender_job,finalize_model,attach_quality
    from app.motion_job import ensure_motion
    from app.animation_job import export_animation
    from app.finger_job import export_automatic_fingers
    from app.model_preview import encode_model_frames,cleanup_model_frames
    row=registered().get(key)
    if row is None:raise ValueError('추가한 모델을 찾을 수 없습니다.')
    folder=Path(folder).resolve()
    if not (folder/'sam3d.json').is_file():raise ValueError('완료된 SAM3D 결과를 선택하세요.')
    source=Path(json.loads((folder/'sam-request.json').read_text(encoding='utf-8'))['source'])
    auto=folder/'automatic-report.json';post=json.loads(auto.read_text(encoding='utf-8')) if auto.is_file() else {}
    if cancelled():raise KeyboardInterrupt
    progress(0,4)
    motion,_=ensure_motion(folder,source,post,cancelled)
    animation=export_automatic_fingers(export_animation(motion,cancelled),folder/'sam3d.json',cancelled,progress)
    out=folder/('model-'+key+'-'+uuid.uuid4().hex[:10]);out.mkdir()
    progress(1,4)
    blender_job('retarget_builtin_model.py',[row['folder']/'model.blend',animation,row['folder']/'profile.json',out],out/'retarget.log',cancelled)
    filtered=out/'hand-filtered'
    blender_job('stabilize_manny_hands.py',[out/'animation.blend',filtered],out/'hand-stability.log',cancelled)
    stable=finalize_model(filtered/'animation.blend',animation,row['folder']/'profile.json',out,bool(row.get('auto_rigged')),cancelled)
    progress(2,4)
    blender_job('export_model_animation.py',[stable/'animation.blend',out,'Model_Animation'],out/'delivery.log',cancelled)
    delivery=json.loads((out/'delivery.json').read_text(encoding='utf-8'))
    delivery.update(model_id=key,model_name=row['name'])
    (out/'delivery.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2),encoding='utf-8')
    blender_job('render_model_preview.py',[stable/'animation.blend',out/'frames','all'],out/'render.log',cancelled)
    progress(3,4)
    result=encode_model_frames(source,folder/'overlay.mp4',out/'frames',out/'model-preview.mp4',cancelled)
    attach_quality(result,stable,animation)
    metadata=json.loads(result.with_suffix('.json').read_text(encoding='utf-8'))
    metadata.update(model_id=key,model_name=row['name'])
    result.with_suffix('.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    from app.animation_edit_job import prepare_scene
    prepare_scene(result,cancelled)
    cleanup_model_frames(out/'frames',result)
    progress(4,4)
    return result
