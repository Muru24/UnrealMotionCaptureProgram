import numpy as np
import pytest
from core.pose3d.leg_estimation import propose
from core.pose3d.manual_leg_geometry import project

def sample():
    q=np.random.default_rng(4).uniform(-.05,.05,(70,3))
    q[5]=[-.2,-.4,0];q[6]=[.2,-.4,0];q[9]=[-.1,0,0];q[10]=[.1,0,0]
    q[11]=[-.3,.3,0];q[12]=[.3,.3,0];q[13]=[-.1,.6,0];q[14]=[.1,.6,0]
    cam={'focal':600.,'translation':[0,-.1,4.],'center':[160.,120.]};p=project(q,cam)
    mask=np.zeros((240,320),bool);x,y=p[13].round().astype(int);mask[y-5:y+6,x-5:x+6]=True
    lengths={a:[np.linalg.norm(q[k]-q[h]),np.linalg.norm(q[a]-q[k])] for h,k,a in ((9,11,13),(10,12,14))}
    return q,p,mask,lengths

def test_no_shoe_observation_is_unknown():
    q,p,mask,lengths=sample();options,failures=propose(q,p,q,p,[],lengths,320,240)
    assert not options and failures[0]['reason']=='no_shoe_observation'

def test_unsupported_model_ankles_are_rejected():
    q,p,mask,lengths=sample();cp=p.copy();cp[[13,14]]=[0,0]
    options,failures=propose(q,p,q,cp,[mask],lengths,320,240)
    assert not options and all(f['reason']=='alternative_ankle_outside_shoe' for f in failures)

def test_visible_leg_preserves_upper_body_other_leg_and_lengths():
    q,p,mask,lengths=sample();before=q.copy();options,_=propose(q,p,q,p,[mask],lengths,320,240)
    assert options
    for o in options:
        np.testing.assert_array_equal(o['world_joints'][[5,6,7,8,9,10,12,14,18,19,20]],q[[5,6,7,8,9,10,12,14,18,19,20]])
        a=o['legs'][0]['ankle'];assert a==13
        result=o['world_joints'];np.testing.assert_allclose([np.linalg.norm(result[11]-q[9]),np.linalg.norm(result[13]-result[11])],lengths[13],atol=1e-6)
    np.testing.assert_array_equal(q,before)

def test_unreachable_shoe_does_not_stretch_leg():
    q,p,mask,lengths=sample();mask[:]=False;mask[:12,:12]=True;cp=p.copy();cp[[13,14]]=[5,5]
    options,failures=propose(q,p,q,cp,[mask],lengths,320,240)
    assert not options and all('unreachable_shoe_ray' in f['reason'] for f in failures)
