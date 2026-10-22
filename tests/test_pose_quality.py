from copy import deepcopy
import numpy as np
import pytest
from core.pose3d.quality import review_pose


def sample(n=30):
    frames=[]
    for i in range(n):
        points=[{'x':0.,'y':0.,'z':0.,'valid':True} for _ in range(70)]
        points[5].update(x=-.2,y=-.3)
        points[7].update(x=-.4,y=-.1)
        points[62].update(x=-.55,y=.1)
        frames.append({'frame_index':i,'person_bbox':[0,0,100,200],'tracking_segment':0,'landmarks':points})
    return {'frames':frames,'video':{'fps':30}}


def test_static_pose_has_no_flags_and_review_never_changes_observations():
    document=sample();before=deepcopy(document);result=review_pose(document)
    assert document==before and result['summary']['review_frames']==0


def test_extreme_bone_length_is_review_candidate_not_automatic_correction():
    document=sample();document['frames'][10]['landmarks'][7]['x']=-1.2
    before=deepcopy(document);result=review_pose(document)
    assert any(e['reason']=='length_outlier' and e['bone']==[5,7] and e['start']==10 for e in result['events'])
    assert document==before and result['meaning']=='review_candidates_not_confirmed_errors'


def test_isolated_direction_flip_is_flagged_even_with_constant_length():
    document=sample()
    document['frames'][10]['landmarks'][7].update(x=0.,y=-.5)
    result=review_pose(document)
    assert any(e['reason']=='isolated_direction_spike' and e['bone']==[5,7] for e in result['events'])


def test_smooth_fast_rotation_does_not_become_isolated_spike():
    document=sample()
    for i,frame in enumerate(document['frames']):
        theta=i*.4;offset=np.array([np.cos(theta),np.sin(theta)])*.3
        frame['landmarks'][7].update(x=-.2+offset[0],y=-.3+offset[1])
        frame['landmarks'][62].update(x=-.2+offset[0]*2,y=-.3+offset[1]*2)
    result=review_pose(document)
    assert result['summary']['review_frames']==0


@pytest.mark.parametrize('boundary',['segment','lost','invalid'])
def test_review_does_not_cross_segment_or_use_missing_observations(boundary):
    document=sample();document['frames'][10]['landmarks'][7].update(x=0.,y=-.5)
    if boundary=='segment':
        for f in document['frames'][10:]:f['tracking_segment']=1
    elif boundary=='lost':document['frames'][10]['person_bbox']=None
    else:document['frames'][10]['landmarks'][7]['valid']=False
    result=review_pose(document)
    assert not any(e['bone']==[5,7] for e in result['events'])


def test_cancel_stops_diagnostic_work():
    with pytest.raises(KeyboardInterrupt):review_pose(sample(),lambda:True)
