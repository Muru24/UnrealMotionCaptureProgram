import json
import numpy as np
import pytest
from core.pose3d.sam_completion import adapt,complete_sam,LEGS


def sample():
    names=[str(i) for i in range(70)]
    for i,name in {9:'left-hip',10:'right-hip',11:'left-knee',12:'right-knee',
                   13:'left-ankle',14:'right-ankle',17:'left-heel',20:'right-heel'}.items():names[i]=name
    frames=[]
    for t in range(30):
        xyz=np.zeros((70,3));image=np.full((70,2),100.)
        for hip,knee,ankle in LEGS:
            x=-.2 if hip==9 else .2
            xyz[hip]=[x,0,0];xyz[knee]=[x,.4,.1];xyz[ankle]=[x,.8,0]
            for tip in ((15,16,17) if hip==9 else (18,19,20)):
                xyz[tip]=xyz[ankle]+[0,.05,.1]
        frames.append({'frame_index':t,'timestamp':t/30,'outputs':{
            'pred_keypoints_3d':xyz.tolist(),'pred_keypoints_2d':image.tolist()}})
    return {'schema':'sam3d_mhr70','coordinates':'sam_native_pred_keypoints_3d',
            'joint_names':names,'video':{'width':200,'height':200,'fps':30},
            'roi':[0,0,200,200],'selection':'fixed_first_frame_roi','frames':frames}


def test_short_offscreen_ankle_interpolates_without_mutating_raw_or_arms():
    raw=sample()
    for t in (10,11,12):raw['frames'][t]['outputs']['pred_keypoints_2d'][13]=[100,250]
    before=json.dumps(raw);document,out=complete_sam(raw)
    assert json.dumps(raw)==before and out['schema']=='sam3d_mhr70_completion'
    for t in (10,11,12):
        p=out['frames'][t]['joints'];assert p[13]['source']=='interpolated'
        assert np.linalg.norm(np.subtract(p[13]['xyz'],p[11]['xyz']))==pytest.approx(out['lengths']['11-13'])
        assert p[7]['xyz']==[document['frames'][t]['landmarks'][7][k] for k in ('x','y','z')]


def test_long_reidentified_segment_is_preserved_and_lost_frames_never_completed():
    raw=sample();raw['target_id']=1
    for i,frame in enumerate(raw['frames']):
        missing=10<=i<20
        frame['tracking_segment']=1 if i>=20 else 0
        frame['tracking']={'state':'lost' if missing else 'tracked','track_id':1}
        if missing:frame['outputs']=None
    before=json.dumps(raw)
    document,out=complete_sam(raw)
    assert json.dumps(raw)==before
    for i in range(10,20):assert all(j['xyz'] is None for j in out['frames'][i]['joints'])
    assert out['frames'][20]['tracking_segment']==document['frames'][20]['tracking_segment']==1
    assert out['frames'][9]['tracking_segment']==0


def test_entire_clip_cropped_legs_use_explicit_hidden_model_priors():
    raw=sample()
    for f in raw['frames']:
        for j in range(11,21):f['outputs']['pred_keypoints_2d'][j]=[100,300]
    _,out=complete_sam(raw)
    assert all(v=='hidden_model_predictions' for v in out['length_calibration'].values())
    for f in out['frames']:
        assert f['joints'][13]['source']=='estimated_leg_ik'
        assert f['joints'][17]['source']=='estimated_foot_offset'
        assert np.isfinite(f['joints'][13]['xyz']).all()


def test_outside_torso_not_completed_and_wrong_joint_order_rejected():
    raw=sample()
    for j in (9,10):raw['frames'][12]['outputs']['pred_keypoints_2d'][j]=[300,300]
    _,out=complete_sam(raw);assert all(p['xyz'] is None for p in out['frames'][12]['joints'])
    raw['joint_names'][13]='right-ankle'
    with pytest.raises(ValueError,match='ordering'):adapt(raw)


def test_sam_completion_cancel_and_partial_report_guard(tmp_path):
    raw=sample()
    with pytest.raises(KeyboardInterrupt):complete_sam(raw,lambda:True)
    from app.completion_job import run_completion
    (tmp_path/'sam3d.json').write_text(json.dumps(raw))
    (tmp_path/'report.json').write_text(json.dumps({'status':'cancelled','frames_processed':30}))
    with pytest.raises(ValueError,match='Finish SAM'):run_completion(tmp_path)
    assert not list(tmp_path.glob('completion_*'))


def test_short_clip_does_not_invent_uncalibrated_hidden_foot_lengths():
    raw=sample();raw['frames']=raw['frames'][:3]
    for f in raw['frames']:
        f['outputs']['pred_keypoints_2d'][13]=[199,100]
    _,out=complete_sam(raw)
    assert not out['lengths']
    assert all(f['joints'][13]['xyz'] is None for f in out['frames'])


def test_dynamic_roi_loss_is_preserved_through_foot_completion():
    raw=sample();raw['selection']='detector_tracker_target_id';raw['target_id']=1
    for f in raw['frames']:
        f['roi']=raw['roi'];f['tracking']={'state':'tracked','track_id':1}
    del raw['roi']
    f=raw['frames'][12];f['tracking']['state']='lost';f['outputs']=None;f['roi']=None
    _,out=complete_sam(raw)
    assert all(p['xyz'] is None for p in out['frames'][12]['joints'])
    assert out['frames'][13]['joints'][13]['xyz'] is not None
    assert 'lost_target_frames_not_completed' in out['limits']


def arm_sample():
    raw=sample()
    for f in raw['frames']:
        p=f['outputs']['pred_keypoints_3d']
        for j,xyz in {5:[-.2,-.3,0],7:[-.4,-.1,0],62:[-.55,.1,0],
                      6:[.2,-.3,0],8:[.4,-.1,0],41:[.55,.1,0]}.items():p[j]=xyz
    return raw


def test_short_elbow_and_wrist_gaps_use_parent_relative_endpoints_and_preserve_raw():
    raw=arm_sample()
    for t in (10,11,12):
        for j in (7,62):
            raw['frames'][t]['outputs']['pred_keypoints_2d'][j]=[300,300]
            raw['frames'][t]['outputs']['pred_keypoints_3d'][j]=[99,99,99]
    before=json.dumps(raw);_,out=complete_sam(raw)
    assert json.dumps(raw)==before
    assert out['joint_gap_completion']['filled_joint_frames']==6
    for t in (10,11,12):
        assert out['frames'][t]['joints'][7]['source']=='interpolated_joint'
        assert out['frames'][t]['joints'][62]['xyz']==pytest.approx([-.55,.1,0])
    assert out['frames'][9]['joints'][62]['xyz']==[-.55,.1,0]
    assert out['frames'][13]['joints'][62]['source']=='observed'


@pytest.mark.parametrize('condition',['long','segment','lost','large_turn','length_change','unbounded'])
def test_arm_gaps_do_not_invent_motion_across_unsafe_boundaries(condition):
    raw=arm_sample();start=0 if condition=='unbounded' else 10;end=18 if condition=='long' else 13
    for t in range(start,end):raw['frames'][t]['outputs']['pred_keypoints_2d'][62]=[300,300]
    if condition=='segment':
        for f in raw['frames'][12:]:f['tracking_segment']=1
    if condition=='lost':
        raw['frames'][11]['tracking']={'state':'lost','track_id':1};raw['frames'][11]['outputs']=None
    if condition in ('large_turn','length_change'):
        p=raw['frames'][13]['outputs']['pred_keypoints_3d']
        p[62]=(np.asarray(p[7])+(np.asarray(p[62])-p[7])*(-1 if condition=='large_turn' else 4)).tolist()
    _,out=complete_sam(raw)
    assert out['joint_gap_completion']['filled_joint_frames']==0
    for t in range(start,end):assert out['frames'][t]['joints'][62]['xyz'] is None


def test_leg_direction_interpolation_and_recent_history_respect_segment_boundary():
    raw=arm_sample()
    for t in (10,11,12):raw['frames'][t]['outputs']['pred_keypoints_2d'][13]=[300,300]
    for f in raw['frames'][12:]:f['tracking_segment']=1
    _,out=complete_sam(raw)
    assert all(out['frames'][t]['joints'][13]['source']!='interpolated' for t in (10,11,12))
    assert out['frames'][12]['joints'][13]['source']!='estimated_recent_direction'


def test_detected_scene_cut_blocks_short_arm_gap_and_preserves_scene_metadata():
    from core.video.scene_cuts import SceneTimeline
    raw=arm_sample();timeline=SceneTimeline()
    for i,frame in enumerate(raw['frames']):
        raw['frames'][i]=timeline.annotate(frame,{'frame_index':i,'cut':i==12})
        if 10<=i<13:frame['outputs']['pred_keypoints_2d'][62]=[300,300]
    before=json.dumps(raw)
    document,out=complete_sam(raw)
    assert json.dumps(raw)==before
    assert out['joint_gap_completion']['blocked_spans']['segment_boundary']>=1
    assert all(out['frames'][i]['joints'][62]['xyz'] is None for i in (10,11,12))
    assert document['frames'][12]['scene']==out['frames'][12]['scene']==raw['frames'][12]['scene']
