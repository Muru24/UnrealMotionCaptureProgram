import copy
import numpy as np
import pytest
from test_part_reestimation import sequence,prepared
from core.pose3d.part_reestimation import combine,make_plan,editable_joints
from core.pose3d.reconnection import reconnect
from app.reconnection_job import ensure_reconnection
from app.part_reestimate_job import run_part_reestimation

def sample(tmp_path):
    packet,review,fresh=sequence(tmp_path)
    rows,_=combine(packet,review,make_plan(packet,review),fresh)
    # A small checked reappearance offset; requests are supplied independently.
    for r in review['frames']:r['review_parts']=[]
    q=np.asarray(rows[4]['world_joints']);q[11,0]+=.01
    rows[4]['world_joints']=q.tolist()
    return packet,review,{'frames':rows}

def test_checked_transition_preserves_body_lengths_and_final_observation(tmp_path):
    packet,review,parts=sample(tmp_path);before=copy.deepcopy(parts)
    rows,report=reconnect(packet,review,parts)
    assert report['events'][0]['accepted'] and report['changed_frames']==[5,6]
    for i in (5,6):
        q=np.asarray(rows[i]['world_joints']);b=np.asarray(parts['frames'][i]['world_joints'])
        fixed=[j for j in range(70) if j not in editable_joints('left_leg')]
        np.testing.assert_array_equal(q[fixed],b[fixed])
        for a,c in ((9,11),(11,13)):assert np.linalg.norm(q[c]-q[a])==pytest.approx(np.linalg.norm(b[c]-b[a]))
    assert rows[7]['world_joints']==parts['frames'][7]['world_joints'] and parts==before

@pytest.mark.parametrize('field',['target_id','tracking_segment','scene_index','pose_track_start'])
def test_never_connects_across_boundary(tmp_path,field):
    p,r,d=sample(tmp_path);r['frames'][5][field]=999
    rows,report=reconnect(p,r,d);assert not report['changed_frames'] and report['events'][0]['reason']=='track_boundary_or_missing_body'

def test_missing_body_is_not_filled(tmp_path):
    p,r,d=sample(tmp_path);d['frames'][5]['world_joints']=None;d['frames'][5]['image_joints']=None
    rows,report=reconnect(p,r,d);assert rows[5]['world_joints'] is None and not report['changed_frames']

@pytest.mark.parametrize('mode',['review','mask','jump','length'])
def test_conflicting_observations_do_not_commit_partial_path(tmp_path,mode):
    p,r,d=sample(tmp_path)
    if mode=='review':r['frames'][6]['review_parts']=['left_leg']
    if mode=='jump':
        q=np.asarray(d['frames'][6]['world_joints']);q[[11,13],0]+=2;d['frames'][6]['world_joints']=q.tolist()
    if mode=='length':
        q=np.asarray(d['frames'][6]['world_joints']);q[13]=q[11]+(q[13]-q[11])*1.5;d['frames'][6]['world_joints']=q.tolist()
    rows,report=reconnect(p,r,d,lambda i,p:2 if mode=='mask' and i==6 else 0)
    assert not report['changed_frames'] and not report['events'][0]['accepted']

def test_timeline_and_cancel(tmp_path):
    p,r,d=sample(tmp_path)
    with pytest.raises(KeyboardInterrupt):reconnect(p,r,d,cancelled=lambda:True)
    d['frames'][2]['frame_index']=99
    with pytest.raises(ValueError,match='order'):reconnect(p,r,d)

def test_job_cache_and_stale_parts(tmp_path):
    source,folder,selection,raw,review=prepared(tmp_path)
    parts,_=run_part_reestimation(folder,source,selection,review)
    out,state=ensure_reconnection(folder,source,selection,review,parts)
    assert state=='computed'
    assert ensure_reconnection(folder,source,selection,review,parts)==(out,'reused')
    import json
    path=parts/'part-joints.json';data=json.loads(path.read_text());data['review_sha256']='stale';path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='provenance'):ensure_reconnection(folder,source,selection,review,parts)

def test_reconnection_failure_keeps_part_result(tmp_path,monkeypatch):
    import app.automatic_postprocess as auto
    from test_knee_job import candidate_fixture
    source,folder,selected,_,_=candidate_fixture(tmp_path)
    parts=folder/'parts_stub';parts.mkdir()
    monkeypatch.setattr(auto,'latest_part_result',lambda *a:parts)
    def fail(*a):raise ValueError('reappearance conflict')
    monkeypatch.setattr(auto,'ensure_reconnection',fail)
    result=auto.process_sam_result(folder,source)
    assert result['part_result_directory']==str(parts)
    assert result['automatic_postprocess']['stages']['reconnection']=='failed'
    assert result['automatic_postprocess']['status']=='partial'

def test_cancel_job_does_not_publish_completion(tmp_path):
    source,folder,selection,raw,review=prepared(tmp_path)
    parts,_=run_part_reestimation(folder,source,selection,review)
    with pytest.raises(KeyboardInterrupt):ensure_reconnection(folder,source,selection,review,parts,cancelled=lambda:True)
    assert not list(folder.glob('reconnect_*'))
