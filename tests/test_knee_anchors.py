import numpy as np
import pytest
from validation.sam2.knee_anchors import validate_anchors,knee_target_at
from validation.sam2.shoe_leg_geometry import project,solve_leg

def data(rows):return {'schema':'manual_knees_v1','source_sha256':'abc','anchors':rows}
def row(frame=58,joint=11,xy=None):return {'frame':frame,'joint':joint,'xy':xy or [100,200]}

def test_source_binding():
    with pytest.raises(ValueError):validate_anchors(data([row()]),'other',720,1280,218)

@pytest.mark.parametrize('r',[row(-1),row(218),row(joint=13),row(xy=[720,20]),row(xy=[float('nan'),20])])
def test_bad_input_rejected(r):
    with pytest.raises(ValueError):validate_anchors(data([r]),'abc',720,1280,218)

def test_duplicate_rejected():
    with pytest.raises(ValueError):validate_anchors(data([row(),row()]),'abc',720,1280,218)

def test_manual_and_interpolated_have_distinct_provenance():
    a=validate_anchors(data([row(50,xy=[100,200]),row(60,xy=[200,300])]),'abc',720,1280,218)
    assert knee_target_at(a,50,11)[1]=='manual'
    p,kind=knee_target_at(a,55,11);np.testing.assert_array_equal(p,[150,250]);assert kind=='interpolated_2d'
    assert knee_target_at(a,49,11)[0] is None and knee_target_at(a,55,12)[0] is None

def test_long_gap_not_interpolated():
    a={0:{11:np.zeros(2)},30:{11:np.ones(2)}}
    assert knee_target_at(a,15,11)[0] is None

def test_knee_observation_changes_bend_without_stretching_bones():
    cam={'focal':1200.,'translation':[0,0,4.],'center':[360.,640.]}
    h=np.zeros(3);a=np.array([0,.6,0]);desired=np.array([.264575131,.3,0]);wrong=np.array([-.264575131,.3,0])
    target=project(a[None],cam)[0];knee=project(desired[None],cam)[0]
    plain=solve_leg(h,wrong,a,target,cam,.4,.4,wrong,a)
    guided=solve_leg(h,wrong,a,target,cam,.4,.4,wrong,a,knee_target=knee)
    assert guided['knee_error_pixels']<5
    assert np.linalg.norm(project(plain['knee'][None],cam)[0]-knee)>50
    assert np.linalg.norm(guided['knee']-h)==pytest.approx(.4)
    assert np.linalg.norm(guided['ankle']-guided['knee'])==pytest.approx(.4)
