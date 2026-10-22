from copy import deepcopy
import json
import numpy as np
import pytest

from core.pose3d.completion import complete,leg_ik


def inputs():
    frames=[];tracking=[]
    for i in range(30):
        points=[{'x':0.,'y':0.,'z':0.,'valid':True} for _ in range(33)]
        for hip,knee,ankle,x in [(23,25,27,-.2),(24,26,28,.2)]:
            for j,y,z in [(hip,0,0),(knee,.4,.1),(ankle,.8,0)]:points[j].update(x=x,y=y,z=z)
        for shoulder,elbow,wrist,x in [(11,13,15,-.2),(12,14,16,.2)]:
            for j,y in [(shoulder,-.5),(elbow,-.2),(wrist,.1)]:points[j].update(x=x,y=y)
        frames.append({'frame_index':i,'timestamp':i/30,'person_bbox':[0,0,100,200],'landmarks':points})
        tracking.append({'frame_index':i,'tracking':{'state':'tracked'}})
    return {'frames':frames,'video':{'fps':30},'joint_names':list(range(33)),
            'coordinates':'mediapipe_native_world_xyz'}, {'frames':tracking}


def test_short_gap_uses_endpoints_and_fixed_length_without_mutating_raw():
    raw,tr=inputs()
    for i in (10,11,12):raw['frames'][i]['landmarks'][27]['valid']=False
    before=json.dumps(raw)
    out=complete(raw,tr)
    assert json.dumps(raw)==before
    for i in (10,11,12):
        p=out['frames'][i]['joints'];assert p[27]['source']=='interpolated'
        assert np.linalg.norm(np.subtract(p[27]['xyz'],p[25]['xyz']))==pytest.approx(out['lengths']['25-27'])


def test_long_leg_gap_is_explicit_ik_estimate_not_observation():
    raw,tr=inputs()
    for i in range(10,22):
        for j in (25,27):raw['frames'][i]['landmarks'][j]['valid']=False
    out=complete(raw,tr);p=out['frames'][15]['joints']
    assert p[25]['source']==p[27]['source']=='estimated_leg_ik'
    assert np.linalg.norm(np.subtract(p[25]['xyz'],p[23]['xyz']))==pytest.approx(out['lengths']['23-25'])
    assert np.linalg.norm(np.subtract(p[27]['xyz'],p[25]['xyz']))==pytest.approx(out['lengths']['25-27'])


def test_lost_target_never_filled_or_interpolated_across():
    raw,tr=inputs();tr['frames'][11]['tracking']['state']='lost'
    for i in (10,11,12):raw['frames'][i]['landmarks'][15]['valid']=False
    out=complete(raw,tr)
    assert all(p['xyz'] is None for p in out['frames'][11]['joints'])
    assert out['frames'][10]['joints'][15]['xyz'] is None


def test_wrong_length_is_suspect_before_interpolation():
    raw,tr=inputs();raw['frames'][12]['landmarks'][15]['x']=5.
    out=complete(raw,tr);p=out['frames'][12]['joints'][15]
    assert p['suspect'] and p['source']=='interpolated'
    assert abs(p['xyz'][0])<1


def test_ik_unreachable_target_is_clamped_to_bone_lengths():
    k,a=leg_ik(np.zeros(3),np.array([0.,10.,0.]),np.array([0.,0.,1.]),.4,.5)
    assert np.linalg.norm(k)==pytest.approx(.4)
    assert np.linalg.norm(a-k)==pytest.approx(.5)


def test_completion_cancel_and_alignment_guard():
    raw,tr=inputs()
    with pytest.raises(KeyboardInterrupt):complete(raw,tr,lambda:True)
    tr['frames'][2]['frame_index']=9
    with pytest.raises(ValueError):complete(raw,tr)


def test_repaired_parent_with_observed_child_keeps_both_bone_lengths():
    raw,tr=inputs();raw['frames'][12]['landmarks'][13]['valid']=False
    out=complete(raw,tr);p=out['frames'][12]['joints']
    for a,b in ((11,13),(13,15)):
        assert np.linalg.norm(np.subtract(p[b]['xyz'],p[a]['xyz']))==pytest.approx(out['lengths'][f'{a}-{b}'])
