import cv2
import numpy as np

from core.pose3d.point_tracking import ImagePointTracker


def test_clicked_patch_tracks_real_image_translation():
    rng=np.random.default_rng(4)
    image=np.zeros((200,200,3),np.uint8)
    image[70:110,70:110]=rng.integers(0,255,(40,40,3),dtype=np.uint8)
    tracker=ImagePointTracker()
    tracker.update(image,{'left_wrist':[90,90]})
    moved=cv2.warpAffine(image,np.float32([[1,0,5],[0,1,3]]),(200,200))
    result=tracker.update(moved,{})
    assert np.linalg.norm(result['left_wrist']-[95,93])<.5


def test_blank_or_disappeared_patch_is_not_a_valid_track():
    blank=np.zeros((200,200,3),np.uint8)
    tracker=ImagePointTracker();tracker.update(blank,{'left_wrist':[90,90]})
    assert tracker.update(blank,{})=={}
    assert 'left_wrist' in tracker.bound


def test_explicit_torso_reselection_drops_old_person_points():
    image=np.zeros((200,200,3),np.uint8)
    tracker=ImagePointTracker();tracker.update(image,{'left_wrist':[90,90]})
    tracker.update(image,{'pelvis':[80,150],'chest':[80,80]})
    assert 'left_wrist' not in tracker.bound and 'left_wrist' not in tracker.points
