import json,time
from pathlib import Path
import numpy as np
import cv2


def test_selection_loads_results_and_editor_without_extra_buttons(tmp_path,monkeypatch):
    import app.user_models as users
    monkeypatch.setattr(users,'selected',lambda:'unreal_manny')
    from tkinterdnd2 import TkinterDnD
    from app.gui import PrototypeApp
    import app.animation_edit_job as edit_job
    import app.builtin_models as builtin
    monkeypatch.setattr(builtin,'installed',lambda key:True)
    folder=tmp_path/'result';folder.mkdir();cache=tmp_path/'cache';cache.mkdir()
    source=tmp_path/'source.mp4';preview=folder/'model-preview.mp4'
    for path in (source,preview):
        writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),10,(64,64));assert writer.isOpened()
        for _ in range(4):writer.write(np.full((64,64,3),80,np.uint8))
        writer.release()
    preview.with_suffix('.json').write_text(json.dumps({'schema':'model_preview_v1','status':'completed','source':str(source),'tracking':None}))
    (folder/'animation.blend').write_bytes(b'fixture')
    (cache/'scene.json').write_text(json.dumps({'source_blend':str(folder/'animation.blend'),'source_sha256':'fixture','names':['pelvis','head'],
        'parents':[-1,0],'fps':10,'frames':4,'frame_start':1}))
    rest=np.tile(np.eye(4),(2,1,1));rest[1,2,3]=1
    np.savez(cache/'scene.npz',vertices=np.array([[0,0,0],[.1,0,0],[0,0,1]]),triangles=np.array([[0,1,2]]),
        weights=np.ones((3,1)),weight_ids=np.zeros((3,1),int),rest=rest,locations=np.zeros((4,2,3)),quaternions=np.tile([1.,0,0,0],(4,2,1)),
        scales=np.ones((4,2,3)),object_matrices=np.tile(np.eye(4),(4,1,1)))
    calls=[]
    def prepare(path,cancelled):calls.append(path);return cache
    monkeypatch.setattr(edit_job,'prepare_scene',prepare)
    root=TkinterDnD.Tk();root.withdraw();app=PrototypeApp(root)
    try:
        app.result_panel.root=tmp_path;app.result_panel.refresh();root.update()
        assert not hasattr(app,'engine_button') and not hasattr(app,'mode_box')
        assert not hasattr(app.studio,'bone_generate_button') and app.skeleton_panel.convert_button is None
        assert app.result_panel.preview_button is None and app.result_panel.refresh_button is None
        assert not hasattr(app.studio.editor,'load_button') and len(app.studio.editor.buttons)==3
        app.studio.show_stage(3)
        deadline=time.monotonic()+10
        while time.monotonic()<deadline and (app.studio.editor.clip is None or app.busy):root.update();time.sleep(.01)
        assert calls==[preview] and app.studio.editor.clip is not None and not app.busy
        app.studio.show_stage(0);root.update()
        app.result_panel.tree.selection_set(next(k for k,v in app.result_panel.rows.items() if v['path']==folder))
        app.result_panel.select();assert app.capture is not None and app.preview_path==source
        app.seek_var.set(2);app.seek_end();app.result_panel.refresh(selected=folder);root.update()
        assert app.position==2
        assert not app.studio.builtin_apply_button.winfo_manager() and not app.studio.builtin_install_button.winfo_manager()
    finally:app.studio.editor.pause();app.stop_video();root.destroy()
