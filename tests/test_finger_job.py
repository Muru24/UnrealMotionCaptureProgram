import json
from pathlib import Path
import pytest
from app import finger_job as job
from app.knee_job import digest


def fixture(tmp_path):
 p=tmp_path/'animation-base';p.mkdir();blend=p/'animation.blend';blend.write_bytes(b'original blend');(p/'animation.json').write_text('{}');(p/'corrected-motion.json').write_text('{}');raw=tmp_path/'sam3d.json';raw.write_text('{}')
 (p/'report.json').write_text(json.dumps({'status':'completed','hand_raw_sha256':digest(raw),'motion_sha256':'motionhash'}));return blend,raw


def test_cancel_and_wrong_raw_never_start_process(tmp_path,monkeypatch):
 b,r=fixture(tmp_path);monkeypatch.setattr(job.subprocess,'Popen',lambda *a,**k:pytest.fail('started'))
 with pytest.raises(KeyboardInterrupt):job.export_fingers(b,r,lambda:True)
 r.write_text('changed')
 with pytest.raises(ValueError,match='다릅니다'):job.export_fingers(b,r)


def test_finger_job_success_preserves_base_and_records_52(tmp_path,monkeypatch):
 b,r=fixture(tmp_path);before=b.read_bytes()
 class Process:
  returncode=0
  def poll(self):return 0
 def start(args,**kwargs):
  assert isinstance(args,list) and '--python-exit-code' in args
  out=Path(args[-1]);out.mkdir();(out/'animation.blend').write_bytes(b'52bone');(out/'animation.json').write_text(json.dumps({'bone_names':[str(i) for i in range(52)],'frames':[{}]}));return Process()
 monkeypatch.setattr(job.subprocess,'Popen',start)
 out=job.export_fingers(b,r,executable='blender.exe');report=json.loads((out.parent/'report.json').read_text())
 assert b.read_bytes()==before and report['bones']==52 and report['status']=='completed'
 assert (out.parent/'corrected-motion.json').read_text()=='{}'


def test_finger_process_failure_does_not_publish_completed(tmp_path,monkeypatch):
 b,r=fixture(tmp_path)
 class Process:
  returncode=1
  def poll(self):return 1
 monkeypatch.setattr(job.subprocess,'Popen',lambda *a,**k:Process())
 with pytest.raises(RuntimeError):job.export_fingers(b,r,executable='blender.exe')
 assert list(tmp_path.glob('animation-fingers-*/report.json'))==[]


def test_crop_provenance_and_selection_record(tmp_path,monkeypatch):
 from test_refined_hands import fixture as crop_fixture
 b,r=fixture(tmp_path);raw,crop=crop_fixture();r.write_text(json.dumps(raw))
 report=json.loads((b.parent/'report.json').read_text());report['hand_raw_sha256']=digest(r);(b.parent/'report.json').write_text(json.dumps(report))
 (b.parent/'corrected-motion.json').write_text(json.dumps({'source_sha256':'video'}))
 folder=tmp_path/'hand_crop_test';folder.mkdir();path=folder/'report.json'
 crop.update(raw_sha256=digest(r),source_sha256='wrong');path.write_text(json.dumps(crop))
 monkeypatch.setattr(job.subprocess,'Popen',lambda *a,**k:pytest.fail('started with wrong provenance'))
 with pytest.raises(ValueError,match='해시'):job.export_fingers(b,r,crop_report=path)
 crop['source_sha256']='video';path.write_text(json.dumps(crop))
 class Process:
  returncode=0
  def poll(self):return 0
 def start(args,**kwargs):
  selection=json.loads(Path(args[-1]).read_text());assert selection['selected_hand_frames']=={'l':5,'r':0}
  out=Path(args[-2]);out.mkdir();(out/'animation.blend').write_bytes(b'52');(out/'animation.json').write_text(json.dumps({'bone_names':list(range(52)),'frames':[{}]}));return Process()
 monkeypatch.setattr(job.subprocess,'Popen',start)
 result=job.export_fingers(b,r,crop_report=path,executable='blender.exe')
 assert (result.parent/'hand-selection.json').is_file()
 assert job.latest_hand_crop(tmp_path)==path
 assert not list(tmp_path.glob('*.selection.json'))

def test_gui_finger_export_button_worker(tmp_path,monkeypatch):
    from tkinterdnd2 import TkinterDnD
    from app.gui import PrototypeApp
    import app.motion_job as motion_job
    import app.animation_job as animation_job
    import app.engine_export_job as engine_job
    from test_motion_skeleton import job_fixture
    from test_gui import pump
    import app.gui as gui
    source,folder=job_fixture(tmp_path);base=folder/'motion/animation-base/animation.blend';target=folder/'motion/animation-fingers-test/animation.blend';calls=[]
    monkeypatch.setattr(motion_job,'ensure_motion',lambda *a:(folder/'motion/motion.json','computed'))
    monkeypatch.setattr(animation_job,'export_animation',lambda *a:base)
    def fingers(blend,raw,cancelled):calls.append(('fingers',blend,raw));return target
    monkeypatch.setattr(job,'export_fingers',fingers)
    monkeypatch.setattr(engine_job,'export_engine_fbx',lambda blend,cancelled:calls.append(('engine',blend)))
    monkeypatch.setattr(gui.messagebox,'showinfo',lambda *a:None)
    root=TkinterDnD.Tk();root.withdraw();app=PrototypeApp(root)
    try:
        app.result_dir=folder;app.generate_animation(fingers=True);assert app.busy
        assert not hasattr(app,'finger_button')
        assert str(app.cancel_button.cget('state'))=='normal'
        pump(root,lambda:not app.busy)
        assert calls==[('fingers',base,folder/'sam3d.json'),('engine',target)]
        assert '52본' in app.status_text.get()
    finally:app.stop_video();root.destroy()
