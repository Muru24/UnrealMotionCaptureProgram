import json
from pathlib import Path
from types import SimpleNamespace
import cv2
import numpy as np
import pytest
import app.builtin_models as builtin


def test_only_manny_is_registered_and_missing_model_cannot_apply(tmp_path,monkeypatch):
    monkeypatch.setattr(builtin,'ROOT',tmp_path)
    assert list(builtin.MODELS)==['unreal_manny']
    with pytest.raises(ValueError,match='모델 파일'):builtin.apply_model(tmp_path,'unreal_manny')
    with pytest.raises(ValueError):builtin.model_folder('unity_starter')


def test_automatic_preview_preserves_failure_and_propagates_cancel(monkeypatch,tmp_path):
    def fail(*args):raise RuntimeError('render failed')
    monkeypatch.setattr(builtin,'apply_model',fail)
    assert builtin.automatic_preview(tmp_path)=={'model_preview_error':'render failed'}
    with pytest.raises(KeyboardInterrupt):builtin.automatic_preview(tmp_path,lambda:True)
    def cancel(*args):raise KeyboardInterrupt
    monkeypatch.setattr(builtin,'apply_model',cancel)
    with pytest.raises(KeyboardInterrupt):builtin.automatic_preview(tmp_path)


def test_extraction_automatically_updates_manny_preview(tmp_path,monkeypatch):
    import app.user_models as users
    monkeypatch.setattr(users,'selected',lambda:'unreal_manny')
    from tkinterdnd2 import TkinterDnD
    import app.gui as gui
    import app.automatic_postprocess as post
    import app.motion_job as motion
    source=tmp_path/'source.mp4';folder=tmp_path/'result';folder.mkdir()
    def video(path,value):
        writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),10,(64,64))
        assert writer.isOpened()
        for _ in range(5):writer.write(np.full((64,64,3),value,np.uint8))
        writer.release()
    video(source,40);video(folder/'overlay.mp4',80)
    (folder/'sam-request.json').write_text(json.dumps({'source':str(source)}))
    (folder/'sam3d.json').write_text('{}')
    preview=folder/'model-preview.mp4'
    calls=[]
    def apply(output,key,cancelled,progress):
        assert calls==['tracking','post','bones']
        assert key=='unreal_manny' and output==folder and not cancelled()
        calls.append('manny');video(preview,160)
        preview.with_suffix('.json').write_text(json.dumps({'schema':'model_preview_v1','status':'completed','source':str(source),'tracking':str(folder/'overlay.mp4')}))
        progress(3,3)
        return preview
    def run(*args):calls.append('tracking');return {'frames_processed':5,'frames_with_target':5}
    def process(*args,**kwargs):calls.append('post');return {}
    def bones(*args):calls.append('bones');return {}
    monkeypatch.setattr(gui,'run_job',run)
    monkeypatch.setattr(gui,'new_output',lambda *args:folder)
    monkeypatch.setattr(post,'process_sam_result',process)
    monkeypatch.setattr(motion,'add_motion_result',bones)
    monkeypatch.setattr(builtin,'apply_model',apply)
    monkeypatch.setattr(builtin,'installed',lambda key:True)
    root=TkinterDnD.Tk();root.withdraw();app=gui.PrototypeApp(root)
    try:
        assert app.studio.selected_builtin()=='unreal_manny'
        assert not hasattr(app.studio,'builtin_box')
        app.source=source
        monkeypatch.setattr(app,'settings',lambda:SimpleNamespace(stage='sam3d'))
        app.studio.show_stage(2)
        def launch(kind,operation):
            app.busy=True;app.set_busy(True)
            result=operation();app.events.put((kind,result));app.events.put(('finished',None))
        monkeypatch.setattr(app,'launch_worker',launch)
        app.start();app.poll()
        assert calls==['tracking','post','bones','manny']
        assert not app.busy and app.result_dir==folder
        assert app.saved_preview_path==preview and app.requested_preview_path==preview
        assert app.preview_path==source and app.model_capture is not None
        assert app.model_capture.path==preview
        assert '자동 저장됨' in app.status_text.get()
    finally:app.busy=False;app.stop_video();root.destroy()


def test_manny_apply_uses_engine_poses_instead_of_fk(tmp_path,monkeypatch):
    import app.motion_job as motion
    import app.animation_job as animation
    import app.finger_job as fingers
    import app.model_preview as preview
    (tmp_path/'sam3d.json').write_text('{}')
    (tmp_path/'sam-request.json').write_text(json.dumps({'source':str(tmp_path/'source.mp4')}))
    monkeypatch.setattr(builtin,'installed',lambda key:True)
    monkeypatch.setattr(motion,'ensure_motion',lambda *args:(tmp_path/'motion.json','reused'))
    monkeypatch.setattr(animation,'export_animation',lambda *args:tmp_path/'body.blend')
    monkeypatch.setattr(fingers,'export_automatic_fingers',lambda *args:tmp_path/'animation.blend')
    import app.animation_edit_job as edit_job
    calls=[]
    monkeypatch.setattr(edit_job,'prepare_scene',lambda path,cancelled:calls.append('prepare_editor'))
    monkeypatch.setattr(builtin,'unreal_preview',lambda blend,out,cancelled:calls.append('unreal_ik'))
    monkeypatch.setattr(builtin,'blender_job',lambda script,*args:calls.append(script))
    monkeypatch.setattr(builtin,'finalize_model',lambda source,animation,profile,out,*a:calls.append('model_quality') or out/'hand-stable')
    monkeypatch.setattr(builtin,'attach_quality',lambda *a:None)
    monkeypatch.setattr(preview,'encode_model_frames',lambda source,tracking,frames,output,cancelled:output)
    result=builtin.apply_model(tmp_path,'unreal_manny')
    assert result.name=='model-preview.mp4'
    assert calls==['unreal_ik','bake_unreal_manny.py','stabilize_manny_hands.py','model_quality','export_model_animation.py','render_model_preview.py','prepare_editor']
