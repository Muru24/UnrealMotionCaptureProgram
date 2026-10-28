import copy
import math
import pytest
from core.motion.refined_hands import shape,select_crop_hands


def fixture(n=5):
    points=[[0.,0.,0.]]
    for x in [-.035,-.025,0.,.025,.04]:
        points.extend([[x,.06+j*.025,0.] for j in range(4)])
    candidate={'world_joints':points,'image_joints':[[100.,100.] for _ in points]}
    raw={'video':{'width':400,'height':400},'frames':[]}
    crop={'schema':'hand_crop_comparison_v1','status':'completed','frames':[]}
    for i in range(n):
        raw['frames'].append({'tracking':{'state':'tracked'},'roi':[0,0,400,400],'outputs':{'pred_keypoints_2d':[[100.,100.] for _ in range(70)]}})
        crop['frames'].append({'frame_index':i,'hands':{'left':{'status':'associated_model_candidate','roi':[50,50,150,150],'candidate':copy.deepcopy(candidate)}}})
    return raw,crop


def test_selection_and_rigid_shape_invariance():
    raw,crop=fixture();before=copy.deepcopy(crop)
    assert select_crop_hands(raw,crop)['selected_hand_frames']=={'l':5,'r':0}
    a=shape(crop['frames'][0]['hands']['left']['candidate'])
    b=copy.deepcopy(crop['frames'][0]['hands']['left']['candidate'])
    b['world_joints']=[[3-2*y,4+2*x,5+2*z] for x,y,z in b['world_joints']]
    for finger_a,finger_b in zip(a['canonical'],shape(b)['canonical']):
        for edge_a,edge_b in zip(finger_a,finger_b):assert edge_a==pytest.approx(edge_b,abs=1e-12)
    assert crop==before


def test_short_missing_scene_and_duplicate_runs_fall_back():
    raw,crop=fixture(2);assert select_crop_hands(raw,crop)['selected_hand_frames']['l']==0
    raw,crop=fixture();raw['frames'][2]['tracking']['state']='lost'
    assert select_crop_hands(raw,crop)['selected_hand_frames']['l']==0
    raw,crop=fixture(4)
    for row in raw['frames'][2:]:row['tracking_segment']=1
    assert select_crop_hands(raw,crop)['selected_hand_frames']['l']==0
    raw,crop=fixture()
    for row in crop['frames']:row['hands']['right']=copy.deepcopy(row['hands']['left'])
    assert select_crop_hands(raw,crop)['selected_hand_frames']=={'l':0,'r':0}


def test_invalid_geometry_and_one_finger_fallback():
    raw,crop=fixture();candidate=crop['frames'][0]['hands']['left']['candidate']
    candidate['world_joints'][1][0]=math.nan;assert shape(candidate) is None
    raw,crop=fixture()
    for row in crop['frames']:
        p=row['hands']['left']['candidate']['world_joints'];p[2]=p[1][:]
    result=select_crop_hands(raw,crop)
    assert result['selected_hand_frames']['l']==5
    assert 'thumb' not in result['frames'][0]['hands']['l']['valid_fingers']
    crop['frames'][0]['frame_index']=7
    with pytest.raises(ValueError):select_crop_hands(raw,crop)
