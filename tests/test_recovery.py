from types import SimpleNamespace as NS
import numpy as np
import pytest
from core.pose2d.recovery import recover_candidates
from core.pose2d.rtmpose_backend import RTMPoseBackend
from core.pose2d.interface import Pose2DError
from core.pose2d.tracker import TargetTracker


def prepared():
    frame=np.full((600,400,3),120,np.uint8)
    tracker=TargetTracker(target_index=0,motion_fps=30,max_missing=12)
    tracker.select(frame,np.array([[140,150,260,450]],float))
    return frame,tracker


def test_recovery_is_an_observation_and_does_not_advance_or_update_filter():
    frame,t=prepared();before=t.motion.x.copy();variance=t.motion.P.copy();calls=[]
    found=np.array([[142,150,262,450]],float)
    backend=NS(detect_region=lambda f,r:(calls.append(r.copy()) or found,(np.zeros((1,17,2)),np.ones((1,17)))))
    boxes,pose,diag=recover_candidates(frame,t,backend,np.empty((0,4)),None)
    assert diag['attempted'] and diag['added']==1 and np.array_equal(boxes,found)
    assert pose[0].shape==(1,17,2)
    assert np.array_equal(t.motion.x,before) and np.array_equal(t.motion.P,variance)
    x,y,x2,y2=calls[0];assert 0<=x<x2<=400 and 0<=y<y2<=600


@pytest.mark.parametrize('state',['stable','latched','ambiguous','no_target'])
def test_recovery_skips_stable_or_unsafe_states(state):
    frame,t=prepared();t.missing=1
    boxes=np.empty((0,4))
    if state=='stable':t.missing=0;boxes=np.array([[140,150,260,450]],float)
    if state=='latched':t.latched=True
    if state=='ambiguous':t.gap_ambiguous=True
    if state=='no_target':t.box=None
    def forbidden(*args):raise AssertionError('Unexpected regional detection')
    _,_,diag=recover_candidates(frame,t,NS(detect_region=forbidden),boxes,None)
    assert not diag['attempted']


def test_regional_duplicate_cannot_replace_full_frame_detection():
    frame,t=prepared();t.missing=1;boxes=np.array([[140,150,260,450]],float)
    keypoints=(np.ones((1,17,2)),np.ones((1,17)))
    backend=NS(detect_region=lambda *args:(boxes+1,(np.zeros((1,17,2)),np.ones((1,17)))))
    result,pose,diag=recover_candidates(frame,t,backend,boxes,keypoints)
    assert diag['added']==0 and np.array_equal(result,boxes) and np.array_equal(pose[0],keypoints[0])


def test_region_coordinates_and_detector_diagnostics_are_restored_even_on_error():
    backend=RTMPoseBackend.__new__(RTMPoseBackend)
    backend.last_detection_diagnostics={'raw_count':7}
    def detect(crop):
        backend.last_detection_diagnostics={'raw_count':1}
        assert crop.shape==(100,80,3)
        return np.array([[2,3,50,90]],float)
    backend.detect=detect
    backend.association_keypoints=lambda *args:(np.full((1,17,2),4.),np.ones((1,17)))
    frame=np.zeros((300,300,3),np.uint8)
    boxes,(coords,scores)=backend.detect_region(frame,[20,30,100,130])
    assert boxes.tolist()==[[22,33,70,120]] and coords[0,0].tolist()==[24,34]
    assert backend.last_detection_diagnostics=={'raw_count':7}
    def fail(*args):raise RuntimeError('model failed')
    backend.association_keypoints=fail
    with pytest.raises(RuntimeError):backend.detect_region(frame,[20,30,100,130])
    assert backend.last_detection_diagnostics=={'raw_count':7}
    with pytest.raises(Pose2DError):backend.detect_region(frame,[-1,0,100,130])
