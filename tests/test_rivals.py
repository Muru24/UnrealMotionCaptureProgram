import numpy as np
from core.pose2d.rivals import OtherPeople
from core.pose2d.tracker import appearance


def scene():
    frame=np.full((240,500,3),(0,0,200),np.uint8)
    target=np.array([0,20,120,220],float);other=target+[190,0,190,0]
    memory=OtherPeople(30);memory.advance();memory.observe(frame,np.stack((target,other)),target)
    return frame,target,other,memory


def test_same_clothes_candidate_matching_known_other_person_is_rejected():
    frame,target,other,memory=scene();memory.advance()
    result=memory.check(other,appearance(frame,other),target+[80,0,80,0],0.)
    assert result['rejected'] and result['reason']=='matches_recent_other_person'
    assert result['rival_score']>result['target_score']+.15


def test_correct_target_and_tied_identity_are_not_vetoed_by_spatial_memory():
    frame,target,other,memory=scene()
    assert not memory.check(target,appearance(frame,target),target,0.)['rejected']
    assert not memory.check(other,appearance(frame,other),other,0.)['rejected']


def test_uncertain_frames_cannot_move_or_add_reference_and_expired_memory_is_dropped():
    frame,target,other,memory=scene();before=memory.references[0]['box'].copy()
    for _ in range(10):
        memory.advance();memory.observe(frame,np.array([target]),None)
    assert len(memory.references)==1 and np.array_equal(memory.references[0]['box'],before)
    for _ in range(21):memory.advance()
    assert not memory.references
    assert not memory.check(other,appearance(frame,other),target,0.)['rejected']


def test_overlapping_duplicate_candidates_do_not_seed_other_people():
    frame,target,other,_=scene();memory=OtherPeople(30);memory.advance()
    memory.observe(frame,np.stack((target,other,other)),target)
    assert not memory.references


def test_missing_detection_does_not_mean_unknown_candidate_is_other_person():
    frame,target,other,_=scene();memory=OtherPeople(30);memory.advance()
    memory.observe(frame,np.stack((target,other)),None)
    assert not memory.references and not memory.check(other,appearance(frame,other),target,0.)['rejected']


def test_known_other_position_requires_two_observations_and_never_learns_appearance():
    frame,target,other,memory=scene();look=tuple(v.copy() for v in memory.references[0]['look'])
    moved=other+[10,0,10,0]
    memory.advance();memory.observe(frame,np.stack((target,moved)),None)
    assert np.array_equal(memory.references[0]['box'],other)
    memory.advance();memory.observe(frame,np.stack((target,moved)),None)
    assert np.array_equal(memory.references[0]['box'],moved)
    assert all(np.array_equal(a,b) for a,b in zip(look,memory.references[0]['look']))


def test_known_other_follow_is_frozen_after_long_loss_or_overlap():
    frame,target,other,memory=scene()
    for _ in range(3):
        memory.advance();memory.observe(frame,np.array([other+[10,0,10,0]]),None,allow_follow=False)
    assert np.array_equal(memory.references[0]['box'],other)
    for _ in range(3):
        memory.advance();memory.observe(frame,np.stack((other+10,other+11)),None)
    assert np.array_equal(memory.references[0]['box'],other)

def head_pose(x,y=50,confidence=.9):
    points=np.array([[x-2,y],[x,y-2],[x+2,y],[x-3,y+2],[x+3,y+2]],float)
    return points,np.full(5,confidence)


def test_head_position_blocks_known_other_despite_partial_box_change():
    frame,target,other,memory=scene()
    memory.references[0]['head']=np.array([240.,50.])
    candidate=other+np.array([20,0,60,0])
    result=memory.check(candidate,appearance(frame,candidate),candidate,0.,
                        head_pose(260),head_pose(60))
    assert result['rejected'] and result['evidence']=='confident_head_position'


def test_head_guard_requires_confidence_and_clear_target_separation():
    frame,target,other,memory=scene();memory.references[0]['head']=np.array([240.,50.])
    candidate=other+np.array([20,0,60,0])
    for current,previous in [(head_pose(260,confidence=.1),head_pose(60)),
                             (head_pose(260),head_pose(255))]:
        assert not memory.check(candidate,appearance(frame,candidate),candidate,0.,current,previous)['rejected']
