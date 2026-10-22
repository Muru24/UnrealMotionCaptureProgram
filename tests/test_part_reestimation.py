import copy,json
import numpy as np
import pytest
from test_knee_job import fixture,candidate_fixture
from app.knee_job import digest
from app.fullbody_job import ensure_fullbody,write
from app.joint_review_job import ensure_joint_review
from app.part_reestimate_job import run_part_reestimation,latest_part_result
from core.pose3d.fullbody_candidates import build_packet
from core.pose3d.joint_review import review_joints
from core.pose3d.manual_leg_geometry import project
from core.pose3d.part_reestimation import make_plan,combine,PARTS

def sequence(tmp_path,part='left_leg'):
    source,folder,q,p,cam=fixture(tmp_path);frames=[];variants={};selected=[]
    for i in range(9):
        xyz=q.copy()
        if i==4:xyz[PARTS[part][1],0]+=.7
        pixels=project(xyz,cam);pose={'world_joints':xyz.tolist(),'image_joints':pixels.tolist()}
        frames.append({'frame_index':i,'tracking_segment':0,'tracking':{'state':'tracked','track_id':1},
            'person_bbox':[0,0,320,240],'roi':[0,0,320,240],'outputs':{'pred_keypoints_3d':xyz.tolist(),'pred_keypoints_2d':pixels.tolist()}})
        variants[i]={name:copy.deepcopy(pose) for name in ('observed','tight','stable-flip')}
        selected.append({'frame_index':i,'candidate':'stable',**copy.deepcopy(pose)})
    packet=build_packet({'target_id':1,'video':{'fps':30,'width':320,'height':240},'frames':frames},variants,selected)
    review=review_joints(packet)
    review['repair_requests']=[{'part':part,'start':4,'end_exclusive':5,'context_start':0,'context_end_exclusive':9,
        'target_id':1,'tracking_segment':0,'scene_index':0,'pose_track_start':0}]
    fresh={4:{('arm-context' if 'arm' in part else 'leg-context'):{'world_joints':q.tolist(),'image_joints':p.tolist()}}}
    return packet,review,fresh

def test_context_plan_targets_only_requested_part(tmp_path):
    packet,review,_=sequence(tmp_path);before=copy.deepcopy(packet);plan=make_plan(packet,review)
    assert list(plan['rois'])==['4'] and set(plan['rois']['4'])=={'leg-context'}
    assert plan['targets'][0]['parts']==['left_leg'] and plan['inference_count']==1 and packet==before

def test_fresh_limb_can_replace_spike_without_moving_body_or_other_limbs(tmp_path):
    packet,review,fresh=sequence(tmp_path);before=copy.deepcopy(packet)
    rows,report=combine(packet,review,make_plan(packet,review),fresh)
    assert report['changed_frames']==[4]
    assert rows[4]['changed_parts']==[{'part':'left_leg','variant':'fresh_leg'}]
    fixed=[j for j in range(70) if j not in [11,13,15,16,17]]
    base=np.asarray(packet['frames'][4]['candidates']['stable']['world_joints'])
    np.testing.assert_array_equal(np.asarray(rows[4]['world_joints'])[fixed],base[fixed])
    assert packet==before

def test_worse_mask_support_is_not_accepted_for_smoother_motion(tmp_path):
    packet,review,fresh=sequence(tmp_path)
    support=lambda i,p:2.*(np.mean(p[:,0])<140)
    rows,report=combine(packet,review,make_plan(packet,review),fresh,support)
    assert report['changed_frames']==[] and any(e['rejected']=='mask_support_worse' for e in report['rejections'])

def test_arm_repair_preserves_shoulders_and_both_legs(tmp_path):
    packet,review,fresh=sequence(tmp_path,'left_arm')
    rows,report=combine(packet,review,make_plan(packet,review),fresh)
    assert report['changed_frames']==[4] and rows[4]['changed_parts'][0]['part']=='left_arm'
    editable={7,62,63,65,*range(42,62)};fixed=[j for j in range(70) if j not in editable]
    np.testing.assert_array_equal(np.asarray(rows[4]['world_joints'])[fixed],np.asarray(packet['frames'][4]['candidates']['stable']['world_joints'])[fixed])

def test_arm_auxiliary_points_follow_the_reestimated_elbow(tmp_path):
    packet,review,fresh=sequence(tmp_path,'left_arm')
    rows,_=combine(packet,review,make_plan(packet,review),fresh)
    q=np.asarray(rows[4]['world_joints']);expected=np.asarray(fresh[4]['arm-context']['world_joints'])
    for j in (63,65):np.testing.assert_allclose(q[j]-q[7],expected[j]-expected[7])

def test_parent_disagreement_rejects_fresh_candidate(tmp_path):
    packet,review,fresh=sequence(tmp_path);fresh[4]['leg-context']['image_joints'][9][0]+=100
    _,report=combine(packet,review,make_plan(packet,review),fresh)
    assert any(e['rejected']=='body_attachment_conflict' and e['variant']=='fresh_leg' for e in report['rejections'])

def test_no_requests_preserves_all_pose_arrays(tmp_path):
    packet,review,fresh=sequence(tmp_path);review['repair_requests']=[];plan=make_plan(packet,review)
    rows,report=combine(packet,review,plan,fresh)
    assert not plan['rois'] and report['changed_frames']==[]
    assert rows[4]['world_joints']==packet['frames'][4]['candidates']['stable']['world_joints']

@pytest.mark.parametrize('field',['scene_index','tracking_segment','target_id','pose_track_start'])
def test_context_cannot_cross_identity_scene_or_missing_pose_boundary(tmp_path,field):
    packet,review,_=sequence(tmp_path);review['frames'][3][field]=99
    with pytest.raises(ValueError,match='boundary'):make_plan(packet,review)

def test_torso_requests_do_not_trigger_unapproved_body_replacement(tmp_path):
    packet,review,_=sequence(tmp_path);review['repair_requests'][0]['part']='torso'
    assert make_plan(packet,review)['inference_count']==0

def prepared(tmp_path,requested=False):
    source,folder,selection,raw,_=candidate_fixture(tmp_path)
    packet,_=ensure_fullbody(folder,source,selection,raw,digest(source));review,_=ensure_joint_review(folder,source,packet,digest(source))
    data=json.loads(review.read_text(encoding='utf-8'));data['repair_requests']=[]
    if requested:data['repair_requests']=[{'part':'left_leg','start':1,'end_exclusive':2,'context_start':0,'context_end_exclusive':3,
        'target_id':1,'tracking_segment':0,'scene_index':0,'pose_track_start':0}]
    write(review,data)
    return source,folder,selection,raw,review

def test_no_request_job_never_loads_gpu_and_cache_tracks_review_hash(tmp_path,monkeypatch):
    import app.part_reestimate_job as job
    source,folder,selection,raw,review=prepared(tmp_path)
    monkeypatch.setattr(job,'gpu_child',lambda *a:pytest.fail('no inference required'))
    before=digest(folder/'sam3d.json');out,report=run_part_reestimation(folder,source,selection,review)
    assert report['inference_count']==0 and report['changed_frames']==[] and before==digest(folder/'sam3d.json')
    assert latest_part_result(folder,digest(source),selection,review)==out
    data=json.loads(review.read_text(encoding='utf-8'));data['extra']='invalidate';write(review,data)
    assert latest_part_result(folder,digest(source),selection,review) is None

def test_requested_job_runs_only_planned_frame_and_variant(tmp_path,monkeypatch):
    import app.part_reestimate_job as job
    source,folder,selection,raw,review=prepared(tmp_path,True);calls=[]
    def child(script,out,*args):
        req=json.loads((out/'request.json').read_text(encoding='utf-8'));calls.append(req['leg_rois'])
        q=raw['frames'][1]['outputs'];write(out/'candidates.json',{'joint_names':None,'frames':[{'frame_index':1,
            'candidates':{'leg-context':{'world_joints':q['pred_keypoints_3d'],'image_joints':q['pred_keypoints_2d']}}}]})
    monkeypatch.setattr(job,'gpu_child',child)
    out,report=run_part_reestimation(folder,source,selection,review)
    assert list(calls[0])==['1'] and report['inference_count']==1
    assert (out/'part-joints.json').is_file() and report['status']=='completed_with_estimates'

def test_stale_selected_pose_is_rejected_before_gpu(tmp_path):
    source,folder,selection,raw,review=prepared(tmp_path)
    path=selection/'selected-joints.json';data=json.loads(path.read_text(encoding='utf-8'));data['extra']='changed';write(path,data)
    with pytest.raises(ValueError,match='provenance'):run_part_reestimation(folder,source,selection,review)

def test_cancellation_does_not_publish_complete_result(tmp_path,monkeypatch):
    import app.part_reestimate_job as job
    source,folder,selection,raw,review=prepared(tmp_path,True)
    def cancelled(*a):raise KeyboardInterrupt
    monkeypatch.setattr(job,'gpu_child',cancelled)
    with pytest.raises(KeyboardInterrupt):run_part_reestimation(folder,source,selection,review)
    out=next(folder.glob('parts_*'))
    assert json.loads((out/'report.json').read_text(encoding='utf-8'))['status']=='cancelled'
    assert not (out/'part-joints.json').exists() and latest_part_result(folder,digest(source),selection,review) is None
