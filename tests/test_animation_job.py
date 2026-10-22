import json
from pathlib import Path
import pytest
from app import animation_job as job


def motion(tmp_path):
    from core.motion.skeleton import definition
    spec=definition()
    data={'schema':'standard_motion_positions_v1','skeleton':spec,'video':{'fps':30},
          'frames':[{'frame_index':0,'positions':[b['head'] for b in spec['bones']]}]}
    folder=tmp_path/'motion';folder.mkdir();p=folder/'motion.json';p.write_text(json.dumps(data));return p


def test_cancel_before_process(tmp_path,monkeypatch):
    monkeypatch.setattr(job.subprocess,'Popen',lambda *a,**k:pytest.fail('Started on cancellation'))
    with pytest.raises(KeyboardInterrupt):job.export_animation(motion(tmp_path),lambda:True)


def test_foreign_filename_refused(tmp_path):
    p=tmp_path/'sam3d.json';p.write_text('{}')
    with pytest.raises(ValueError):job.export_animation(p)


def test_ground_evidence_requires_exact_packet_hash_and_timeline(tmp_path):
    p=motion(tmp_path);folder=tmp_path/'candidates_test';folder.mkdir()
    packet=folder/'selected-joints.json'
    points=[[float(i),float(i+1)] for i in range(70)]
    packet.write_text(json.dumps({'frames':[{'frame_index':0,'image_joints':points}]}))
    data=json.loads(p.read_text());data.update(source_kind='selected_candidates',input_sha256=job.digest(packet))
    pixels,path=job.ground_evidence(p,data)
    assert path==packet and pixels[0][0]==[13.,14.] and pixels[0][4]==[9.5,10.5]
    packet.write_text(json.dumps({'frames':[{'frame_index':1,'image_joints':points}]}))
    assert job.ground_evidence(p,data)==(None,None)
    data['input_sha256']=job.digest(packet)
    with pytest.raises(ValueError,match='timeline'):job.ground_evidence(p,data)


def test_process_failure_preserves_input_and_prior_files(tmp_path,monkeypatch):
    p=motion(tmp_path);original=p.read_bytes();old=p.parent/'animation-existing';old.mkdir();(old/'animation.blend').write_bytes(b'old')
    class Process:
        returncode=1
        def poll(self):return 1
    monkeypatch.setattr(job.subprocess,'Popen',lambda *a,**k:Process())
    with pytest.raises(RuntimeError):job.export_animation(p,executable='blender.exe')
    assert p.read_bytes()==original and (old/'animation.blend').read_bytes()==b'old'
    assert not list(p.parent.glob('animation-*/report.json'))


def test_export_success_argument_array_and_provenance(tmp_path,monkeypatch):
    p=motion(tmp_path)
    class Process:
        returncode=0
        def poll(self):return 0
    def start(args,**kwargs):
        assert isinstance(args,list) and '--python-exit-code' in args and not kwargs.get('shell')
        out=Path(args[-1]);out.mkdir();(out/'animation.blend').write_bytes(b'blend')
        (out/'animation.json').write_text(json.dumps({'frames':[{}],'frames_with_pose':1,'max_solved_head_error_m':0}))
        return Process()
    monkeypatch.setattr(job.subprocess,'Popen',start)
    result=job.export_animation(p,executable='blender.exe')
    report=json.loads((result.parent/'report.json').read_text())
    assert report['status']=='completed' and report['motion_sha256']==job.digest(p)


def test_cancellation_terminates_only_owned_process(tmp_path,monkeypatch):
    p=motion(tmp_path);calls=[]
    class Process:
        returncode=None
        def poll(self):return self.returncode
        def terminate(self):calls.append('terminate');self.returncode=-1
        def wait(self,timeout):calls.append('wait')
    monkeypatch.setattr(job.subprocess,'Popen',lambda *a,**k:Process())
    flags=iter([False,False,True])
    with pytest.raises(KeyboardInterrupt):job.export_animation(p,lambda:next(flags),executable='blender.exe',corrections=False)
    assert calls==['terminate','wait']


def test_latest_preview_requires_completed_untampered_matching_motion(tmp_path):
    p=motion(tmp_path);out=p.parent/'animation-test';out.mkdir()
    corrected=out/'corrected-motion.json';corrected.write_text('{}')
    report={'status':'completed','corrections':True,'motion_sha256':job.digest(p),'corrected_motion_sha256':job.digest(corrected)}
    (out/'report.json').write_text(json.dumps(report))
    assert job.latest_corrected_motion(p)==corrected.resolve()
    corrected.write_text('{"changed":true}')
    assert job.latest_corrected_motion(p)==p.resolve()
    corrected.write_text('{}');p.write_text('{"changed":true}')
    assert job.latest_corrected_motion(p)==p.resolve()


def test_gui_animation_export_wires_current_result_and_busy_state(tmp_path,monkeypatch):
    import app.gui as gui
    import app.motion_job as motion_job
    from tkinterdnd2 import TkinterDnD
    from test_gui import pump
    from test_motion_skeleton import job_fixture
    source,folder=job_fixture(tmp_path)
    target=folder/'motion/animation-test/animation.blend';target.parent.mkdir(parents=True);target.write_bytes(b'blend')
    from test_motion_skeleton import sample_raw
    from core.motion.skeleton import convert
    corrected=job.prepare_motion(convert(sample_raw(4)))
    (target.parent/'corrected-motion.json').write_text(json.dumps(corrected),encoding='utf-8')
    calls=[]
    monkeypatch.setattr(motion_job,'ensure_motion',lambda *a:(folder/'motion/motion.json','computed'))
    def export(path,cancelled):calls.append(path);return target
    monkeypatch.setattr(job,'export_animation',export)
    monkeypatch.setattr(gui.messagebox,'showinfo',lambda *a:None)
    root=TkinterDnD.Tk();root.withdraw();app=gui.PrototypeApp(root)
    try:
        app.result_dir=folder
        app.video_count=4
        assert app.animation_button.cget('text')=='Blender 애니메이션 저장'
        app.generate_animation();assert app.busy
        assert str(app.animation_button.cget('state'))=='disabled'
        pump(root,lambda:not app.busy)
        assert calls==[folder/'motion/motion.json']
        assert str(target) in app.status_text.get()
        assert str(app.animation_button.cget('state'))=='normal'
        assert app.skeleton_panel.points.shape==(4,22,3)
        assert 'SLERP' in app.skeleton_panel.label.cget('text')
    finally:app.stop_video();root.destroy()
