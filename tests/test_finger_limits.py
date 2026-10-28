import math,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from finger_limits import constrain,guard_rotation
from manny_leg_alignment import transport,rotate,axis_rotation,dot

Y=(0,1,0);CURL=(0,0,-1)

def pose(flex,spread=0):
 f,a=map(math.radians,[flex,spread]);d=(math.sin(a),math.cos(f)*math.cos(a),-math.sin(f)*math.cos(a))
 return transport((0,0,0,1),Y,d)

def angles(q):
 x,y,z=rotate(q,Y);return math.degrees(math.atan2(-z,y)),math.degrees(math.atan2(x,math.hypot(y,z)))

def test_normal_rotation_and_antipodal_quaternion_are_unchanged():
 q=pose(45,5)
 for value in [q,tuple(-x for x in q)]:
  out,reasons=constrain(value,CURL,2)
  assert abs(dot(out,q))==pytest.approx(1) and reasons==[]


def test_distal_hyperextension_and_sideways_bend_are_bounded():
 out,reasons=constrain(pose(-45,40),CURL,3)
 flex,spread=angles(out)
 assert flex==pytest.approx(-10) and spread==pytest.approx(10)
 assert set(reasons)=={'flexion_range','sideways_range'}
 out,_=constrain(pose(150),CURL,2);assert angles(out)[0]==pytest.approx(110)


def test_thumb_keeps_opposition_and_handles_antiparallel_axis():
 q=pose(70,35);out,reasons=constrain(q,CURL,1,True)
 assert abs(dot(q,out))==pytest.approx(1) and reasons==[]
 out,reasons=constrain(axis_rotation((1,0,0),math.pi),CURL,1,True)
 assert math.degrees(math.acos(dot(rotate(out,Y),Y)))==pytest.approx(115)
 assert reasons==['thumb_swing_cone']


def test_one_frame_impulse_is_limited_but_finger_can_close_quickly():
 previous=(0,0,0,1);goal=pose(90);out,reasons=guard_rotation(goal,CURL,2,30,previous)
 assert math.degrees(2*math.acos(abs(dot(previous,out))))<=24+1e-8
 assert 'angular_speed' in reasons
 for _ in range(4):out,_=guard_rotation(goal,CURL,2,30,out)
 assert abs(dot(goal,out))==pytest.approx(1)


def test_rate_limit_tracks_time_and_scene_reset_does_not_inherit_previous():
 samples=[]
 for fps in [30,60]:
  q=(0,0,0,1);values=[]
  for _ in range(fps//5):q,_=guard_rotation(pose(90),CURL,2,fps,q);values.append(q)
  samples.append(values)
 for a,b in zip(samples[0],samples[1][1::2]):assert abs(dot(a,b))==pytest.approx(1,abs=1e-7)
 q,reasons=guard_rotation(pose(90),CURL,2,30,None)
 assert angles(q)[0]==pytest.approx(90) and 'angular_speed' not in reasons


def test_invalid_rotation_and_fps_are_rejected():
 with pytest.raises(ValueError):guard_rotation((float('nan'),0,0,1),CURL,2,30)
 with pytest.raises(ValueError):guard_rotation((0,0,0,0),CURL,2,30)
 with pytest.raises(ValueError):guard_rotation((0,0,0,1),CURL,2,0)

def test_intermediate_slerp_is_reprojected_to_finger_range():
    from finger_limits import slerp
    a,_=constrain(pose(0,12),CURL,2);b,_=constrain(pose(110,12),CURL,2)
    midpoint=slerp(a,b,.5)
    assert angles(midpoint)[1]>12
    bounded,reasons=guard_rotation(midpoint,CURL,2,120)
    assert abs(angles(bounded)[1])<=12+1e-8
    assert 'sideways_range' in reasons
