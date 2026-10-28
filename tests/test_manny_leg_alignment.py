"""Geometry tests for actual hinge alignment, not editor API mocks."""
import math
import pytest
from tools.manny_leg_alignment import HingeAlignment,axis_rotation,rotate,transport,dot,length,sub
from tools.manny_leg_alignment import offline_hinge_rotations,bounded_phase


def test_corrects_drifting_input_roll_instead_of_chasing_correction_angle():
    solver=HingeAlignment((1,0,0),30)
    axis=(0,0,-1);normal=(1,0,0)
    for i in range(90):
        source=axis_rotation(axis,math.radians(i*5))
        q,step=solver.solve(source,axis,normal,math.radians(40))
        assert dot(rotate(q,(1,0,0)),normal)>.999
        assert abs(step)<=math.radians(12)+1e-9


def test_straight_knee_does_not_follow_random_input_twist():
    solver=HingeAlignment((1,0,0),30)
    q,_=solver.solve((0,0,0,1),(0,0,-1),(1,0,0),math.radians(40))
    for i in range(1,50):
        q,_=solver.solve(axis_rotation((0,0,-1),i*.3),(0,0,-1),None,0)
        assert dot(rotate(q,(1,0,0)),(1,0,0))>.999


@pytest.mark.parametrize('axis',[(1,0,0),(0,1,0),(0,0,1)])
def test_fast_swing_is_preserved(axis):
    q=transport((0,0,0,1),(0,0,-1),axis)
    assert length(sub(rotate(q,(0,0,-1)),axis))<1e-6


def test_missing_evidence_reset_does_not_carry_old_rotation():
    solver=HingeAlignment((1,0,0),30)
    solver.solve(axis_rotation((0,0,-1),1),(0,0,-1),None,0)
    solver.reset()
    q,_=solver.solve((0,0,0,1),(0,0,-1),None,0)
    assert q==(0.,0.,0.,1.)


def test_reacquired_plane_has_bounded_axial_turn():
    solver=HingeAlignment((1,0,0),60)
    solver.solve((0,0,0,1),(0,0,-1),None,0)
    q,step=solver.solve((0,0,0,1),(0,0,-1),(-1,0,0),math.radians(40))
    assert abs(step)<=math.radians(6)+1e-9
    assert abs(dot(q,q)-1)<1e-9


def hinge_rows():
    rows=[]
    for i in range(61):
        bend=math.radians(30) if i<=20 or i>=40 else 0.
        phase=0. if i<=20 else math.pi/2
        lower=rotate(axis_rotation((0,0,1),phase),(0,math.sin(bend),-math.cos(bend)))
        rows.append({'thigh':{'p':(0,0,0),'q':(0,0,0,1)},
                     'calf':{'p':(0,0,-1),'q':(0,0,0,1)},
                     'foot':{'p':(lower[0],lower[1],-1+lower[2]),'q':(0,0,0,1)}})
    return rows


def test_offline_plans_turn_inside_straight_interval_without_lag():
    rows=hinge_rows()
    q=offline_hinge_rotations(rows,(1,0,0),'thigh','calf',['thigh','calf','foot'],30)
    middle=rotate(q[30],(1,0,0))
    assert middle[0]>.5 and middle[1]>.5
    assert dot(rotate(q[40],(1,0,0)),(0,1,0))>.99
    assert rows[30]['thigh']['q']==(0,0,0,1)


def test_phase_projection_bounds_fast_turn_and_anticipates_it():
    result=bounded_phase([0.]*15+[math.pi]*15,math.radians(18))
    assert max(abs(b-a) for a,b in zip(result,result[1:]))<math.radians(18)+1e-7
    assert result[14]>0 and result[15]<math.pi


def test_offline_does_not_bridge_degenerate_geometry():
    rows=hinge_rows();rows[30]['calf']['p']=(0,0,0)
    q=offline_hinge_rotations(rows,(1,0,0),'thigh','calf',['thigh','calf','foot'],30)
    assert dot(rotate(q[29],(1,0,0)),(1,0,0))>.99
    assert q[30]==(0,0,0,1)
