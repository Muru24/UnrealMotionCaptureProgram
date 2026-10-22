from dataclasses import replace
import json

import numpy as np
import pytest

from core.pose2d.interface import Pose2DResult
from core.pose3d.interface import Landmark3D, Pose3DResult
from core.pose3d.guidance import JointGuide, validate_anchors


def pose(wrist=(140,180), visible=True, shift=0):
    points=[Landmark3D(0,0,0,100.,200.,0,.9,.9,True,'valid') for _ in range(33)]
    for i, xy in {11:(80,100),12:(120,100),23:(80,200),24:(120,200),
                  13:(130,140),15:wrist,14:(70,140),16:(60,180),
                  25:(80,260),26:(120,260),27:(80,320),28:(120,320)}.items():
        points[i]=replace(points[i],image_x=float(xy[0]+shift),image_y=float(xy[1]))
    points[15]=replace(points[15],valid=visible)
    return Pose3DResult(Pose2DResult((40,50,180,340),(),1),tuple(points))


def guide(anchors=None):
    return JointGuide(anchors or {},500,500,30,100)


@pytest.mark.parametrize('anchors', [
    {0:{'pelvis':[100,200]}}, {100:{'left_wrist':[1,2]}},
    {0:{'left_wrist':[float('nan'),2]}}, {0:{'left_wrist':[-1,2]}},
    {0:{'unknown':[1,2]}}, {0:{'pelvis':[100,200],'chest':[100,201]}},
])
def test_invalid_user_anchor_rejected(anchors):
    with pytest.raises(ValueError):validate_anchors(anchors,500,500,100)


def test_manual_overrides_image_only_and_raw_stays_intact():
    g=guide({0:{'left_wrist':[150,180]}});p=pose()
    before=json.dumps(p.to_dict())
    r=g.process(p,0)['joints']['left_wrist']
    assert r['state']=='manual' and r['xy']==[150,180]
    assert json.dumps(p.to_dict())==before


def test_prediction_expires_and_does_not_update_last_observation():
    g=guide();g.process(pose(),0)
    assert g.process(pose(visible=False),3)['joints']['left_wrist']['state']=='predicted'
    assert g.history['left_wrist']['time']==0
    assert g.process(pose(visible=False),7)['joints']['left_wrist']['state']=='uncertain'


def test_outlier_never_poison_anchor():
    g=guide();g.process(pose(),0)
    r=g.process(pose(wrist=(450,50)),1)['joints']['left_wrist']
    assert r['state']=='predicted' and r['reason']=='outlier_rejected'
    assert g.history['left_wrist']['time']==0


def test_two_observations_required_for_reconnect():
    g=guide();g.process(pose(),0);g.process(pose(visible=False),1)
    assert g.process(pose(),2)['joints']['left_wrist']['state']=='predicted'
    assert g.process(pose(),3)['joints']['left_wrist']['state']=='reacquired'


def test_body_translation_is_not_a_limb_outlier():
    g=guide();g.process(pose(),0)
    assert g.process(pose(shift=70),1)['joints']['left_wrist']['state']=='observed'


def test_no_prediction_across_identity_loss():
    g=guide();g.process(pose(),0)
    lost=replace(pose(),pose2d=Pose2DResult(None,(),0))
    r=g.process(lost,1)
    assert all(p['xy'] is None for p in r['joints'].values())


def test_torso_reselection_refuses_two_people():
    g=guide({0:{'pelvis':[100,200],'chest':[100,100]}})
    c=(np.array([40,50,180,340]),pose().landmarks)
    kept,reselect=g.candidates([c],0)
    assert len(kept)==1 and reselect
    kept,reselect=g.candidates([c,c],0)
    assert not kept and not reselect


def test_confident_model_snap_back_cannot_replace_manual_anchor():
    g=guide({0:{'left_wrist':[140,180]}})
    g.process(pose(),0)
    r=g.process(pose(wrist=(205,180)),1)['joints']['left_wrist']
    assert r['reason']=='outlier_rejected'
    assert g.history['left_wrist']['manual']


def test_torso_loss_requires_two_new_observations():
    g=guide();g.process(pose(),0)
    lost=replace(pose(),pose2d=Pose2DResult(None,(),0))
    g.process(lost,1)
    assert g.process(pose(),2)['joints']['left_wrist']['state']=='predicted'
    assert g.process(pose(),3)['joints']['left_wrist']['state']=='reacquired'


def test_automatic_unreliable_torso_does_not_latch_identity():
    g=guide();g.process(pose(),0)
    c=(np.array([40,50,180,340]),pose(shift=300).landmarks)
    kept,reselect=g.candidates([c],1)
    assert kept==[c] and not reselect


def test_manual_image_track_overrides_wrong_confident_model():
    import cv2
    rng=np.random.default_rng(2)
    image=np.zeros((500,500,3),np.uint8)
    image[160:200,120:160]=rng.integers(0,255,(40,40,3),dtype=np.uint8)
    g=guide({0:{'left_wrist':[140,180]}})
    g.process(pose(),0,frame=image)
    moved=cv2.warpAffine(image,np.float32([[1,0,5],[0,1,3]]),(500,500))
    p=g.process(pose(wrist=(450,50)),1,frame=moved)['joints']['left_wrist']
    assert p['state']=='image_tracked'
    assert np.linalg.norm(np.array(p['xy'])-[145,183])<.5


def test_failed_manual_image_track_never_jumps_to_far_model_joint():
    image=np.zeros((500,500,3),np.uint8)
    g=guide({0:{'left_wrist':[140,180]}})
    g.process(pose(),0,frame=image)
    p=g.process(pose(wrist=(450,50)),1,frame=image)['joints']['left_wrist']
    assert p['state']=='predicted' and p['xy']==[140,180]
