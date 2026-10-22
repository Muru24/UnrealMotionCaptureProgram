import numpy as np
import pytest
from validation.sam2.temporal_leg_path import interpolate_references,select_path


def skeletons(n):
    q=np.zeros((n,70,3));q[:,5]=[-.2,0,0];q[:,6]=[.2,0,0]
    q[:,9]=[-.1,.5,0];q[:,10]=[.1,.5,0]
    q[:,11]=[-.1,.8,.1];q[:,12]=[.1,.8,.1];q[:,13]=[-.1,1.1,0];q[:,14]=[.1,1.1,0]
    return q


def test_interpolates_supported_endpoints_only():
    q=skeletons(6);q[4,11,2]=.3;t=np.zeros((6,2),bool);t[[1,4],0]=True
    ref=interpolate_references(q,t)
    assert np.isnan(ref[0]).all() and np.isnan(ref[5]).all()
    assert np.isnan(ref[:,1]).all()
    np.testing.assert_allclose(ref[2,0],ref[1,0]*2/3+ref[4,0]/3)


def test_long_gap_remains_unknown():
    t=np.zeros((20,2),bool);t[[0,19],0]=True
    assert np.isnan(interpolate_references(skeletons(20),t)).all()


def test_path_avoids_one_frame_named_leg_jump():
    a=np.zeros((2,2,3));a[:,:,1]=.5;b=a.copy();b[0,:,0]=2
    path=select_path([[a],[a,b],[a]],[[0],[.1,0],[0]])
    assert path==[0,0,0]


def test_coherent_evidence_can_outweigh_transition_cost():
    a=np.zeros((2,2,3));a[:,:,1]=.5;b=a.copy();b[:,:,0]=.02
    assert select_path([[a],[a,b],[b]],[[0],[3,0],[0]])==[0,1,0]


def test_rigid_world_motion_does_not_change_local_reference():
    q=skeletons(4);t=np.ones((4,2),bool);before=interpolate_references(q,t)
    rotation=np.array([[0,0,1],[0,1,0],[-1,0,0]])
    after=interpolate_references(q@rotation.T+[5,6,7],t)
    np.testing.assert_allclose(before,after,atol=1e-12)


def test_invalid_trust_shape_rejected():
    with pytest.raises(ValueError):interpolate_references(skeletons(3),np.zeros((3,3)))


def test_nonfinite_cost_rejected():
    a=np.zeros((2,2,3))
    with pytest.raises(ValueError):select_path([[a]],[[np.nan]])
