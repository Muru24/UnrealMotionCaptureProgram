import numpy as np
import pytest

from core.pose3d.observations import MaskSupport, intersection_ratios, mask_support, same_foreground
from core.pose3d.observations import shared_previous_observation


def support(x1=30,y1=20,x2=70,y2=180):
    mask=np.zeros((200,100),np.float32)
    mask[y1:y2,x1:x2]=.9
    return mask_support(mask,100,200)


def test_segmentation_box_is_independent_of_joint_visibility():
    observed=support()
    assert observed is not None
    assert observed.bbox[0]<30 and observed.bbox[2]>70
    assert observed.bbox[1]<20 and observed.bbox[3]>180
    assert observed.pixels.shape==(200,100)
    assert intersection_ratios(observed,observed)==(1.,1.,1.)


def test_mask_shape_singleton_channel_and_bounded_matching_memory():
    mask=np.zeros((1280,720,1),np.float32)
    mask[300:1200,200:500,0]=.9
    observed=mask_support(mask,720,1280)
    assert max(observed.pixels.shape)<=256
    assert observed.bbox[0]==pytest.approx(188,abs=8)
    assert observed.bbox[3]==pytest.approx(1236,abs=10)


@pytest.mark.parametrize('kind',['empty','full','nonfinite','wrong_shape','tiny'])
def test_unusable_masks_do_not_create_fake_person_boxes(kind):
    mask=np.zeros((200,100),np.float32)
    if kind=='full':mask[:]=1
    if kind=='nonfinite':mask[10,10]=np.nan
    if kind=='wrong_shape':mask=mask[:100]
    if kind=='tiny':mask[5:7,5:7]=1
    assert mask_support(mask,100,200) is None


def test_disconnected_background_noise_does_not_expand_body_box():
    mask=np.zeros((200,100),np.float32)
    mask[20:180,30:70]=.9
    baseline=mask_support(mask,100,200)
    mask[1,1]=1.;mask[195,95]=1.
    noisy=mask_support(mask,100,200)
    assert np.array_equal(baseline.bbox,noisy.bbox)


def test_nested_same_body_needs_a_shared_unique_previous_observation():
    full=support()
    partial=support(32,60,68,176)
    assert same_foreground(full,partial,[full])
    assert not same_foreground(full,partial,[])
    assert not same_foreground(full,partial,[None])


def test_two_previously_separate_bodies_that_now_overlap_remain_distinct():
    # Current masks can be identical during occlusion: previous distinct support
    # still prevents mask-based merging and leaves the tracker ambiguity guard on.
    left=support(10,20,50,180)
    right=support(50,20,90,180)
    overlapping=support(25,20,75,180)
    assert not same_foreground(overlapping,overlapping,[left,right])


def test_partial_overlap_and_disjoint_bodies_are_not_merged():
    a=support(10,20,55,180)
    b=support(40,20,85,180)
    assert not same_foreground(a,b,[a])
    assert not same_foreground(a,support(60,20,95,180),[a])


def test_small_part_inside_body_is_not_automatically_another_full_body_duplicate():
    whole=support(10,20,90,180)
    tiny=support(45,50,55,100)
    assert not same_foreground(whole,tiny,[whole])


def backend_with_raw(masks,previous=None):
    from types import SimpleNamespace as NS
    from core.pose3d.mediapipe_backend import MediaPipeBackend
    images=[];world=[]
    for person in range(len(masks)):
        images.append([NS(x=.3+person*.12+i*.006,y=.18+i*.02,z=.01,
                           visibility=.9,presence=.9) for i in range(33)])
        world.append([NS(x=person*.25+i*.01,y=i*.02,z=.3) for i in range(33)])
    raw=NS(pose_landmarks=images,pose_world_landmarks=world,
           segmentation_masks=[NS(numpy_view=lambda m=m:m) for m in masks])
    backend=MediaPipeBackend.__new__(MediaPipeBackend)
    backend.landmarker=NS(detect_for_video=lambda image,timestamp:raw)
    backend.mp=NS(ImageFormat=NS(SRGB=1),Image=lambda **kwargs:kwargs)
    backend._last_timestamp=-1
    backend._previous_supports=previous or []
    backend.last_diagnostics={}
    return backend,raw


def test_backend_merges_supported_duplicate_and_preserves_one_raw_pose():
    full=np.zeros((200,100,1),np.float32);full[20:180,30:70]=.9
    part=np.zeros_like(full);part[60:176,32:68]=.9
    backend,raw=backend_with_raw([full,part],[mask_support(full,100,200)])
    result=backend._candidates(np.zeros((200,100,3),np.uint8),0)
    assert len(result)==1
    assert result[0][1][0].x==raw.pose_world_landmarks[0][0].x
    assert result[0][1][0].image_x==pytest.approx(raw.pose_landmarks[0][0].x*100)
    assert backend.last_diagnostics['duplicates_suppressed']==1
    assert backend.last_diagnostics['box_sources']==['segmentation']


def test_backend_keeps_two_initial_nested_observations_without_history():
    full=np.zeros((200,100,1),np.float32);full[20:180,30:70]=.9
    part=np.zeros_like(full);part[60:176,32:68]=.9
    backend,raw=backend_with_raw([full,part])
    assert len(backend._candidates(np.zeros((200,100,3),np.uint8),0))==2
    assert backend.last_diagnostics['duplicates_suppressed']==0


def test_matching_joints_alone_cannot_merge_previously_distinct_bodies():
    full=np.zeros((200,100,1),np.float32);full[20:180,25:75]=.9
    previous=[support(10,20,50,180),support(50,20,90,180)]
    backend,raw=backend_with_raw([full,full],previous)
    raw.pose_landmarks[1]=raw.pose_landmarks[0]
    assert not shared_previous_observation(mask_support(full,100,200),mask_support(full,100,200),previous)
    assert len(backend._candidates(np.zeros((200,100,3),np.uint8),0))==2


def test_invalid_mask_falls_back_to_landmarks_and_mismatched_mask_counts_fail():
    from core.pose3d.interface import Pose3DError
    backend,raw=backend_with_raw([np.zeros((200,100,1),np.float32)])
    assert len(backend._candidates(np.zeros((200,100,3),np.uint8),0))==1
    assert backend.last_diagnostics['box_sources']==['landmarks']
    backend._last_timestamp=-1
    raw.segmentation_masks.append(raw.segmentation_masks[0])
    with pytest.raises(Pose3DError,match='mask/pose counts'):
        backend._candidates(np.zeros((200,100,3),np.uint8),0)
