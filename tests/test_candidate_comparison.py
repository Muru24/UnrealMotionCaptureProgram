import numpy as np
import pytest
from validation.sam2.candidate_geometry import mirror_indices,restore_flip,flip_roi
from validation.sam2.candidate_ranking import rank_candidates,BONES


def test_flip_roundtrip_restores_joint_identity_pixels_and_camera_x_without_mutation():
    names=['nose','left-wrist','right-wrist','left-heel','right-heel','neck']
    rng=np.random.default_rng(4);p=rng.random((6,2))*100;q=rng.normal(size=(6,3));a=p.copy();b=q.copy()
    flipped_p,flipped_q=restore_flip(p,q,names,720)
    restored_p,restored_q=restore_flip(flipped_p,flipped_q,names,720)
    np.testing.assert_allclose(restored_p,p);np.testing.assert_allclose(restored_q,q)
    np.testing.assert_array_equal(p,a);np.testing.assert_array_equal(q,b)
    assert flipped_p[1,0]==pytest.approx(719-p[2,0])
    assert flipped_q[1,0]==-q[2,0] and flipped_q[1,2]==q[2,2]
    assert flip_roi(flip_roi([10,20,600,900],720),720)==[10,20,600,900]


@pytest.mark.parametrize('names',[['left-wrist'],['nose','nose']])
def test_invalid_joint_mapping_is_rejected(names):
    with pytest.raises(ValueError):mirror_indices(names)


def test_joint_dimensions_are_checked():
    with pytest.raises(ValueError):restore_flip(np.zeros((1,3)),np.zeros((1,3)),['nose'],720)


def fixture():
    rng=np.random.default_rng(5);pose=rng.normal(size=(70,3))*.1
    xyz=np.tile(pose,(6,2,1,1));pixels=xyz[:,:,:,:2]*100+200
    refs=np.array([np.linalg.norm(pose[b]-pose[a]) for a,b in BONES])
    return xyz,pixels,refs


def test_identical_candidates_do_not_switch_and_translation_does_not_change_motion_ranking():
    xyz,pixels,refs=fixture();original=xyz.copy()
    result=rank_candidates(xyz,pixels,refs,np.ones(6)*500,.4)
    assert result['path']==[0]*6
    xyz+=np.arange(6)[:,None,None,None]
    translated=rank_candidates(xyz,pixels,refs,np.ones(6)*500,.4)
    np.testing.assert_allclose(translated['fixed_sequence_costs'],result['fixed_sequence_costs'],atol=1e-12)
    assert np.isfinite(original).all()


def test_one_bad_candidate_is_not_favored_by_length_or_transition_costs():
    xyz,pixels,refs=fixture();xyz[:,1,62]*=8
    result=rank_candidates(xyz,pixels,refs,np.ones(6)*500,.4)
    assert result['path']==[0]*6 and result['fixed_sequence_costs'][0]<result['fixed_sequence_costs'][1]


@pytest.mark.parametrize('kind',['nonfinite','dimensions','scale','diagonal'])
def test_invalid_ranking_input_is_rejected(kind):
    xyz,pixels,refs=fixture();scale=.4;diagonal=np.ones(6)*500
    if kind=='nonfinite':xyz[0,0,0,0]=np.nan
    if kind=='dimensions':pixels=pixels[:,:,:,:1]
    if kind=='scale':scale=0
    if kind=='diagonal':diagonal[0]=0
    with pytest.raises(ValueError):rank_candidates(xyz,pixels,refs,diagonal,scale)
