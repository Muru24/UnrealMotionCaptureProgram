from pathlib import Path
from types import SimpleNamespace as NS
import json
import numpy as np
import pytest
from core.pose2d.mask_tracking import MaskTrack
from app.gui_jobs import JobSettings


def scores(box=(20,20,60,80)):
    a=np.full((120,160),-6.,np.float32)
    x1,y1,x2,y2=box;a[y1:y2,x1:x2]=6
    return a


def test_visible_mask_creates_padded_original_image_roi_without_keypoints():
    row=MaskTrack(160,120,30).evaluate(scores(),4,0)
    assert row['person_bbox']==[20,20,60,80] and row['roi']==[10,11,70,89]
    assert row['tracking']['state']=='tracked' and not row['mask']['identity_verified']
    assert not row['detector_diagnostics']['people_count_observed']


@pytest.mark.parametrize('kind,reason',[
    ('empty','empty_or_tiny_mask'),('object_absent','object_not_visible'),
    ('nonfinite','nonfinite_mask'),('full','mask_covers_frame'),('unstable','unstable_mask')])
def test_bad_mask_never_supplies_sam3d_roi(kind,reason):
    a=scores();obj=4
    if kind=='empty':a[:]=-6
    elif kind=='object_absent':obj=-1
    elif kind=='nonfinite':a[0,0]=np.nan
    elif kind=='full':a[:]=6
    elif kind=='unstable':a[a>0]=.1
    row=MaskTrack(160,120,30).evaluate(a,obj,0)
    assert row['roi'] is None and row['person_bbox'] is None
    assert row['tracking']['reason']==reason


def test_jump_is_not_prediction_and_recovery_starts_new_segment():
    policy=MaskTrack(160,120,30)
    policy.evaluate(scores(),4,0)
    bad=policy.evaluate(scores((120,20,150,80)),4,1)
    assert bad['roi'] is None and bad['tracking']['reason']=='mask_position_jump'
    good=policy.evaluate(scores(),4,2)
    assert good['tracking_segment']==1 and good['tracking']['missing_frames']==0


def test_fragmentation_is_held_but_a_small_detached_limb_is_included():
    a=np.full((120,160),-6.,np.float32)
    a[10:20,10:20]=6;a[40:50,40:50]=6;a[80:90,80:90]=6
    assert MaskTrack(160,120,30).evaluate(a,4,0)['tracking']['reason']=='fragmented_mask'
    a=scores();a[85:90,70:75]=6
    assert MaskTrack(160,120,30).evaluate(a,4,0)['person_bbox']==[20,20,75,90]


def test_mask_dimensions_cannot_silently_change():
    with pytest.raises(ValueError,match='dimensions'):
        MaskTrack(160,120,30).evaluate(np.ones((120,120)),4,0)


def test_sam2_settings_only_allowed_for_sam3d():
    assert JobSettings(stage='sam3d',tracking_method='sam2').tracking_method=='sam2'
    with pytest.raises(ValueError):JobSettings(stage='pose3d',tracking_method='sam2')
    with pytest.raises(ValueError):JobSettings(stage='sam3d',tracking_method='unknown')


def job_fixture(monkeypatch,tmp_path):
    import app.sam2_job as job
    closed=[]
    monkeypatch.setattr(job,'validate_runtime',lambda:Path('python.exe'))
    capture=NS(read=lambda:(True,np.zeros((120,160,3),np.uint8)),release=lambda:closed.append('capture'))
    monkeypatch.setattr(job.cv2,'VideoCapture',lambda *a:capture)
    backend=NS(detect=lambda frame:np.array([[10,20,50,100],[90,20,130,100]],float),
               association_keypoints=lambda *a:pytest.fail('2D keypoints must never be requested'),
               close=lambda:closed.append('backend'))
    metadata=NS(width=160,height=120,fps=30,frame_count=1)
    return job,backend,metadata,closed


def test_sam2_initial_selection_and_close_do_not_use_pose(monkeypatch,tmp_path):
    job,backend,metadata,closed=job_fixture(monkeypatch,tmp_path)
    plan={'status':'completed','frames':[{'frame_index':0}]}
    (tmp_path/'sam2-plan.json').write_text(json.dumps(plan))
    monkeypatch.setattr(job.subprocess,'Popen',lambda *a,**k:NS(poll=lambda:0,returncode=0))
    result=job.build_sam2_plan(Path('input.mp4'),metadata,JobSettings(stage='sam3d',target_index=1,tracking_method='sam2'),
        lambda:False,lambda *a:None,lambda s:backend,tmp_path)
    assert result==plan and closed==['capture','backend']
    request=json.loads((tmp_path/'sam2-request.json').read_text(encoding='utf-8'))
    assert request['initial_box']==[90,20,130,100] and request['target_index']==1


def test_sam2_ambiguous_initial_frame_requires_selection(monkeypatch,tmp_path):
    job,backend,metadata,closed=job_fixture(monkeypatch,tmp_path)
    with pytest.raises(ValueError,match='인물 번호'):
        job.build_sam2_plan('input.mp4',metadata,JobSettings(stage='sam3d',tracking_method='sam2'),
            lambda:False,lambda *a:None,lambda s:backend,tmp_path)
    assert closed==['capture','backend'] and not (tmp_path/'sam2-request.json').exists()


def test_cancel_stops_only_created_child_and_removes_its_temp_frames(monkeypatch,tmp_path):
    import app.sam3d_job
    job,backend,metadata,closed=job_fixture(monkeypatch,tmp_path)
    state={'cancel':False,'stopped':False}
    def poll():
        state['cancel']=True
        return 0 if state['stopped'] else None
    child=NS(poll=poll)
    monkeypatch.setattr(job.subprocess,'Popen',lambda *a,**k:child)
    monkeypatch.setattr(app.sam3d_job,'terminate_worker',lambda p:state.update(stopped=p is child))
    temporary=tmp_path/'sam2-frames-own';temporary.mkdir();(temporary/'0.jpg').write_bytes(b'fixture')
    with pytest.raises(KeyboardInterrupt):
        job.build_sam2_plan('input.mp4',metadata,JobSettings(stage='sam3d',target_index=0,tracking_method='sam2'),
            lambda:state['cancel'],lambda *a:None,lambda s:backend,tmp_path)
    assert state['stopped'] and not temporary.exists()


def test_gui_sam2_option_preserves_sam3d_stage():
    from app.gui import PrototypeApp
    value=lambda text:NS(get=lambda:text)
    app=NS(mode=value('SAM 3D + SAM 2 마스크 (시험)'),target=value('대상 1'),single=value(False),joint_anchors={})
    settings=PrototypeApp.settings(app)
    assert settings.stage=='sam3d' and settings.tracking_method=='sam2' and settings.target_index==1
