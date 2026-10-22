import numpy as np
import pytest
from core.pose2d.association import skeleton_similarity,tracking_score,collapse_same_skeleton
from core.pose2d.tracker import TargetTracker


def body():
    return np.array([[60,20],[55,18],[65,18],[50,20],[70,20],
                     [40,50],[80,50],[25,80],[95,80],[20,110],[100,110],
                     [45,100],[75,100],[45,140],[75,140],[45,180],[75,180]],dtype=float)


def test_skeleton_similarity_ignores_translation_and_scale():
    p=body();s=np.ones(17)
    assert skeleton_similarity((p,s),(p*2+[100,50],s))==pytest.approx(1.)


def test_bad_confidence_and_extreme_bone_do_not_become_identity_evidence():
    p=body();q=p.copy();q[9]=[10000,-10000];s=np.ones(17);bad=s.copy();bad[10]=np.inf
    assert skeleton_similarity((p,s),(q,bad))==pytest.approx(1.)
    bad[:]=0;bad[:5]=1
    assert skeleton_similarity((p,s),(q,bad)) is None
    score,components,weights=tracking_score(.8,.325,None,.7)
    assert 'skeleton' not in weights and sum(weights.values())==pytest.approx(1)
    assert 0<=score<=1 and components['skeleton'] is None


def test_user_weights_use_center_similarity_not_raw_distance():
    score,components,weights=tracking_score(.8,.325,.9,.7)
    assert score==pytest.approx(.735)
    assert weights=={'iou':.25,'center':.25,'skeleton':.3,'appearance':.2}
    assert components['center']==pytest.approx(.5)


def test_duplicate_requires_coincident_image_joints_not_merely_similar_pose():
    p=body();boxes=np.array([[0,0,120,195],[5,0,115,190]],dtype=float)
    coords=np.stack([p,p]);scores=np.ones((2,17))
    b,k,removed=collapse_same_skeleton(boxes,(coords,scores))
    assert len(b)==1 and len(removed)==1
    coords[1]+=40
    b,k,removed=collapse_same_skeleton(boxes,(coords,scores))
    assert len(b)==2 and not removed


def test_ambiguous_candidate_does_not_update_skeleton_reference():
    t=TargetTracker(target_index=0,multi_cue=True)
    frame=np.full((200,300,3),(0,0,200),np.uint8);p=body();scores=np.ones((1,17))
    t.select(frame,np.array([[0,0,120,195]],dtype=float),(p[None],scores))
    before=t.skeleton[0].copy()
    d=t.select(frame,np.array([[1,0,121,195],[0,0,119,195]],dtype=float),
               (np.stack([p+1,p-1]),np.ones((2,17))))
    assert d.bbox is None and d.info.requires_reselection
    assert np.array_equal(t.skeleton[0],before)


def test_low_iou_fast_motion_can_match_only_with_strong_body_and_appearance():
    frame=np.full((220,400,3),(0,0,200),np.uint8);p=body();s=np.ones((1,17))
    old=np.array([[0,0,120,195]],dtype=float);moved=old+[125,0,125,0]
    legacy=TargetTracker(target_index=0);legacy.select(frame,old)
    assert legacy.select(frame,moved).bbox is None
    tracker=TargetTracker(target_index=0,multi_cue=True)
    tracker.select(frame,old,(p[None],s))
    decision=tracker.select(frame,moved,((p+np.array([125,0]))[None],s))
    assert decision.bbox is not None and decision.info.track_id==1
    assert tracker.association_diagnostics[0]['components']['iou']==0
