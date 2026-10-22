from copy import deepcopy
import numpy as np
import pytest
from core.pose2d.roi_envelope import RoiEnvelope


def row(index=0, roi=(10, 10, 110, 210), segment=0):
    return dict(frame_index=index, roi=list(roi), person_bbox=[30, 40, 90, 180],
                tracking_segment=segment, tracking={'state':'tracked'}, mask={'file':'masks/0.png'})


def test_contraction_retains_context_and_expansion_includes_current_observation():
    policy=RoiEnvelope(30)
    policy.update(row())
    current=row(1,(20,20,100,200)); original=deepcopy(current)
    result=policy.update(current)
    assert 10<result['roi'][0]<20 and 100<result['roi'][2]<110
    assert current==original
    expanded=policy.update(row(2,(0,0,120,220)))
    assert expanded['roi']==[0,0,120,220]
    assert expanded['mask']==current['mask']


@pytest.mark.parametrize('boundary,reason', [('gap','frame_gap'),('segment','segment_boundary'),('motion','abrupt_geometry')])
def test_boundary_resets_without_bridging(boundary,reason):
    policy=RoiEnvelope(30);policy.update(row())
    current=row(2 if boundary=='gap' else 1,(20,20,100,200),int(boundary=='segment'))
    if boundary=='motion':current['person_bbox']=[400,400,460,540]
    result=policy.update(current)
    assert result['roi']==current['roi'] and result['roi_stabilization']['reset']==reason


def test_missing_observation_does_not_predict_and_clears_history():
    policy=RoiEnvelope(30);policy.update(row())
    missing=row(1);missing['roi']=None;missing['person_bbox']=None
    assert policy.update(missing)['roi'] is None
    current=row(2,(20,20,100,200))
    assert policy.update(current)['roi']==current['roi']


def test_context_area_is_bounded():
    policy=RoiEnvelope(30);policy.update(row())
    current=row(1,(40,80,70,120))
    result=policy.update(current)
    assert result['roi']==current['roi'] and result['roi_stabilization']['reset']=='area_limit'


@pytest.mark.parametrize('kwargs',[{'fps':0},{'fps':float('nan')},{'fps':30,'tau_seconds':0},
                                  {'fps':30,'tau_seconds':float('inf')},{'fps':30,'max_area_ratio':.9}])
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):RoiEnvelope(**kwargs)


@pytest.mark.parametrize('roi',[(1,2,1,4),(1,2,float('nan'),4),(1,2,3)])
def test_invalid_observed_roi(roi):
    with pytest.raises(ValueError):RoiEnvelope(30).update(row(roi=roi))


def test_envelope_remains_inside_image_and_contains_every_current_roi():
    policy=RoiEnvelope(30);rng=np.random.default_rng(42)
    for index in range(120):
        box=[*rng.uniform(0,20,2),*rng.uniform(100,200,2)]
        current=row(index,box);result=policy.update(current);a=result['roi']
        assert 0<=a[0]<=box[0] and 0<=a[1]<=box[1]
        assert box[2]<=a[2]<=200 and box[3]<=a[3]<=200
        assert result['roi_stabilization']['area_ratio_to_observed_roi']<=1.8
