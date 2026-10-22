import copy,json
import numpy as np
import pytest
from core.pose3d.fullbody_candidates import build_packet
from core.pose3d.joint_review import review_joints
from app.joint_review_job import ensure_joint_review,mask_evidence
from app.fullbody_job import ensure_fullbody
from app.knee_job import digest
from test_knee_job import candidate_fixture

def neutral_packet(n=9):
    q=np.zeros((70,3));q[5]=[-.2,-.4,0];q[6]=[.2,-.4,0];q[69]=[0,-.5,0]
    for a,b,x,y in ((7,8,.35,-.2),(62,41,.4,0),(9,10,.1,0),(11,12,.1,.3),(13,14,.1,.6)):
        q[a]=[-x,y,0];q[b]=[x,y,0]
    for i in (15,16,17):q[i]=q[13]
    for i in (18,19,20):q[i]=q[14]
    p=q[:,:2]*100+[160,100];frames=[];variants={};selected=[]
    for i in range(n):
        pose={'world_joints':q.tolist(),'image_joints':p.tolist()}
        frames.append({'frame_index':i,'tracking_segment':0,'tracking':{'state':'tracked','track_id':1},
            'person_bbox':[50,20,270,230],'roi':[40,10,280,240],
            'outputs':{'pred_keypoints_3d':q.tolist(),'pred_keypoints_2d':p.tolist()}})
        variants[i]={name:copy.deepcopy(pose) for name in ('observed','tight','stable-flip')}
        selected.append({'frame_index':i,'candidate':'stable',**copy.deepcopy(pose)})
    raw={'target_id':1,'video':{'fps':30,'width':320,'height':240},'frames':frames}
    return build_packet(raw,variants,selected)

def reasons(report,i,j):return report['frames'][i]['joints'][j]['reasons']

def test_constant_pose_is_unverified_and_diagnostics_do_not_modify_inputs():
    packet=neutral_packet();before=copy.deepcopy(packet);r=review_joints(packet)
    assert r['summary']['review_frames']==0 and r['repair_requests']==[] and packet==before
    assert r['frames'][4]['joints'][13]['state']=='model_estimate_unverified'
    assert r['frames'][4]['joints'][13]['mask_evidence_status']=='unknown'
    assert r['frames'][0]['joints'][13]['trajectory_id']==r['frames'][4]['joints'][13]['trajectory_id']
    assert r['frames'][4]['joints'][13]['metrics']['forward_velocity_torso_per_second']==[0.,0.,0.]

def test_spike_is_flagged_by_bidirectional_motion_and_bone_lengths():
    packet=neutral_packet();packet['frames'][4]['candidates']['stable']['world_joints'][11][0]+=1
    r=review_joints(packet)
    assert {'temporal_inconsistency','bone_length_change'}<=set(reasons(r,4,11))
    assert 'left_leg' in r['frames'][4]['review_parts']
    assert any(w['part']=='left_leg' and w['start']<=4<w['end_exclusive'] for w in r['repair_requests'])

def test_left_right_swap_is_only_a_review_flag():
    packet=neutral_packet();pose=packet['frames'][4]['candidates']['stable'];a,b=62,41
    pose['world_joints'][a],pose['world_joints'][b]=pose['world_joints'][b],pose['world_joints'][a]
    before=copy.deepcopy(packet);r=review_joints(packet)
    assert 'left_right_swap_suspected' in reasons(r,4,a) and packet==before

def test_camera_translation_does_not_create_local_joint_motion_flags():
    packet=neutral_packet()
    for i,row in enumerate(packet['frames']):
        for pose in row['candidates'].values():pose['world_joints']=(np.asarray(pose['world_joints'])+i*.03).tolist()
    r=review_joints(packet)
    assert r['summary']['review_frames']==0

@pytest.mark.parametrize('boundary',['scene','segment','missing','target'])
def test_temporal_checks_and_requests_never_cross_boundaries(boundary):
    packet=neutral_packet()
    for row in packet['frames'][4:]:
        if boundary=='scene':row['scene_index']=1
        if boundary=='segment':row['tracking_segment']=1
        if boundary=='target':row['target_id']=2
    if boundary=='missing':packet['frames'][3]['selected_candidate']=None
    packet['frames'][4]['candidates']['stable']['world_joints'][11][0]+=1
    r=review_joints(packet)
    assert 'temporal_inconsistency' not in reasons(r,4,11)
    assert not r['frames'][4]['joints'][11]['temporal_context_available']
    assert r['frames'][2]['joints'][11]['trajectory_id']!=r['frames'][4]['joints'][11]['trajectory_id']
    assert all(w['context_start']>=4 for w in r['repair_requests'] if w['start']>=4)

def test_one_poor_augmentation_does_not_veto_agreeing_candidates():
    packet=neutral_packet()
    packet['frames'][4]['candidates']['tight']['world_joints'][11][0]+=4
    assert 'candidate_disagreement' not in reasons(review_joints(packet),4,11)

def test_disagreeing_majority_is_preserved_as_evidence():
    packet=neutral_packet()
    for name in ('observed','tight','stable-flip'):packet['frames'][4]['candidates'][name]['world_joints'][11][0]+=.4
    assert 'candidate_disagreement' in reasons(review_joints(packet),4,11)

def test_mask_support_is_evidence_not_joint_accuracy():
    packet=neutral_packet();evidence={4:{'status':'available','distances':[0.]*70,'tolerance_pixels':3}}
    evidence[4]['distances'][13]=20
    r=review_joints(packet,evidence)
    assert reasons(r,4,13)==['outside_person_mask']
    assert r['frames'][4]['joints'][12]['state']=='model_estimate_unverified'

def test_outside_frame_is_not_reported_as_observed_joint():
    packet=neutral_packet();pose=packet['frames'][4]['candidates']['stable']
    pose['joint_inside_frame'][13]=False;pose['image_joints'][13]=[-20,100]
    r=review_joints(packet)
    assert r['frames'][4]['joints'][13]['state']=='outside_frame'
    assert r['frames'][4]['joints'][13]['image_position']==[-20,100]

def test_constant_systematic_model_error_cannot_be_certified_correct():
    packet=neutral_packet()
    for row in packet['frames']:
        for pose in row['candidates'].values():
            for j in (11,12,13,14):pose['world_joints'][j][1]*=.3
    r=review_joints(packet)
    assert r['summary']['review_frames']==0
    assert r['frames'][4]['joints'][13]['state']=='model_estimate_unverified'

def prepared(tmp_path):
    source,folder,selection,raw,_=candidate_fixture(tmp_path)
    packet,_=ensure_fullbody(folder,source,selection,raw,digest(source))
    return source,folder,selection,packet

def test_job_publishes_preview_and_requests_reuses_matching_inputs(tmp_path):
    source,folder,selection,packet=prepared(tmp_path);before=digest(folder/'sam3d.json')
    path,state=ensure_joint_review(folder,source,packet,digest(source))
    assert state=='computed' and (selection/'joint-review.mp4').is_file()
    assert (selection/'joint-repair-requests.json').is_file()
    assert ensure_joint_review(folder,source,packet,digest(source))[1]=='reused'
    assert digest(folder/'sam3d.json')==before

def test_mask_paths_cannot_read_outside_output_root(tmp_path):
    source,folder,selection,packet_path=prepared(tmp_path);packet=json.loads(packet_path.read_text(encoding='utf-8'))
    plan={'frames':[{'frame_index':i,'tracking':{'state':'tracked','track_id':1},'mask':{'file':'../private.png'}} for i in range(3)]}
    (folder/'sam-tracking.json').write_text(json.dumps(plan),encoding='utf-8')
    evidence,manifest,_=mask_evidence(folder,packet,lambda:False)
    assert all(e['status']=='invalid_mask_path' for e in evidence.values()) and not manifest

def test_mismatched_mask_timeline_is_rejected(tmp_path):
    source,folder,selection,packet=prepared(tmp_path)
    (folder/'sam-tracking.json').write_text(json.dumps({'frames':[]}),encoding='utf-8')
    with pytest.raises(ValueError,match='timeline'):ensure_joint_review(folder,source,packet,digest(source))

def test_review_cancel_preserves_previous_complete_files(tmp_path):
    source,folder,selection,packet=prepared(tmp_path);source_hash=digest(source)
    path,_=ensure_joint_review(folder,source,packet,source_hash)
    frozen={p:digest(p) for p in (path,selection/'joint-review.mp4')}
    data=json.loads(packet.read_text(encoding='utf-8'));data['extra']='invalidate cache';packet.write_text(json.dumps(data),encoding='utf-8')
    state=[False]
    with pytest.raises(KeyboardInterrupt):ensure_joint_review(folder,source,packet,source_hash,lambda:state[0],lambda *a:state.__setitem__(0,True))
    assert all(digest(p)==h for p,h in frozen.items()) and not (selection/'joint-review.partial.mp4').exists()

def test_real_mask_distance_and_mask_content_invalidate_cache(tmp_path):
    import cv2
    source,folder,selection,packet=prepared(tmp_path);masks=folder/'masks';masks.mkdir()
    mask=np.zeros((240,320),np.uint8);mask[:180,80:240]=255
    for i in range(3):(masks/f'{i}.png').write_bytes(cv2.imencode('.png',mask)[1].tobytes())
    plan={'frames':[{'frame_index':i,'tracking':{'state':'tracked','track_id':1},'mask':{'file':f'masks/{i}.png'}} for i in range(3)]}
    (folder/'sam-tracking.json').write_text(json.dumps(plan),encoding='utf-8')
    path,_=ensure_joint_review(folder,source,packet,digest(source));r=json.loads(path.read_text(encoding='utf-8'))
    assert 'outside_person_mask' in reasons(r,0,13) and r['summary']['mask_available_frames']==3
    (masks/'1.png').write_bytes(cv2.imencode('.png',np.zeros_like(mask))[1].tobytes())
    assert ensure_joint_review(folder,source,packet,digest(source))[1]=='computed'
    assert json.loads(path.read_text(encoding='utf-8'))['summary']['mask_available_frames']==2

def test_failed_review_does_not_run_legacy_leg_stage(tmp_path,monkeypatch):
    import app.automatic_postprocess as auto
    source,folder,selection,_,_=candidate_fixture(tmp_path)
    def fail(*a):raise ValueError('joint evidence mismatch')
    monkeypatch.setattr(auto,'ensure_joint_review',fail)
    monkeypatch.setattr(auto,'run_part_reestimation',lambda *a:pytest.fail('must preserve completed earlier stages'))
    result=auto.process_sam_result(folder,source)
    assert result['automatic_postprocess']['stages']['joint_review']=='failed'
    assert result['candidate_selection_directory']==str(selection) and result.get('fullbody_candidates_file')
