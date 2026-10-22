import numpy as np
import pytest
from core.pose2d.mask_tracking import MaskTrack

def logits(x=20,y=20,width=30,height=60):
    a=np.full((160,320),-6.,np.float32);a[y:y+height,x:x+width]=6;return a

def tracker():return MaskTrack(320,160,30,motion_guard=True)

def test_short_missing_keeps_position_prediction_without_pose_roi():
    p=tracker()
    for i in range(8):p.evaluate(logits(20+i*3),4,i)
    row=p.evaluate(logits(),-1,8)
    assert row['roi'] is None and row['person_bbox'] is None
    assert row['motion']['prediction_only'] and row['motion']['predicted_center'][0]>50
    assert row['tracking']['track_id']==1 and not row['motion']['identity_verified']
    recovered=p.evaluate(logits(47),4,9)
    assert recovered['roi'] is not None and recovered['tracking_segment']==1

def test_distant_mask_is_not_accepted_after_repeated_rejections():
    p=tracker();p.evaluate(logits(),4,0)
    for i in range(1,10):
        row=p.evaluate(logits(230),4,i)
        assert row['roi'] is None and row['tracking']['reason']=='mask_motion_mismatch'
    assert p.previous[0]==0

def test_multi_frame_gap_requires_two_consistent_observations():
    p=tracker();p.evaluate(logits(),4,0)
    for i in range(1,4):p.evaluate(logits(),-1,i)
    first=p.evaluate(logits(),4,4);second=p.evaluate(logits(),4,5)
    assert first['tracking']['reason']=='mask_reconnection_pending' and first['roi'] is None
    assert second['roi'] is not None and second['tracking_segment']==1

def test_reconnection_confirmation_cannot_bridge_another_bad_mask():
    p=tracker();p.evaluate(logits(),4,0)
    for i in range(1,4):p.evaluate(logits(),-1,i)
    p.evaluate(logits(),4,4);p.evaluate(logits(),-1,5)
    assert p.evaluate(logits(),4,6)['tracking']['reason']=='mask_reconnection_pending'

@pytest.mark.parametrize('cut',[True,False])
def test_cut_or_long_loss_cannot_silently_reassign_target(cut):
    p=tracker();p.evaluate(logits(),4,0)
    if cut:row=p.evaluate(logits(),4,1,scene_cut=True)
    else:
        for i in range(1,18):row=p.evaluate(logits(),-1,i)
    assert row['motion']['predicted_bbox'] is None
    assert row['tracking']['requires_reselection']==(not cut)
    index=2 if cut else 18
    row=p.evaluate(logits(),4,index)
    assert row['roi'] is None
    assert row['tracking']['reason']==('scene_appearance_unconfirmed' if cut else 'target_reselection_required')

def test_crouching_changes_mask_shape_without_joint_identity_input():
    p=tracker();p.evaluate(logits(30,20,40,100),4,0)
    row=p.evaluate(logits(15,60,70,50),4,1)
    assert row['roi'] is not None and row['motion']['observation_kind']=='mask_region'

def test_guard_requires_consecutive_frames():
    with pytest.raises(ValueError):tracker().evaluate(logits(),4,1)

def test_same_visual_region_reconnects_after_cut_without_old_velocity():
    p=tracker();frame=np.zeros((160,320,3),np.uint8);frame[:]=(50,80,180)
    p.evaluate(logits(),4,0,frame=frame)
    pending=p.evaluate(logits(180),4,1,scene_cut=True,frame=frame)
    assert pending['roi'] is None and pending['motion']['predicted_bbox'] is None
    row=p.evaluate(logits(182),4,2,frame=frame)
    assert row['roi'] is not None and row['tracking_segment']==1
    assert row['motion']['predicted_center'] is None and not row['motion']['identity_verified']

def test_different_visual_region_after_cut_is_not_location_reconnected():
    p=tracker();frame=np.zeros((160,320,3),np.uint8);frame[:]=(0,0,255)
    p.evaluate(logits(),4,0,frame=frame);frame[:]=(255,0,0)
    for i in range(1,4):
        row=p.evaluate(logits(),4,i,scene_cut=i==1,frame=frame)
        assert row['roi'] is None and row['tracking']['reason']=='scene_appearance_unconfirmed'

def test_unconfirmed_cut_times_out():
    p=tracker();p.evaluate(logits(),4,0)
    for i in range(1,18):row=p.evaluate(logits(),4,i,scene_cut=i==1)
    assert row['tracking']['requires_reselection'] and row['roi'] is None
