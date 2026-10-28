"""Cancellable cache/export jobs for the fourth studio panel."""
import json,hashlib,uuid
from pathlib import Path
from app.gui_jobs import ROOT
from app.builtin_models import blender_job


def edit_source(preview):
    preview=Path(preview).resolve();folder=preview.parent
    suffix=preview.stem.removeprefix('model-preview')
    choices=[folder/('hand-stable'+suffix)/'animation.blend',folder/'hand-stable/animation.blend',folder/'animation.blend']
    for p in choices:
        if p.is_file():return p
    raise FileNotFoundError('이 미리보기의 원본 animation.blend가 없습니다.')


def prepare_scene(preview,cancelled=lambda:False):
    source=edit_source(preview);signature=hashlib.sha256(source.read_bytes()).hexdigest()
    revision=hashlib.sha256((ROOT/'tools/export_editable_scene.py').read_bytes()).hexdigest()
    out=source.parent/('.editor-cache-'+signature[:12]+revision[:8])
    if not (out/'scene.json').is_file() or not (out/'scene.npz').is_file():
        out.mkdir(exist_ok=True);blender_job('export_editable_scene.py',[source,out],out/'export.log',cancelled)
    info=json.loads((out/'scene.json').read_text(encoding='utf-8'))
    if info['source_sha256']!=signature or hashlib.sha256(source.read_bytes()).hexdigest()!=signature:raise ValueError('편집 준비 중 원본이 변경되었습니다.')
    return out


def export_edit(preview,cache,packet,cancelled=lambda:False,progress=lambda *args:None):
    from app.editable_animation import EditableAnimation
    from app.model_preview import describe,encode_model_frames,cleanup_model_frames
    item=describe(preview)
    if item is None:raise ValueError('모델 미리보기를 먼저 선택하세요.')
    editor=EditableAnimation(cache)
    source=Path(editor.info['source_blend'])
    if hashlib.sha256(source.read_bytes()).hexdigest()!=editor.info['source_sha256']:raise ValueError('원본 애니메이션이 변경되었습니다.')
    if cancelled():raise KeyboardInterrupt
    result_root=ROOT/'outputs'/Path(preview).resolve().relative_to((ROOT/'outputs').resolve()).parts[0]
    out=result_root/('edit-'+uuid.uuid4().hex[:10]);out.mkdir()
    project=out/'animation-edits.json';project.write_text(json.dumps(packet,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
    editor.load(project);progress(0,3)
    blender_job('apply_animation_edits.py',[cache,project,out],out/'edit.log',cancelled)
    progress(1,3)
    blender_job('render_model_preview.py',[out/'animation.blend',out/'frames','all'],out/'render.log',cancelled)
    progress(2,3)
    video=encode_model_frames(item.source or source,item.tracking or source,out/'frames',out/'model-preview.mp4',cancelled)
    metadata=json.loads(video.with_suffix('.json').read_text(encoding='utf-8'));metadata['tracking']=None if item.tracking is None else str(item.tracking)
    prior=json.loads(Path(preview).with_suffix('.json').read_text(encoding='utf-8'))
    for field in ('model_id','model_name'):
        if field in prior:metadata[field]=prior[field]
    metadata['source']=None if item.source is None else str(item.source);metadata['edited_animation']=str(out/'animation.blend')
    video.with_suffix('.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    cleanup_model_frames(out/'frames',video)
    progress(3,3)
    return video
