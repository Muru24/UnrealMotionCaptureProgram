from types import SimpleNamespace as NS
import json
import cv2
import numpy as np
import pytest

from app.gui_jobs import JobSettings
from app.target_start import find_target_start
from core.pose2d.mask_tracking import MaskTrack,waiting_for_target


def setup_scan(monkeypatch,appear=10,people=1):
    import app.target_start as scan
    closed=[];detected=[]
    frames=[np.full((120,160,3),i,np.uint8) for i in range(20)]
    remaining=iter(frames)
    class Capture:
        def read(self):
            frame=next(remaining,None)
            return frame is not None,frame
        def release(self):closed.append('capture')
    monkeypatch.setattr(scan.cv2,'VideoCapture',lambda *a:Capture())
    def detect(frame):
        i=int(frame[0,0,0]);detected.append(i)
        return np.array([[20+50*j,20,50+50*j,100] for j in range(people)] if i>=appear else [],float).reshape(-1,4)
    backend=NS(detect=detect,close=lambda:closed.append('backend'))
    return backend,detected,closed


def settings(**kwargs):return JobSettings(stage='sam3d',tracking_method='sam2',**kwargs)


def test_auto_finds_person_at_frame_ten_and_closes_resources(monkeypatch):
    backend,seen,closed=setup_scan(monkeypatch)
    index,frame,boxes=find_target_start('input.mp4',settings(),lambda:False,lambda s:backend)
    assert index==10 and int(frame[0,0,0])==10 and len(boxes)==1
    assert seen==list(range(11)) and closed==['capture','backend']


def test_explicit_position_inspects_only_that_frame(monkeypatch):
    backend,seen,_=setup_scan(monkeypatch,appear=2)
    index,_,_=find_target_start('input.mp4',settings(target_frame=15),lambda:False,lambda s:backend)
    assert index==15 and seen==[15]


def test_explicit_empty_position_does_not_silently_choose_someone_later(monkeypatch):
    backend,seen,_=setup_scan(monkeypatch)
    index,_,boxes=find_target_start('input.mp4',settings(target_frame=5),lambda:False,lambda s:backend)
    assert index==5 and len(boxes)==0 and seen==[5]


def test_first_appearance_can_be_ambiguous_without_auto_switching(monkeypatch):
    backend,seen,_=setup_scan(monkeypatch,people=2)
    index,_,boxes=find_target_start('input.mp4',settings(),lambda:False,lambda s:backend)
    assert index==10 and len(boxes)==2 and seen[-1]==10


@pytest.mark.parametrize('frame,message',[(None,'인물 후보'),(30,'프레임')])
def test_no_person_or_missing_frame_gives_selection_error_and_closes(monkeypatch,frame,message):
    backend,_,closed=setup_scan(monkeypatch,appear=99)
    with pytest.raises(ValueError,match=message):
        find_target_start('input.mp4',settings(target_frame=frame),lambda:False,lambda s:backend)
    assert closed==['capture','backend']


def test_scan_cancelled_inside_blank_prefix_closes_backend(monkeypatch):
    backend,seen,closed=setup_scan(monkeypatch)
    with pytest.raises(KeyboardInterrupt):
        find_target_start('input.mp4',settings(),lambda:len(seen)>=4,lambda s:backend)
    assert len(seen)==4 and closed==['capture','backend']


@pytest.mark.parametrize('frame',[-1,True,2.5])
def test_target_frame_validation(frame):
    with pytest.raises(ValueError):settings(target_frame=frame)


def test_late_mask_start_is_accepted_and_subsequent_loss_guard_still_works():
    logits=np.full((120,160),-6.,np.float32);logits[20:100,20:50]=6
    image=np.full((120,160,3),80,np.uint8)
    tracker=MaskTrack(160,120,30,motion_guard=True,start_index=10)
    first=tracker.evaluate(logits,4,10,frame=image)
    assert first['tracking']['state']=='tracked' and not first['tracking']['requires_reselection']
    assert first['timestamp']==10/30
    for i in range(11,29):
        row=tracker.evaluate(np.full_like(logits,-6),-4,i,frame=image)
    assert row['roi'] is None and row['tracking']['requires_reselection']
    with pytest.raises(ValueError,match='consecutive'):tracker.evaluate(logits,4,30,frame=image)


def test_prefix_never_predicts_or_sends_roi_to_sam3d():
    from app.sam3d_worker import predict_target
    estimator=NS(process_one_image=lambda *a,**k:pytest.fail('No pose before target start'))
    image=np.zeros((120,160,3),np.uint8)
    for i in range(10):
        row=waiting_for_target(i,30)
        assert row['timestamp']==i/30 and row['tracking']['state']=='uninitialized'
        assert row['roi'] is None and row['person_bbox'] is None
        assert not row['motion']['prediction_only'] and not row['tracking']['requires_reselection']
        assert predict_target(estimator,image,row,1) is None
        json.dumps(row,allow_nan=False)


def test_sam2_request_preserves_late_frame_and_target_index(monkeypatch,tmp_path):
    import app.sam2_job as job
    backend,_,_=setup_scan(monkeypatch,people=2)
    monkeypatch.setattr(job,'validate_runtime',lambda:tmp_path/'python.exe')
    monkeypatch.setattr(job.subprocess,'Popen',lambda *a,**k:NS(poll=lambda:0,returncode=0))
    (tmp_path/'sam2-plan.json').write_text(json.dumps({'status':'completed','frames':[{'frame_index':0}]}))
    job.build_sam2_plan('input.mp4',NS(width=160,height=120,fps=30,frame_count=20),settings(target_index=1),
                        lambda:False,lambda *a:None,lambda s:backend,tmp_path)
    request=json.loads((tmp_path/'sam2-request.json').read_text(encoding='utf-8'))
    assert request['initial_frame_index']==10 and request['target_index']==1
    assert request['initial_box']==[70,20,100,100]


def test_gui_preview_frame_is_bound_to_extraction_and_resets_on_reload(monkeypatch,tmp_path):
    from tkinterdnd2 import TkinterDnD
    import app.gui_jobs as jobs
    from app.gui import PrototypeApp
    from test_gui import pump
    source=tmp_path/'late.mp4';writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*'mp4v'),30,(160,120))
    for i in range(20):writer.write(np.full((120,160,3),0 if i<10 else 80,np.uint8))
    writer.release()
    monkeypatch.setattr(jobs,'make_backend',lambda s:NS(
        detect=lambda f:np.array([[20,20,50,100]],float) if f.mean()>20 else np.empty((0,4)),close=lambda:None))
    root=TkinterDnD.Tk();root.withdraw();app=PrototypeApp(root)
    try:
        app.load_source(source);pump(root,lambda:not app.busy)
        app.find_candidates();pump(root,lambda:not app.busy)
        assert app.target_frame==app.position==app.settings().target_frame==10
        assert app.settings().target_index==0
        app.seek_var.set(15);app.seek_end();app.find_candidates();pump(root,lambda:not app.busy)
        assert app.settings().target_frame==15
        app.load_source(source);pump(root,lambda:not app.busy)
        assert app.target_frame is None
    finally:app.stop_video();root.destroy()
