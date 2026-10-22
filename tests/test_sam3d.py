import numpy as np
import pytest
from app.sam3d_job import select_roi
from app.gui_jobs import JobSettings


def test_sam_candidate_numpy_selection_and_clipping():
    boxes=np.array([[10,20,30,40],[20,30,190,180]])
    assert select_roi(boxes,None,200,200)==[0,7.5,200,200]
    assert select_roi(boxes,0,200,200)==[5,17,35,43]
    assert JobSettings(stage='sam3d').stage=='sam3d'


def test_sam_missing_candidate_does_not_silently_use_whole_frame():
    with pytest.raises(ValueError):select_roi(np.empty((0,4)),None,200,200)
    with pytest.raises(ValueError):select_roi(np.array([[0,0,20,30]]),1,200,200)


def test_sam_cancel_terminates_only_its_child_and_marks_partial(monkeypatch,tmp_path):
    import json
    from types import SimpleNamespace as NS
    import app.sam3d_job as job
    closed=[]
    state={'stop':False,'terminated':False}
    class Child:
        def poll(self):
            state['stop']=True
            return 0 if state['terminated'] else None
        def terminate(self):state['terminated']=True
        def wait(self,timeout):return 0
    monkeypatch.setattr(job,'read_source',lambda source:(NS(width=200,height=200,fps=30,frame_count=1,to_dict=lambda:{}),None))
    monkeypatch.setattr(job.subprocess,'Popen',lambda *a,**k:Child())
    monkeypatch.setattr(job,'terminate_worker',lambda child:(child.terminate(),child.wait(timeout=15)))
    backend=NS(detect=lambda frame:np.array([[0,0,100,180]]),close=lambda:closed.append(True))
    def prepared(*args):
        backend.close()
        return {'status':'completed','target_id':1,'frames':[]}
    monkeypatch.setattr(job,'build_tracking_plan',prepared)
    (tmp_path/'source.mp4').write_bytes(b'synthetic source for mocked decoder')
    with pytest.raises(KeyboardInterrupt):
        job.run_sam3d(tmp_path/'source.mp4',tmp_path/'result',JobSettings(stage='sam3d'),
                      lambda:state['stop'],lambda *a:None,lambda settings:backend)
    assert closed==[True] and state['terminated']
    assert json.loads((tmp_path/'result/report.json').read_text(encoding='utf-8'))['status']=='cancelled'


def make_plan(monkeypatch,positions):
    from types import SimpleNamespace as NS
    import app.sam3d_job as job
    frames=[];boxes=[];closed=[]
    for position in positions:
        frame=np.zeros((200,400,3),np.uint8)
        candidates=[]
        # A second person appears to the left, changing candidate indexes.
        if frames:
            frame[30:180,0:30]=(255,0,0);candidates.append([0,30,30,180])
        if position is not None:
            frame[30:180,position:position+80]=(0,0,255)
            candidates.append([position,30,position+80,180])
        frames.append(frame);boxes.append(np.asarray(candidates,dtype=np.float32).reshape(-1,4))
    class Capture:
        def __init__(self):self.index=0
        def open(self,*a):return True
        def read(self):
            if self.index==len(frames):return False,None
            frame=frames[self.index];self.index+=1;return True,frame
        def release(self):closed.append('capture')
    capture=Capture();monkeypatch.setattr(job.cv2,'VideoCapture',lambda: capture)
    backend=NS(detect=lambda frame:boxes[capture.index-1],close=lambda:closed.append('backend'))
    metadata=NS(width=400,height=200,fps=30,frame_count=len(frames))
    plan=job.build_tracking_plan('input.mp4',metadata,JobSettings(stage='sam3d',target_index=0),
                                lambda:False,lambda *a:None,lambda s:backend)
    assert closed==['capture','backend']
    return plan


def test_roi_follows_same_id_when_candidate_indexes_change_and_short_gap(monkeypatch):
    plan=make_plan(monkeypatch,[60,70,None,90,100])
    assert plan['motion_policy']['measurement_noise']=='torso_scaled_shoulder_proxy_and_returning_hip_floor'
    f=plan['frames']
    assert f[0]['roi']!=f[1]['roi']
    assert f[1]['person_bbox'][0]==70 and f[1]['people_detected']==2
    assert f[2]['roi'] is None and f[2]['tracking']['state']=='uncertain'
    assert f[3]['tracking']['reason']=='reconnection_pending' and f[3]['roi'] is None
    assert f[4]['tracking']['reason']=='short_gap_reconnected'
    assert all(x['tracking']['track_id']==1 for x in f)


def test_long_loss_does_not_attach_to_the_other_person_or_returned_candidate(monkeypatch):
    plan=make_plan(monkeypatch,[60]+[None]*13+[70,80])
    assert all(f['roi'] is None for f in plan['frames'][1:])
    assert plan['frames'][-1]['tracking']['requires_reselection']


def test_sam_infers_only_tracked_roi_and_rejects_changed_identity():
    from app.sam3d_worker import predict_target
    calls=[]
    class Estimator:
        def process_one_image(self,frame,bboxes,inference_type):
            calls.append(bboxes.copy())
            return [{'pred_keypoints_2d':np.zeros((70,2)),'pred_keypoints_3d':np.zeros((70,3))}]
    frame=np.zeros((200,400,3),np.uint8)
    selected={'roi':[10,20,100,190],'tracking':{'state':'tracked','track_id':1}}
    assert predict_target(Estimator(),frame,selected,1) is not None
    assert calls[0].tolist()==[[10,20,100,190]]
    selected['tracking']['state']='lost';assert predict_target(Estimator(),frame,selected,1) is None
    assert len(calls)==1
    selected['tracking']={'state':'tracked','track_id':2}
    with pytest.raises(RuntimeError,match='identity'):predict_target(Estimator(),frame,selected,1)


def test_sam_same_height_nested_duplicate_keeps_crossing_guard_and_m1_default():
    from core.pose2d.tracker import suppress_duplicate_boxes
    frame=np.zeros((200,400,3),np.uint8);frame[20:180,20:180]=(0,0,255)
    nested=np.array([[20,20,180,180],[60,20,140,180]],dtype=np.float32)
    assert len(suppress_duplicate_boxes(nested))==2
    assert len(suppress_duplicate_boxes(nested,frame))==1
    crossing=np.array([[20,20,100,180],[35,20,115,180]],dtype=np.float32)
    assert len(suppress_duplicate_boxes(crossing,frame))==2
    short_person=np.array([[20,20,180,180],[40,60,160,170]],dtype=np.float32)
    assert len(suppress_duplicate_boxes(short_person,frame))==2


def test_windows_cancel_stops_real_venv_python_child(tmp_path):
    import os,sys,time,subprocess,ctypes
    from ctypes import wintypes
    from app.sam3d_job import terminate_worker
    if os.name!='nt' or os.environ.get('RUN_WINDOWS_PROCESS_TREE_TEST')!='1':
        pytest.skip('Opt in with RUN_WINDOWS_PROCESS_TREE_TEST=1 on a Windows desktop with process-management access')
    marker=tmp_path/'child-pid.txt'
    code='import os,sys,time;from pathlib import Path;Path(sys.argv[1]).write_text(str(os.getpid()));time.sleep(30)'
    process=subprocess.Popen([sys.executable,'-c',code,str(marker)],creationflags=subprocess.CREATE_NO_WINDOW)
    handle=None
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];kernel.WaitForSingleObject.restype=wintypes.DWORD
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    try:
        deadline=time.monotonic()+5
        while not marker.exists():
            assert time.monotonic()<deadline;time.sleep(.02)
        actual_pid=int(marker.read_text())
        handle=kernel.OpenProcess(0x00100000,False,actual_pid)
        assert handle
        terminate_worker(process)
        assert process.poll() is not None
        assert kernel.WaitForSingleObject(handle,5000)==0
    finally:
        if handle:kernel.CloseHandle(handle)
        if process.poll() is None:terminate_worker(process)
