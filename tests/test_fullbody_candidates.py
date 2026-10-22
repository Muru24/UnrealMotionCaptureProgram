import json,copy
import numpy as np
import pytest
from test_knee_job import candidate_fixture
from app.knee_job import digest
from app.fullbody_job import ensure_fullbody
from core.pose3d.fullbody_candidates import build_packet

def packet_fixture(tmp_path):
    source,folder,selection,raw,variants=candidate_fixture(tmp_path)
    selected=json.loads((selection/'selected-joints.json').read_text(encoding='utf-8'))['frames']
    return source,folder,selection,raw,variants,selected

def test_four_hypotheses_keep_original_70_joints_and_derived_axis(tmp_path):
    _,_,_,raw,variants,selected=packet_fixture(tmp_path);before=copy.deepcopy(raw)
    packet=build_packet(raw,variants,selected)
    row=packet['frames'][0];pose=row['candidates']['stable'];p=np.array(pose['world_joints'])
    assert len(row['candidates'])==4 and row['selected_candidate'] is not None
    np.testing.assert_allclose(pose['references_world']['pelvis_center'],p[[9,10]].mean(axis=0))
    np.testing.assert_allclose(pose['references_world']['spine_axis_proxy'][1],p[[5,6]].mean(axis=0))
    assert raw==before and packet['joint_layout']=='MHR70'
    assert pose['accuracy_confidence'] is None and pose['visibility'] is None
    assert row['candidates']['stable-flip']['input_transform']=='horizontal_flip'
    assert row['candidates']['stable-flip']['input_roi_coordinates']=='flipped_image_pixels'

@pytest.mark.parametrize('reason',['no_outputs','predicted','different_id','lost'])
def test_unavailable_target_never_gets_a_pose_from_other_candidates(tmp_path,reason):
    _,_,_,raw,variants,selected=packet_fixture(tmp_path);r=raw['frames'][1]
    if reason=='no_outputs':r['outputs']=None
    if reason=='predicted':r['motion']={'prediction_only':True}
    if reason=='different_id':r['tracking']={'track_id':2,'state':'tracked'}
    if reason=='lost':r['tracking']={'state':'lost'}
    packet=build_packet(raw,variants,selected)
    assert packet['frames'][1]['candidates']=={} and packet['frames'][1]['status']=='target_unavailable'
    assert len(packet['frames'])==3

def test_outside_frame_is_flagged_without_claiming_occlusion(tmp_path):
    _,_,_,raw,variants,selected=packet_fixture(tmp_path)
    variants[0]['tight']['image_joints'][13]=[-30,400]
    pose=build_packet(raw,variants,selected)['frames'][0]['candidates']['tight']
    assert not pose['joint_inside_frame'][13] and pose['visibility'] is None
    assert pose['image_joints'][13]==[-30,400]

def test_missing_or_invalid_candidate_is_explicit_not_copied_from_baseline(tmp_path):
    _,_,_,raw,variants,selected=packet_fixture(tmp_path)
    del variants[0]['tight'];variants[0]['observed']['world_joints'][0][0]=float('nan')
    row=build_packet(raw,variants,selected)['frames'][0]
    assert set(row['candidates'])=={'stable','stable-flip'}
    assert row['unavailable_candidates']['observed']=='invalid_joint_array'
    assert row['unavailable_candidates']['tight']=='candidate_not_generated'

def test_edited_selection_is_not_mislabelled_as_a_candidate(tmp_path):
    _,_,_,raw,variants,selected=packet_fixture(tmp_path)
    selected[0]['world_joints'][0][0]+=1
    row=build_packet(raw,variants,selected)['frames'][0]
    assert row['selected_candidate'] is None and row['selected_pose_status']=='selected_pose_not_in_pool'

def test_export_reuses_only_matching_inputs_and_preserves_raw(tmp_path):
    source,folder,selection,raw,_,_=packet_fixture(tmp_path);before=(folder/'sam3d.json').read_bytes()
    path,state=ensure_fullbody(folder,source,selection,raw,digest(source))
    assert state=='computed' and json.loads(path.read_text(encoding='utf-8'))['summary']['frames_with_four_candidates']==3
    assert ensure_fullbody(folder,source,selection,raw,digest(source))[1]=='reused'
    assert before==(folder/'sam3d.json').read_bytes()
    file=selection/'candidates.json';data=json.loads(file.read_text(encoding='utf-8'));data['frames'][0]['candidates'].pop('tight');file.write_text(json.dumps(data),encoding='utf-8')
    assert ensure_fullbody(folder,source,selection,raw,digest(source))[1]=='computed'
    assert json.loads(path.read_text(encoding='utf-8'))['summary']['frames_with_four_candidates']==2

def test_cancel_does_not_publish_complete_packet(tmp_path):
    source,folder,selection,raw,_,_=packet_fixture(tmp_path)
    with pytest.raises(KeyboardInterrupt):ensure_fullbody(folder,source,selection,raw,digest(source),lambda:True)
    assert not (selection/'fullbody-candidates.json').exists()

def test_duplicate_candidate_timeline_is_rejected(tmp_path):
    source,folder,selection,raw,_,_=packet_fixture(tmp_path)
    file=selection/'candidates.json';data=json.loads(file.read_text(encoding='utf-8'));data['frames'].append(data['frames'][0]);file.write_text(json.dumps(data),encoding='utf-8')
    with pytest.raises(ValueError,match='timeline'):ensure_fullbody(folder,source,selection,raw,digest(source))

def test_mid_export_cancel_keeps_previous_complete_artifacts(tmp_path):
    source,folder,selection,raw,_,_=packet_fixture(tmp_path);source_hash=digest(source)
    packet,_=ensure_fullbody(folder,source,selection,raw,source_hash)
    frozen={p:digest(p) for p in (packet,selection/'fullbody-reference.mp4')}
    candidates=selection/'candidates.json';data=json.loads(candidates.read_text(encoding='utf-8'));data['frames'][0]['candidates'].pop('tight');candidates.write_text(json.dumps(data),encoding='utf-8')
    state=[False]
    with pytest.raises(KeyboardInterrupt):ensure_fullbody(folder,source,selection,raw,source_hash,lambda:state[0],lambda *a:state.__setitem__(0,True))
    assert all(digest(p)==h for p,h in frozen.items())
    assert not (selection/'fullbody-reference.partial.mp4').exists()

def test_changed_source_is_rejected_even_when_export_would_be_cached(tmp_path):
    source,folder,selection,raw,_,_=packet_fixture(tmp_path);source_hash=digest(source)
    ensure_fullbody(folder,source,selection,raw,source_hash)
    source.write_bytes(source.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='source changed'):ensure_fullbody(folder,source,selection,raw,source_hash)

def test_export_failure_preserves_selected_result_and_stops_later_stage(tmp_path,monkeypatch):
    import app.automatic_postprocess as auto
    source,folder,selection,_,_,_=packet_fixture(tmp_path)
    def fail(*a):raise ValueError('export failed')
    monkeypatch.setattr(auto,'ensure_fullbody',fail)
    monkeypatch.setattr(auto,'run_part_reestimation',lambda *a:pytest.fail('must not continue after failed handoff'))
    result=auto.process_sam_result(folder,source)
    assert result['candidate_selection_directory']==str(selection)
    assert result['automatic_postprocess']['stages']['fullbody_candidates']=='failed'
