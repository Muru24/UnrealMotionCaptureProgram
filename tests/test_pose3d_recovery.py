from types import SimpleNamespace as NS

import numpy as np
import pytest

from core.pose2d.tracker import TargetTracker
from core.pose3d.mediapipe_backend import MediaPipeBackend, convert_landmarks
from core.pose3d.interface import Pose3DError


def raw_pose():
    image = [NS(x=.3+i*.01,y=.2+i*.01,z=.04,visibility=.9,presence=.8) for i in range(33)]
    world = [NS(x=i*.01,y=i*.02,z=-.2) for i in range(33)]
    return image,world


def recovery_backend(raw):
    backend = MediaPipeBackend.__new__(MediaPipeBackend)
    backend.tracker = TargetTracker(target_index=0)
    backend.tracker.box = np.array([60.,80.,200.,220.])
    backend._previous_supports = ['previous']
    backend.last_diagnostics = {'raw_pose_count':0}
    backend.mp = NS(ImageFormat=NS(SRGB=1),Image=lambda **kw:kw)
    backend._recovery_landmarker = NS(detect=lambda _:raw)
    return backend


def test_recovery_maps_pixels_and_depth_but_preserves_native_world_and_scores():
    im,world = raw_pose()
    raw = NS(pose_landmarks=[im],pose_world_landmarks=[world],segmentation_masks=[])
    backend = recovery_backend(raw)
    candidates = backend._recover_candidates(np.zeros((300,320,3),np.uint8))
    assert len(candidates)==1
    p = candidates[0][1][11]
    assert p.image_x == pytest.approx(28+.41*204)
    assert p.image_y == pytest.approx(48+.31*204)
    assert p.image_z_normalized == pytest.approx(.04*204/320)
    assert (p.x,p.y,p.z,p.visibility,p.presence)==(.11,.22,-.2,.9,.8)
    assert backend._previous_supports==[]
    assert backend.last_diagnostics['recovery']['roi']==[28,48,232,252]


def test_crop_extrapolation_remains_invalid_even_if_it_maps_inside_source():
    im,world = raw_pose()
    im[15].x=-.05
    backend = recovery_backend(NS(pose_landmarks=[im],pose_world_landmarks=[world],segmentation_masks=[]))
    points = backend._recover_candidates(np.zeros((300,320,3),np.uint8))[0][1]
    assert points[15].image_x > 0
    assert not points[15].valid
    assert points[15].reason=='outside_recovery_crop'


@pytest.mark.parametrize('bad',['world','mask'])
def test_recovery_schema_mismatch_fails_explicitly(bad):
    im,world = raw_pose()
    backend = recovery_backend(NS(pose_landmarks=[im],pose_world_landmarks=[] if bad=='world' else [world],
                                  segmentation_masks=[object(),object()] if bad=='mask' else []))
    with pytest.raises(Pose3DError,match='counts differ'):
        backend._recover_candidates(np.zeros((300,320,3),np.uint8))


def test_recovery_mask_is_translated_into_original_frame():
    im,world = raw_pose()
    mask = np.zeros((204,204,1),np.float32); mask[40:180,50:150]=1
    backend = recovery_backend(NS(pose_landmarks=[im],pose_world_landmarks=[world],
                                  segmentation_masks=[NS(numpy_view=lambda:mask)]))
    box,_ = backend._recover_candidates(np.zeros((300,320,3),np.uint8))[0]
    assert box[0]==pytest.approx(74,abs=1)
    assert box[1]==pytest.approx(82.4,abs=1)
    assert backend.last_diagnostics['box_sources']==['recovery_segmentation']


@pytest.mark.parametrize('state',['initial','lost','normal'])
def test_no_recovery_for_initial_selection_latched_loss_or_existing_candidates(monkeypatch,state):
    im,world=raw_pose(); points=convert_landmarks(im,world,320,300)
    frame=np.full((300,320,3),100,np.uint8)
    backend=recovery_backend(None)
    backend.tracker=TargetTracker(target_index=0)
    box=np.array([60.,80.,200.,220.],np.float32)
    backend.tracker.select(frame,np.array([box]))
    if state=='initial': backend.tracker=TargetTracker()
    if state=='lost':
        backend.tracker.latched=True
        backend.tracker.missing=6
    monkeypatch.setattr(backend,'_candidates',lambda *a:[(box,points)] if state=='normal' else [])
    monkeypatch.setattr(backend,'_recover_candidates',lambda *a:pytest.fail('unexpected retry'))
    backend.infer(frame,0)


def test_recovery_exposes_two_overlapping_candidates_and_keeps_ambiguity_latched(monkeypatch):
    im,world=raw_pose(); points=convert_landmarks(im,world,320,300)
    frame=np.full((300,320,3),100,np.uint8)
    backend=recovery_backend(None)
    backend.tracker=TargetTracker(target_index=0)
    box=np.array([60.,50.,200.,280.],np.float32)
    backend.tracker.select(frame,np.array([box]))
    monkeypatch.setattr(backend,'_candidates',lambda *a:[])
    monkeypatch.setattr(backend,'_recover_candidates',lambda *a:[(box,points),(box+np.array([10,0,10,0]),points)])
    monkeypatch.setattr(backend,'close',lambda:None)
    monkeypatch.setattr(backend,'_create_landmarker',lambda:None)
    result=backend.infer(frame,0)
    assert backend.tracker.latched
    assert result.pose2d.person_bbox is None
    assert all(p.x is None and not p.valid for p in result.landmarks)


def test_close_releases_primary_and_recovery_exactly_once():
    backend=MediaPipeBackend.__new__(MediaPipeBackend)
    closed=[]
    backend.landmarker=NS(close=lambda:closed.append('primary'))
    backend._recovery_landmarker=NS(close=lambda:closed.append('retry'))
    backend.close(); backend.close()
    assert closed==['primary','retry']
