import numpy as np
import pytest
from core.pose2d.tracker import TargetTracker


def setup(enabled=True):
    frame=np.full((300,500,3),(0,0,200),np.uint8)
    box=np.array([[80,20,200,215]],float)
    p=np.array([[60,20],[55,18],[65,18],[50,20],[70,20],[40,50],[80,50],[25,80],[95,80],
                [20,110],[100,110],[45,100],[75,100],[45,140],[75,140],[45,180],[75,180]],float)+[80,20]
    scores=np.ones((1,17))
    t=TargetTracker(target_index=0,multi_cue=True,motion_fps=30,max_missing=2,long_reidentify=enabled)
    t.select(frame,box,(p[None],scores))
    for _ in range(3):t.select(frame,np.empty((0,4)))
    assert t.latched
    return t,frame,box,p,scores


def test_long_reidentify_confirms_three_observations_without_updating_frozen_reference():
    t,frame,box,p,s=setup();before=t.motion.x.copy();references=len(t.references.gallery)
    for _ in range(2):
        d=t.select(frame,box+[100,0,100,0],((p+[100,0])[None],s))
        assert d.bbox is None and np.array_equal(t.motion.x,before)
        assert len(t.references.gallery)==references and t.segment==0
    d=t.select(frame,box+[100,0,100,0],((p+[100,0])[None],s))
    assert d.info.track_id==1 and d.info.reason=='long_gap_reidentified'
    assert t.segment==1 and not t.latched and t.motion_diagnostics['filter_reset']
    assert t.motion.x[2:].tolist()==[0,0] and t.velocity.tolist()==[0,0]


@pytest.mark.parametrize('case',['disabled','ambiguous_history','wrong_appearance','no_pose','two_lookalikes','expired'])
def test_long_reidentify_does_not_accept_insufficient_identity_evidence(case):
    t,frame,box,p,s=setup(case!='disabled')
    if case=='ambiguous_history':t.gap_ambiguous=True
    if case=='wrong_appearance':frame[:]=(200,0,0)
    if case=='expired':t.missing=151
    boxes=box;pose=(p[None],s)
    if case=='no_pose':pose=None
    if case=='two_lookalikes':boxes=np.vstack((box,box+[140,0,140,0]));pose=(np.stack((p,p+[140,0])),np.ones((2,17)))
    for _ in range(4):assert t.select(frame,boxes,pose).bbox is None
    assert t.latched and t.segment==0 and len(t.references.gallery)==(0 if case=='disabled' else 1)


def test_missing_frame_interrupts_reidentification_confirmations():
    t,frame,box,p,s=setup()
    t.select(frame,box,(p[None],s));assert t.references.hits==1
    t.select(frame,np.empty((0,4)),(np.empty((0,17,2)),np.empty((0,17))))
    assert t.references.hits==0
    for _ in range(2):assert t.select(frame,box,(p[None],s)).bbox is None
