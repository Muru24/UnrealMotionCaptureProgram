import numpy as np
import pytest
from core.pose2d.motion import BodyMotion
from core.pose2d.tracker import TargetTracker
from core.pose2d.metrics import tracking_metrics


def pose():
    p=np.array([[60,20],[55,18],[65,18],[50,20],[70,20],[40,50],[80,50],[25,80],[95,80],
                [20,110],[100,110],[45,100],[75,100],[45,140],[75,140],[45,180],[75,180]],float)
    return p,np.ones(17)


def test_body_center_does_not_follow_accessory_box_width_change():
    m=BodyMotion(30);p,s=pose();m.initialize([0,0,120,195],(p,s))
    z,kind,*_=m.measurement([0,0,200,195],(p,s))
    assert kind=='hip' and z.tolist()==[60,100]
    s[[11,12]]=0
    z,kind,*_=m.measurement([0,0,200,195],(p,s))
    assert kind=='shoulder_with_hip_offset' and z.tolist()==[60,100]


def test_kalman_velocity_predicts_a_short_gap_and_covariance_grows():
    m=BodyMotion(30);p,s=pose()
    m.initialize([0,0,120,195],(p,s))
    for i in range(1,8):
        m.predict();m.update(np.array([0,0,120,195])+[i*5,0,i*5,0],(p+[i*5,0],s))
    before=m.x[:2].copy();variance=np.trace(m.P[:2,:2]);m.predict();m.predict()
    assert m.x[0]>before[0]+5 and abs(m.x[1]-before[1])<1e-6
    assert np.trace(m.P[:2,:2])>variance
    assert m.innovation(np.array([10000.,10000.]),3)>9.21


def test_high_confidence_incoherent_torso_cannot_poison_offsets():
    m=BodyMotion(30);p,s=pose();box=[0,0,120,195]
    m.initialize(box,(p,s));offset=m.shoulder_offset.copy();length=m.torso_length
    wrong=p.copy();wrong[[11,12],1]=52
    z,kind,*_=m.measurement(box,(wrong,s))
    assert kind=='box_fallback'
    m.predict();m.update(box,(wrong,s))
    assert np.array_equal(m.shoulder_offset,offset) and m.torso_length==length
    assert m.measurement(box,(p,s))[1]=='hip'


def test_torso_validation_does_not_assume_upright_or_left_right_order():
    m=BodyMotion(30);p,s=pose();box=[0,0,200,200]
    m.initialize(box,(p,s))
    rotated=np.column_stack((200-p[:,1],p[:,0]))
    assert m.measurement(box,(rotated,s))[1]=='hip'
    swapped=p.copy();swapped[[11,12]]=swapped[[12,11]]
    assert m.measurement(box,(swapped,s))[1]=='hip'


def test_source_transition_preserves_noise_floor_only_until_accepted():
    m=BodyMotion(30);p,s=pose();box=[0,0,120,195]
    m.initialize(box,(p,s))
    shoulder_scores=s.copy();shoulder_scores[[11,12]]=0
    _,kind,std,*_=m.measurement(box,(p,shoulder_scores))
    quality=dict(m.observation_quality)
    assert kind=='shoulder_with_hip_offset' and quality['source_changed']
    assert std==max(quality['base_std_pixels'],m.accepted_base_std)
    for _ in range(5):m.measurement(box,None)
    assert m.accepted_kind=='hip'
    assert m.measurement(box,(p,shoulder_scores))[2]==std
    m.predict();m.update(box,(p,shoulder_scores))
    assert m.measurement(box,(p,shoulder_scores))[2]==quality['base_std_pixels']
    _,kind,hip_std,*_=m.measurement(box,(p,s))
    assert kind=='hip' and hip_std>m.observation_quality['base_std_pixels']
    m.predict();m.update(box,(p,s))
    assert m.measurement(box,(p,s))[2]==m.observation_quality['base_std_pixels']


def test_source_uncertainty_does_not_open_physical_distance_gate():
    frame=np.full((220,400,3),(0,0,200),np.uint8);p,s=pose();box=np.array([[0,0,120,195]],float)
    tracker=TargetTracker(target_index=0,multi_cue=True,motion_fps=30)
    tracker.select(frame,box,(p[None],s[None]))
    far=box+[220,0,220,0]
    tracker.motion.P[:2,:2]=np.eye(2)*1e8
    decision=tracker.select(frame,far)
    assert decision.bbox is None and tracker.motion.accepted_kind=='hip'
    assert tracker.association_diagnostics[0]['reason']=='motion_gate'


def test_box_fallback_cannot_relax_returning_hip_candidate():
    m=BodyMotion(30);p,s=pose();box=[0,0,120,195]
    m.initialize(box,None)
    _,kind,std,*_=m.measurement(box,(p,s))
    assert kind=='hip' and m.observation_quality['source_changed']
    assert std==m.observation_quality['base_std_pixels']
    assert not m.observation_quality['shoulder_to_hip_noise_floor']


def test_fast_reconnect_requires_all_cues_and_preserves_selected_id():
    frame=np.full((220,400,3),(0,0,200),np.uint8);p,s=pose();box=np.array([[0,0,120,195]],float)
    t=TargetTracker(target_index=0,multi_cue=True,motion_fps=30,reconnect_confirmations=2,fast_reconnect=True)
    t.select(frame,box,(p[None],s[None]))
    t.select(frame,np.empty((0,4)))
    d=t.select(frame,box,(p[None],s[None]))
    assert d.bbox is not None and d.info.track_id==1 and d.info.reason=='short_gap_reconnected'
    assert t.motion_diagnostics['reconnection']['fast_path']


@pytest.mark.parametrize('condition',['ambiguous','weak_appearance','missing_skeleton','longer_gap','disabled'])
def test_fast_reconnect_does_not_skip_safety_confirmation(condition,monkeypatch):
    import core.pose2d.tracker as module
    frame=np.full((220,400,3),(0,0,200),np.uint8);p,s=pose();box=np.array([[0,0,120,195]],float)
    t=TargetTracker(target_index=0,multi_cue=True,motion_fps=30,max_missing=12,
                    reconnect_confirmations=2,fast_reconnect=condition!='disabled')
    t.select(frame,box,(p[None],s[None]));reference=t.skeleton[0].copy()
    if condition=='ambiguous':
        t.select(frame,np.vstack((box,box)),(np.stack((p,p)),np.stack((s,s))))
    else:
        for _ in range(4 if condition=='longer_gap' else 1):t.select(frame,np.empty((0,4)))
    if condition=='weak_appearance':monkeypatch.setattr(module,'appearance_distance',lambda *args:.4)
    d=t.select(frame,box,None if condition=='missing_skeleton' else (p[None],s[None]))
    assert d.bbox is None and d.info.reason=='reconnection_pending'
    assert t.motion_diagnostics['prediction_only'] and not t.motion_diagnostics['reconnection']['fast_path']
    assert np.array_equal(t.skeleton[0],reference)


def test_strong_overlap_history_still_requires_confirmation_after_separation(monkeypatch):
    import core.pose2d.association as association
    scores=iter([.95,.5,.95])
    def strong_score(*args):
        return next(scores),{'iou':.9,'center':.9,'appearance':.9,'skeleton':.9},{}
    monkeypatch.setattr(association,'tracking_score',strong_score)
    frame=np.full((220,400,3),(0,0,200),np.uint8);p,s=pose();box=np.array([[0,0,120,195]],float)
    t=TargetTracker(target_index=0,multi_cue=True,motion_fps=30,reconnect_confirmations=2,fast_reconnect=True)
    t.select(frame,box,(p[None],s[None]))
    d=t.select(frame,np.vstack((box,box+[1,0,1,0])),(np.stack((p,p+[1,0])),np.stack((s,s))))
    assert d.bbox is None and d.info.reason=='reconnection_pending' and t.gap_ambiguous
    # The next isolated observation must be confirmed through the normal path.
    d=t.select(frame,box,(p[None],s[None]))
    assert d.bbox is not None and not t.motion_diagnostics['reconnection']['fast_path']


def test_overlap_waits_then_reconnects_without_updating_reference_from_ambiguity():
    t=TargetTracker(target_index=0,multi_cue=True,motion_fps=30,reconnect_confirmations=2,max_missing=12)
    frame=np.full((220,400,3),(0,0,200),np.uint8);p,s=pose();box=np.array([[0,0,120,195]],float)
    t.select(frame,box,(p[None],s[None]));reference=t.skeleton[0].copy()
    for _ in range(2):
        d=t.select(frame,np.array([[0,0,120,195],[1,0,121,195]],float),(np.stack([p,p+1]),np.ones((2,17))))
        assert d.bbox is None and not t.latched and t.motion_diagnostics['prediction_only']
        assert np.array_equal(t.skeleton[0],reference)
    assert t.select(frame,box+np.array([3,0,3,0]),((p+[3,0])[None],s[None])).bbox is None
    d=t.select(frame,box+np.array([4,0,4,0]),((p+[4,0])[None],s[None]))
    assert d.bbox is not None and d.info.track_id==1 and not t.motion_diagnostics['prediction_only']


def test_ambiguity_does_not_allow_unbounded_prediction_or_new_identity():
    t=TargetTracker(target_index=0,multi_cue=True,motion_fps=30,max_missing=3)
    frame=np.full((220,400,3),(0,0,200),np.uint8);p,s=pose();box=np.array([[0,0,120,195]],float)
    t.select(frame,box,(p[None],s[None]))
    for _ in range(4):
        d=t.select(frame,np.array([[0,0,120,195],[1,0,121,195]],float),(np.stack([p,p+1]),np.ones((2,17))))
        assert d.bbox is None
    assert t.latched and t.select(frame,box,(p[None],s[None])).bbox is None


def test_metrics_separate_box_jumps_body_jumps_gaps_and_unconfirmed_identity_flags():
    rows=[]
    for i in range(7):
        missing=i in (2,3,6);x=0 if i==0 else 120
        rows.append({'frame_index':i,'person_bbox':None if missing else [x,0,x+100,200],
                     'roi':None if missing else [x,0,x+100,200],'people_detected':2 if i==4 else 1,
                     'motion':{'observed_center':None if missing else [50,100],'observation_kind':'hip'}})
    m=tracking_metrics({'frames':rows},30)
    assert m['missing_frames']==3 and m['gap_count']==2
    assert m['max_gap_seconds']==pytest.approx(2/30)
    assert len(m['box_jump_events'])==1 and not m['body_jump_events']
    assert len(m['identity_review_events'])==1 and m['confirmed_identity_switches'] is None


def test_rotation_appearance_change_needs_reliable_body_motion_and_is_flagged(monkeypatch):
    import core.pose2d.tracker as module
    monkeypatch.setattr(module,'appearance_distance',lambda *a:.7)
    frame=np.full((220,400,3),(0,0,200),np.uint8);p,s=pose();box=np.array([[0,0,120,195]],float)
    tracker=TargetTracker(target_index=0,multi_cue=True,motion_fps=30)
    tracker.select(frame,box,(p[None],s[None]))
    first=dict(tracker.motion_diagnostics)
    d=tracker.select(frame,box,(p[None],s[None]));assert d.bbox is not None
    assert tracker.association_diagnostics[0]['appearance_gate_relaxed_by_body_motion']
    rows=[{'frame_index':0,'person_bbox':box[0].tolist(),'roi':box[0].tolist(),'people_detected':1,'motion':first},
          {'frame_index':1,'person_bbox':list(d.bbox),'roi':list(d.bbox),'people_detected':1,
           'motion':tracker.motion_diagnostics,'association_scores':tracker.association_diagnostics}]
    metrics=tracking_metrics({'frames':rows},30)
    assert metrics['identity_review_events'][0]['reasons']==['appearance_change_accepted_with_motion_support']
    assert metrics['confirmed_identity_switches'] is None

def test_shoulder_proxy_noise_scales_with_calibrated_torso_without_moving_measurement():
    m=BodyMotion(30);p,s=pose();box=[0,0,120,195];m.initialize(box,(p,s))
    s[[11,12]]=0;offset=m.shoulder_offset.copy();p[[5,6],0]+=25
    z,kind,std,*_=m.measurement(box,(p,s))
    assert kind=='shoulder_with_hip_offset' and std>=m.torso_length*.35
    assert np.allclose(z,p[[5,6]].mean(axis=0)+offset)
    assert np.array_equal(m.shoulder_offset,offset) and m.accepted_kind=='hip'


@pytest.mark.parametrize('similarity,color,accepted',[(.1,.45,False),(.4,.45,True),(.1,.2,True)])
def test_reconnection_needs_independent_identity_evidence(monkeypatch,similarity,color,accepted):
    import core.pose2d.tracker as tracking
    import core.pose2d.association as association
    monkeypatch.setattr(tracking,'appearance_distance',lambda *a:color)
    monkeypatch.setattr(association,'skeleton_similarity',lambda *a:similarity)
    frame=np.full((220,400,3),(0,0,200),np.uint8);p,s=pose();boxes=np.array([[0,0,120,195]],float)
    t=TargetTracker(target_index=0,multi_cue=True,motion_fps=30,reconnect_identity_guard=True)
    t.select(frame,boxes,(p[None],s[None]));t.select(frame,np.empty((0,4)))
    decision=t.select(frame,boxes,(p[None],s[None]))
    assert (decision.bbox is not None)==accepted
    if not accepted:assert any(a.get('reason')=='weak_reconnection_identity' for a in t.association_diagnostics)
