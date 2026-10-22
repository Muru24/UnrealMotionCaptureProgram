from copy import deepcopy
import numpy as np
import pytest
from core.video.scene_cuts import SceneCutDetector, SceneTimeline
from core.pose2d.roi_envelope import RoiEnvelope


def image(color):
    return np.full((240,160,3),color,dtype=np.uint8)


def detect(frames):
    detector=SceneCutDetector();events=[]
    for i,frame in enumerate(frames):
        event=detector.observe(frame,i)
        if event is not None:events.append(event)
    event=detector.finish()
    if event is not None:events.append(event)
    return events


def test_hard_cut_belongs_to_first_frame_of_new_scene_and_final_frame_is_retained():
    events=detect([image(20),image(20),image(190),image(190)])
    assert [e['frame_index'] for e in events]==list(range(4))
    assert [e['frame_index'] for e in events if e['cut']]==[2]
    assert len(detect([image(20)]))==1
    assert detect([])==[]


def test_large_subject_translation_with_same_histogram_is_not_a_cut():
    a=image(20);a[30:180,0:80]=210
    b=image(20);b[30:180,80:160]=210
    events=detect([a,a,b,b])
    assert events[2]['mean_pixel_difference']>.08
    assert not any(e['cut'] for e in events)


def test_single_frame_flash_is_suppressed_on_both_sides():
    events=detect([image(20),image(20),image(240),image(20),image(20)])
    assert not any(e['cut'] for e in events)
    assert all(events[i]['reason']=='single_frame_flash_suppressed' for i in (2,3))


def test_fade_is_not_misrepresented_as_supported_cut_detection():
    events=detect([image(i) for i in range(20,200,5)])
    assert not any(e['cut'] for e in events)


def test_scene_timeline_keeps_identity_loss_and_recovery_segments_without_mutation():
    timeline=SceneTimeline()
    row=dict(frame_index=3,tracking_segment=1,roi=None,tracking={'state':'uncertain','track_id':1})
    before=deepcopy(row)
    out=timeline.annotate(row,dict(frame_index=3,cut=True))
    assert row==before and out['tracking_segment']==2 and out['roi'] is None
    assert out['tracking']==row['tracking'] and out['scene']['index']==1
    row.update(frame_index=4,tracking_segment=2)
    assert timeline.annotate(row,dict(frame_index=4,cut=False))['tracking_segment']==3


def test_scene_boundary_resets_roi_envelope_even_without_a_large_position_change():
    timeline=SceneTimeline();envelope=RoiEnvelope(30)
    row=dict(frame_index=0,tracking_segment=0,roi=[0,0,100,200],person_bbox=[20,30,80,180])
    envelope.update(timeline.annotate(row,dict(frame_index=0,cut=False)))
    row.update(frame_index=1,roi=[10,10,90,190])
    out=envelope.update(timeline.annotate(row,dict(frame_index=1,cut=True)))
    assert out['roi']==row['roi'] and out['roi_stabilization']['reset']=='segment_boundary'


def test_alignment_and_frame_type_errors_are_explicit():
    detector=SceneCutDetector()
    with pytest.raises(ValueError):detector.observe(image(0),1)
    with pytest.raises(ValueError):detector.observe(image(0).astype(float),0)
    with pytest.raises(ValueError):SceneTimeline().annotate({'frame_index':1},{'frame_index':2,'cut':False})
