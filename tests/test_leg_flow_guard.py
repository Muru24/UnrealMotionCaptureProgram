import cv2
import numpy as np
import pytest
from validation.sam2.leg_flow_guard import track_leg_points,transition_evidence
from validation.sam2.candidate_ranking import rank_candidates,BONES


def test_textured_translation_supports_joint_motion():
    rng=np.random.default_rng(22);before=rng.integers(0,256,(160,160),dtype=np.uint8)
    after=cv2.warpAffine(before,np.float32([[1,0,5],[0,1,3]]),(160,160))
    points=np.array([[[45,45],[100,45],[45,100],[100,100]]],float)
    predicted,support=track_leg_points(before,after,points)
    assert (support>=3).all()
    np.testing.assert_allclose(predicted,points+[5,3],atol=1.)


def test_featureless_region_is_unknown():
    image=np.zeros((160,160),np.uint8);points=np.ones((1,4,2))*70
    predicted,support=track_leg_points(image,image,points)
    assert not support.any() and np.isnan(predicted).all()
    cost,residual,suspect=transition_evidence(predicted,support,points,80)
    assert not cost.any() and np.isnan(residual).all() and not suspect.any()


def test_supported_displacement_has_cost_and_review_flag():
    p=np.ones((2,4,2))*70;s=np.ones((2,4),int)*5;current=p.copy();current[1,:,0]+=100
    cost,residual,suspect=transition_evidence(p,s,current,80)
    assert cost[0,1]>cost[0,0] and suspect[0,1].all()


@pytest.mark.parametrize('kind',['extra_shape','extra_nan','extra_negative','empty_allowed'])
def test_invalid_candidate_constraints(kind):
    rng=np.random.default_rng(2);xyz=np.tile(rng.normal(size=(70,3)),(3,2,1,1));pixels=xyz[:,:,:,:2]
    refs=np.array([np.linalg.norm(xyz[0,0,b]-xyz[0,0,a]) for a,b in BONES]);kwargs={}
    if kind=='extra_shape':kwargs['extra_transition_cost']=np.zeros((2,2))
    if kind=='extra_nan':kwargs['extra_transition_cost']=np.full((3,2,2),np.nan)
    if kind=='extra_negative':kwargs['extra_transition_cost']=-np.ones((3,2,2))
    if kind=='empty_allowed':kwargs['allowed_candidates']=np.zeros((3,2),bool)
    with pytest.raises(ValueError):rank_candidates(xyz,pixels,refs,np.ones(3)*100,1,**kwargs)


def test_candidate_restrictions_are_obeyed():
    rng=np.random.default_rng(2);xyz=np.tile(rng.normal(size=(70,3)),(3,2,1,1));pixels=xyz[:,:,:,:2]
    refs=np.array([np.linalg.norm(xyz[0,0,b]-xyz[0,0,a]) for a,b in BONES])
    result=rank_candidates(xyz,pixels,refs,np.ones(3)*100,1,allowed_candidates=[[False,True]]*3)
    assert result['path']==[1,1,1]


def test_duplicate_shoe_masks_do_not_prove_two_visible_legs():
    from validation.sam2.boot_evidence import shoe_support
    mask=np.zeros((100,100),bool);mask[10:25,10:25]=True
    evidence=shoe_support([mask,mask.copy()],[[15,15],[85,85]])
    assert evidence['regions']==1 and evidence['status']=='one_region_other_leg_unknown'
    assert not evidence['disagrees'] and not evidence['left_right_identity_verified']


def test_two_visible_shoes_require_two_different_ankle_matches():
    from validation.sam2.boot_evidence import shoe_support
    a=np.zeros((100,100),bool);b=a.copy();a[10:25,10:25]=True;b[70:85,70:85]=True
    assert not shoe_support([a,b],[[75,75],[15,15]])['disagrees']
    assert shoe_support([a,b],[[15,15],[15,15]])['disagrees']


def test_absent_shoe_evidence_is_unknown():
    from validation.sam2.boot_evidence import shoe_support
    result=shoe_support([],[[15,15],[75,75]])
    assert result['status']=='unknown' and result['error_pixels'] is None and not result['disagrees']
