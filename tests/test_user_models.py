import hashlib,json
from pathlib import Path
import pytest
import app.user_models as users
import app.builtin_models as builtin


def publish(root,key='user_test',name='Test'):
    folder=root/'assets/user_models'/key;folder.mkdir(parents=True)
    (folder/'model.blend').write_bytes(b'model')
    (folder/'profile.json').write_text('{}')
    (folder/'registry.json').write_text(json.dumps(dict(id=key,name=name,status='completed',
        auto_rigged=True,estimated=True,bones=52,fingers=30)))
    return folder


def test_registry_selection_survives_restart_and_ignores_incomplete(tmp_path,monkeypatch):
    monkeypatch.setattr(users,'ROOT',tmp_path)
    publish(tmp_path)
    partial=users.library()/'user_partial';partial.mkdir()
    (partial/'registry.json').write_text('{"status":"completed","id":"user_partial"}')
    assert list(users.registered())==['user_test']
    users.select('user_test');assert users.selected()=='user_test'
    with pytest.raises(ValueError):users.select('../elsewhere')
    assert users.selected()=='user_test'
    users.select('unreal_manny');assert users.selected()=='unreal_manny'


@pytest.mark.parametrize('existing',[False,True])
def test_import_dispatches_by_bone_presence_and_publishes_only_ready(tmp_path,monkeypatch,existing):
    monkeypatch.setattr(users,'ROOT',tmp_path)
    source=tmp_path/'Hero.fbx';source.write_bytes(b'original');calls=[]
    def blender(script,args,log,cancelled):
        calls.append(script)
        assert users.registered()=={}
        if script=='import_user_model.py':
            staging=Path(args[-1]);(staging/'inspection.json').write_text(json.dumps(dict(has_armature=existing,estimated=not existing)))
            (staging/'input.fbx').write_bytes(b'converted')
            (staging/'landmarks.json').write_text('{}')
        else:
            ready=Path(args[-1]);ready.mkdir(exist_ok=True)
            (ready/'model.blend').write_bytes(b'rigged')
            (ready/'profile.json').write_text(json.dumps(dict(model_sha256=hashlib.sha256(b'rigged').hexdigest(),
                mapping={'hand_l':{'source':'hand_l','mode':'direction'},'index_01_l':{'source':'index_01_l','mode':'direction'}})))
    monkeypatch.setattr(builtin,'blender_job',blender)
    key=users.import_model(source)
    assert calls==['import_user_model.py','prepare_builtin_model.py' if existing else 'rig_static_humanoid.py']
    assert key==users.selected() and key in users.registered()
    assert source.read_bytes()==b'original'
    assert users.registered()[key]['auto_rigged']==(not existing)
    if existing:
        profile=json.loads((users.registered()[key]['folder']/'profile.json').read_text())
        assert profile['mapping']['index_01_l']['mode']=='finger_local'


def test_failed_or_cancelled_import_does_not_publish_or_change_selection(tmp_path,monkeypatch):
    monkeypatch.setattr(users,'ROOT',tmp_path);publish(tmp_path);users.select('user_test')
    source=tmp_path/'Bad.fbx';source.write_bytes(b'keep')
    def fail(*args):raise RuntimeError('invalid rig')
    monkeypatch.setattr(builtin,'blender_job',fail)
    with pytest.raises(RuntimeError):users.import_model(source)
    with pytest.raises(KeyboardInterrupt):users.import_model(source,lambda:True)
    assert list(users.registered())==['user_test'] and users.selected()=='user_test'
    assert source.read_bytes()==b'keep'


def test_extraction_uses_selected_custom_model(monkeypatch,tmp_path):
    monkeypatch.setattr(users,'selected',lambda:'user_test')
    calls=[]
    (tmp_path/'preview.json').write_text('{}')
    monkeypatch.setattr(builtin,'apply_model',lambda folder,key,*args:calls.append(key) or tmp_path/'preview.mp4')
    assert builtin.automatic_preview(tmp_path)['model_preview'].endswith('preview.mp4')
    assert calls==['user_test']


@pytest.mark.parametrize('auto_rigged',[False,True])
def test_custom_delivery_and_editor_use_repaired_auto_rig(monkeypatch,tmp_path,auto_rigged):
    import app.motion_job as motion
    import app.animation_job as animation
    import app.finger_job as fingers
    import app.model_preview as preview
    import app.animation_edit_job as editor
    monkeypatch.setattr(users,'ROOT',tmp_path)
    model=publish(tmp_path)
    row=json.loads((model/'registry.json').read_text());row['auto_rigged']=auto_rigged
    (model/'registry.json').write_text(json.dumps(row))
    folder=tmp_path/'clip';folder.mkdir();(folder/'sam3d.json').write_text('{}')
    (folder/'sam-request.json').write_text(json.dumps({'source':str(tmp_path/'source.mp4')}))
    monkeypatch.setattr(motion,'ensure_motion',lambda *a:(folder/'motion.json',{}))
    monkeypatch.setattr(animation,'export_animation',lambda *a:folder/'animation.blend')
    monkeypatch.setattr(fingers,'export_automatic_fingers',lambda *a:folder/'animation.blend')
    (folder/'automatic-hands.json').write_text('{"status":"completed"}')
    calls=[]
    def job(script,args,*unused):
        calls.append((script,args))
        if script=='finalize_model_motion.py':
            candidate=Path(args[3]);candidate.mkdir();(candidate/'animation.blend').write_bytes(b'checked')
            (candidate/'model-quality.json').write_text('{"status":"completed","warnings":[]}')
        if script=='export_model_animation.py':
            (Path(args[1])/'delivery.json').write_text('{"status":"completed"}')
    monkeypatch.setattr(builtin,'blender_job',job)
    def encode(source,tracking,frames,out,*unused):
        out.with_suffix('.json').write_text('{}');return out
    monkeypatch.setattr(preview,'encode_model_frames',encode)
    prepared=[];monkeypatch.setattr(editor,'prepare_scene',lambda p,*a:prepared.append(p))
    result=users.apply_custom(folder,'user_test')
    scripts=[s for s,_ in calls]
    assert 'finalize_model_motion.py' in scripts
    export=next(args for script,args in calls if script=='export_model_animation.py')
    render=next(args for script,args in calls if script=='render_model_preview.py')
    assert export[0]==render[0]==result.parent/'hand-stable/animation.blend'
    repair=next(args for script,args in calls if script=='finalize_model_motion.py')
    assert repair[0]==result.parent/'hand-filtered/animation.blend'
    assert repair[4]==('1' if auto_rigged else '0')
    assert scripts.index('finalize_model_motion.py')<scripts.index('export_model_animation.py')
    assert prepared==[result]
