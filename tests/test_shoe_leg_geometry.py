import numpy as np
import pytest
from validation.sam2.shoe_leg_geometry import fit_camera, project, body_basis, anchor_in_mask, solve_leg


CAM={'focal':1200.,'translation':[.1,-.2,4.],'center':[360.,640.]}


def test_recovers_model_projection():
    q=np.random.default_rng(8).uniform(-.5,.5,(70,3))
    p=project(q,CAM); fitted=fit_camera(q,p,720,1280)
    np.testing.assert_allclose(project(q,fitted),p,atol=1e-8)
    np.testing.assert_allclose(fitted['translation'],CAM['translation'],atol=1e-8)


def test_degenerate_camera_rejected():
    with pytest.raises(ValueError):fit_camera(np.zeros((70,3)),np.zeros((70,2)),720,1280)


def test_nonfinite_camera_rejected():
    with pytest.raises(ValueError):fit_camera(np.full((70,3),np.nan),np.zeros((70,2)),720,1280)


def test_reachable_leg_preserves_lengths_and_projects_to_target():
    h=np.array([0.,0.,0.]);k=np.array([.2,.3,0.]);a=np.array([0.,.6,0.])
    original=np.stack([h,k,a]).copy();target=project(np.array([[.1,.65,0.]]),CAM)[0]
    result=solve_leg(h,k,a,target,CAM,.4,.4,k,a)
    assert result is not None
    assert np.linalg.norm(result['knee']-h)==pytest.approx(.4)
    assert np.linalg.norm(result['ankle']-result['knee'])==pytest.approx(.4)
    np.testing.assert_allclose(project(result['ankle'][None],CAM)[0],target,atol=.1)
    np.testing.assert_array_equal(np.stack([h,k,a]),original)
    assert result['ankle'][2]+4>.1
    u=h-result['knee'];v=result['ankle']-result['knee']
    angle=np.degrees(np.arccos(np.clip(np.dot(u,v)/(.4*.4),-1,1)))
    assert 10-1e-5<=angle<=175+1e-5


def test_unreachable_leg_not_forced():
    z=np.zeros(3)
    assert solve_leg(z,z,z,np.array([10000.,10000.]),CAM,.4,.4,z,z) is None


def test_invalid_bone_length_rejected():
    z=np.zeros(3)
    with pytest.raises(ValueError):solve_leg(z,z,z,np.zeros(2),CAM,0.,.4,z,z)


def test_body_basis_orthonormal_and_degeneracy():
    q=np.zeros((70,3));q[5]=[-.2,0,0];q[6]=[.2,0,0];q[9]=[-.1,.5,0];q[10]=[.1,.5,0]
    basis=body_basis(q);np.testing.assert_allclose(basis.T@basis,np.eye(3),atol=1e-10)
    assert np.linalg.det(basis)==pytest.approx(1.)
    with pytest.raises(ValueError):body_basis(np.zeros((70,3)))


def test_anchor_is_inside_observed_mask_and_empty_rejected():
    mask=np.zeros((100,100),np.uint8);mask[30:80,40:60]=1
    anchor=anchor_in_mask(mask,[50,10],.4)
    assert mask[int(anchor[1]),int(anchor[0])]
    with pytest.raises(ValueError):anchor_in_mask(np.zeros_like(mask),[50,10],.4)
