import math
import numpy as np
from core.motion.correction import smooth_small_rotation_changes
from core.motion.root_motion import smooth_small_root_changes


def quaternions(angles):
    return np.array([[math.cos(a/2),0,0,math.sin(a/2)] for a in angles])


def angle_error(a,b):
    return 2*np.arccos(np.clip(np.abs(np.sum(a*b,axis=1)),0,1))


def test_small_angular_noise_reduces_without_freezing_deliberate_rotation():
    t=np.arange(91)/30;clean=quaternions(t*.15)
    noisy=quaternions(t*.15+.012*(-1.)**np.arange(91))
    filtered=smooth_small_rotation_changes(noisy,30)
    assert np.mean(angle_error(filtered[2:-2],clean[2:-2]))<np.mean(angle_error(noisy[2:-2],clean[2:-2]))*.1
    np.testing.assert_allclose(smooth_small_rotation_changes(clean,30),clean,atol=1e-10)
    np.testing.assert_array_equal(filtered[[0,-1]],noisy[[0,-1]])


def test_fast_peak_is_not_shifted_or_flattened():
    t=np.arange(31)/30;angles=math.pi*.5*np.exp(-((t-.5)/.06)**2)
    values=quaternions(angles);filtered=smooth_small_rotation_changes(values,30)
    output=2*np.arccos(np.clip(filtered[:,0],-1,1))
    assert np.argmax(output)==np.argmax(angles)
    assert abs(output.max()-angles.max())<math.radians(.1)
    assert np.max(angle_error(filtered,values))<math.radians(2)


def test_shortest_arc_signs_and_frame_rates_remain_consistent():
    outputs=[]
    for fps in (30,60):
        t=np.arange(fps*3+1)/fps
        angles=np.radians(150+t*20+np.sin(t*2*math.pi*13))
        values=quaternions(angles);values[1::2]*=-1
        result=smooth_small_rotation_changes(values,fps)[::fps//30]
        outputs.append(result)
        assert np.max(np.abs(np.linalg.norm(result,axis=1)-1))<1e-10
    assert np.max(angle_error(outputs[0],outputs[1]))<1e-6


def test_small_root_noise_reduces_but_linear_movement_and_jump_height_are_preserved():
    t=np.arange(91)/30;clean=np.c_[t*.2,t*.1,np.sin(t)*.3]
    noisy=clean.copy();noisy[:,0]+=.003*(-1.)**np.arange(91)
    filtered=smooth_small_root_changes(noisy,30)
    assert np.std(filtered[2:-2,0]-clean[2:-2,0])<.0001
    np.testing.assert_array_equal(filtered[:,2],noisy[:,2])
    np.testing.assert_allclose(smooth_small_root_changes(clean,30),clean,atol=1e-12)


def test_large_root_reversal_is_not_rounded_or_overshot():
    values=np.zeros((31,3));values[15,0]=.2
    np.testing.assert_array_equal(smooth_small_root_changes(values,30),values)


def test_one_and_two_frame_spans_are_unchanged():
    for n in (1,2):
        q=quaternions(np.arange(n)*.05);p=np.c_[np.arange(n),np.zeros((n,2))]
        np.testing.assert_array_equal(smooth_small_rotation_changes(q,30),q)
        np.testing.assert_array_equal(smooth_small_root_changes(p,30),p)
