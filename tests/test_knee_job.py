import json,cv2,numpy as np,pytest
from app.knee_job import run_knee_correction,digest,target_at
from core.pose3d.manual_leg_geometry import project


def fixture(tmp_path):
    source=tmp_path/'input.mp4';writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*'mp4v'),30,(320,240))
    for i in range(3):writer.write(np.zeros((240,320,3),np.uint8))
    writer.release();rng=np.random.default_rng(2);q=rng.uniform(-.1,.1,(70,3))
    q[5]=[-.2,-.4,0];q[6]=[.2,-.4,0];q[9]=[-.1,0,0];q[10]=[.1,0,0]
    q[11]=[-.3,.3,0];q[12]=[.3,.3,0];q[13]=[-.1,.6,0];q[14]=[.1,.6,0]
    cam={'focal':600.,'translation':[0,-.1,4.],'center':[160.,120.]};p=project(q,cam)
    frames=[{'frame_index':i,'tracking_segment':0,'person_bbox':[0,0,320,240],
             'outputs':{'pred_keypoints_3d':q.tolist(),'pred_keypoints_2d':p.tolist()}} for i in range(3)]
    folder=tmp_path/'run';folder.mkdir()
    def save(n,d):(folder/n).write_text(json.dumps(d),encoding='utf-8')
    save('sam-request.json',{'source':str(source),'source_sha256':digest(source)})
    save('report.json',{'status':'completed_with_warnings','frames_processed':3})
    save('sam3d.json',{'schema':'sam3d_mhr70','video':{'width':320,'height':240,'fps':30},'frames':frames})
    return source,folder,q,p,cam


def test_job_preserves_raw_and_projects_manual_knee(tmp_path):
    source,folder,q,p,cam=fixture(tmp_path);before=(folder/'sam3d.json').read_bytes()
    desired=q[11].copy();desired[0]=.1;target=project(desired[None],cam)[0]
    out,report=run_knee_correction(folder,source,{1:{'left_knee':target.tolist(),'left_ankle':p[13].tolist()}})
    assert report['status']=='completed_with_estimates' and report['extraction_source_hash_verified']
    assert report['anchor_results'][0]['error_pixels']<20
    assert before==(folder/'sam3d.json').read_bytes()
    rows=json.loads((out/'knee-joints.json').read_text())['frames'];frozen=[j for j in range(70) if j not in range(11,21)]
    for row in rows:np.testing.assert_array_equal(np.array(row['world_joints'])[frozen],q[frozen])
    for name in ('knee-overlay.mp4','knee3d.mp4'):
        cap=cv2.VideoCapture(str(out/name));count=0
        while cap.read()[0]:count+=1
        cap.release();assert count==3


def test_modified_source_rejected(tmp_path):
    source,folder,*_=fixture(tmp_path);source.write_bytes(source.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='변경'):run_knee_correction(folder,source,{1:{'left_knee':[100,100]}})


def test_manual_anchor_on_missing_frame_reported(tmp_path):
    source,folder,*_=fixture(tmp_path);path=folder/'sam3d.json';raw=json.loads(path.read_text());raw['frames'][1]['outputs']=None;path.write_text(json.dumps(raw))
    _,report=run_knee_correction(folder,source,{1:{'left_knee':[100,100]}})
    assert report['anchor_results'][0]['status']=='unresolved'


def test_no_interpolation_across_scene_or_tracking_loss():
    a={0:{'left_knee':[10,10]},2:{'left_knee':[20,20]}}
    assert target_at(a,1,'left_knee',[(0,0),None,(0,0)])[0] is None
    assert target_at(a,1,'left_knee',[(0,0),(1,0),(1,0)])[0] is None
    np.testing.assert_array_equal(target_at(a,1,'left_knee',[(0,0)]*3)[0],[15,15])


def test_cancel_before_result_creation(tmp_path):
    source,folder,*_=fixture(tmp_path)
    with pytest.raises(KeyboardInterrupt):run_knee_correction(folder,source,{1:{'left_knee':[100,100]}},lambda:True)
    assert not list(folder.glob('knee_*'))




def candidate_fixture(tmp_path):
    from app.candidate_job import save_selection
    source,folder,q,p,cam=fixture(tmp_path);raw=json.loads((folder/'sam3d.json').read_text())
    variants={i:{name:{'world_joints':q.tolist(),'image_joints':p.tolist()} for name in ('observed','tight','stable-flip')} for i in range(3)}
    out=folder/'candidates_test';out.mkdir();save_selection(out,source,raw,variants)
    return source,folder,out,raw,variants


def test_candidate_selection_preserves_raw_and_produces_complete_timeline(tmp_path):
    source,folder,out,raw,variants=candidate_fixture(tmp_path)
    data=json.loads((out/'selected-joints.json').read_text())
    assert data['schema']=='candidate_joint_selection_not_mhr_animation'
    assert data['raw_sha256']==digest(folder/'sam3d.json')
    assert len(data['frames'])==3 and not any('outputs' in r for r in data['frames'])


def test_knee_correction_uses_selected_baseline(tmp_path):
    source,folder,out,raw,_=candidate_fixture(tmp_path)
    path=out/'selected-joints.json';data=json.loads(path.read_text());data['frames'][1]['world_joints'][0][0]+=.01;path.write_text(json.dumps(data))
    result,report=run_knee_correction(folder,source,{1:{'left_knee':raw['frames'][1]['outputs']['pred_keypoints_2d'][11]}},selection=out)
    rows=json.loads((result/'knee-joints.json').read_text())['frames']
    assert rows[1]['world_joints'][0][0]==data['frames'][1]['world_joints'][0][0]
    assert report['candidate_selection_input']==str(out)


def test_wrong_raw_selection_is_rejected(tmp_path):
    source,folder,out,_,_=candidate_fixture(tmp_path);path=out/'selected-joints.json';data=json.loads(path.read_text());data['raw_sha256']='wrong';path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='원본'):run_knee_correction(folder,source,{1:{'left_knee':[100,100]}},selection=out)


def test_missing_candidates_preserve_raw(tmp_path):
    from app.candidate_job import choose
    source,folder,*_=fixture(tmp_path);raw=json.loads((folder/'sam3d.json').read_text());rows,ranks=choose(raw,{})
    assert not ranks and all(r['candidate']=='raw' for r in rows)


def test_candidate_ranking_splits_loss_and_scene(tmp_path):
    from app.candidate_job import choose
    _,_,_,raw,variants=candidate_fixture(tmp_path)
    raw['frames'][1]['outputs']=None
    rows,ranks=choose(raw,variants)
    assert rows[1]['world_joints'] is None
    assert [(r['start'],r['end_exclusive']) for r in ranks]==[(0,1),(2,3)]
    raw['frames'][1]['outputs']=raw['frames'][0]['outputs'];raw['frames'][1]['scene']={'index':1};raw['frames'][2]['scene']={'index':1}
    _,ranks=choose(raw,variants)
    assert [(r['start'],r['end_exclusive']) for r in ranks]==[(0,1),(1,3)]


def test_reopen_finds_only_matching_completed_selection(tmp_path):
    from app.candidate_job import latest_selection
    source,folder,out,_,_=candidate_fixture(tmp_path)
    assert latest_selection(folder,digest(source))==out
    assert latest_selection(folder,'wrong') is None
    (out/'report.json').write_text(json.dumps({'status':'cancelled'}))
    assert latest_selection(folder,digest(source)) is None




