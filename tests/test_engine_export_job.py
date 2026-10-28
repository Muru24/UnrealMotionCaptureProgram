import json
from pathlib import Path
import pytest
from app import engine_export_job as job

def fixture(tmp_path):
    p=tmp_path/'animation.blend';p.write_bytes(b'preserved blend')
    (tmp_path/'animation.json').write_text(json.dumps({'schema':'standard_bone_animation_v1'}))
    return p

def test_cancel_before_launch(tmp_path,monkeypatch):
    monkeypatch.setattr(job.subprocess,'Popen',lambda *a,**k:pytest.fail('started'))
    with pytest.raises(KeyboardInterrupt):job.export_engine_fbx(fixture(tmp_path),lambda:True)

def test_wrong_schema_refused(tmp_path):
    p=fixture(tmp_path);p.with_suffix('.json').write_text('{}')
    with pytest.raises(ValueError):job.export_engine_fbx(p)

def test_success_hashes_and_hidden_argument_array(tmp_path,monkeypatch):
    p=fixture(tmp_path)
    class Process:
        returncode=0
        def poll(self):return 0
    def launch(args,**kw):
        assert isinstance(args,list) and '--python-exit-code' in args and not kw.get('shell')
        out=Path(args[-1]);out.mkdir();(out/'export.json').write_text('{"status":"exported"}')
        for name in ('Motion_Unreal.fbx','Motion_Unity.fbx'):(out/name).write_bytes(b'x'*2048)
        return Process()
    monkeypatch.setattr(job.subprocess,'Popen',launch)
    out=job.export_engine_fbx(p,executable='blender.exe');r=json.loads((out/'export.json').read_text())
    assert r['status']=='completed' and r['source_blend_sha256']==job.digest(p)
    assert p.read_bytes()==b'preserved blend' and len(r['file_sha256'])==2

def test_cancellation_stops_owned_process(tmp_path,monkeypatch):
    calls=[]
    class Process:
        returncode=None
        def poll(self):return self.returncode
        def terminate(self):calls.append('terminate');self.returncode=-1
        def wait(self,timeout):calls.append('wait')
    monkeypatch.setattr(job.subprocess,'Popen',lambda *a,**k:Process())
    flags=iter([False,True])
    with pytest.raises(KeyboardInterrupt):job.export_engine_fbx(fixture(tmp_path),lambda:next(flags),executable='blender.exe')
    assert calls==['terminate','wait']

def test_gui_engine_button_worker(tmp_path,monkeypatch):
    import app.gui as gui
    import app.animation_job as animation
    import app.motion_job as motion
    from tkinterdnd2 import TkinterDnD
    from test_gui import pump
    from test_motion_skeleton import job_fixture
    source,folder=job_fixture(tmp_path);calls=[]
    blend=folder/'motion/animation-x/animation.blend';out=blend.parent/'engine-x'
    monkeypatch.setattr(motion,'ensure_motion',lambda *a:(folder/'motion/motion.json','computed'))
    monkeypatch.setattr(animation,'export_animation',lambda *a:blend)
    monkeypatch.setattr(job,'export_engine_fbx',lambda p,c:(calls.append(p) or out))
    monkeypatch.setattr(gui.messagebox,'showinfo',lambda *a:None)
    root=TkinterDnD.Tk();root.withdraw();app=gui.PrototypeApp(root)
    try:
        app.result_dir=folder;app.generate_animation(engine=True);assert app.busy
        assert not hasattr(app,'engine_button')
        assert str(app.cancel_button.cget('state'))=='normal'
        pump(root,lambda:not app.busy)
        assert calls==[blend] and str(out) in app.status_text.get()
        assert str(app.cancel_button.cget('state'))=='disabled'
    finally:app.stop_video();root.destroy()
