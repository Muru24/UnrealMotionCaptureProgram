import copy,json
from types import SimpleNamespace as NS
import cv2,numpy as np,pytest
from core.motion.skeleton import AXIS,MHR,definition,convert


def sample_raw(count=4):
    rest={b['name']:np.array(b['head'],float) for b in definition()['bones']}
    q=np.zeros((70,3));names=[f'unused{i}' for i in range(70)]
    for i,name in MHR.items():names[i]=name
    points={5:'upperarm_l',6:'upperarm_r',7:'lowerarm_l',8:'lowerarm_r',62:'hand_l',41:'hand_r',
            9:'thigh_l',10:'thigh_r',11:'calf_l',12:'calf_r',13:'foot_l',14:'foot_r',69:'neck_01',
            15:'ball_l',16:'ball_l',18:'ball_r',19:'ball_r'}
    for i,name in points.items():q[i]=AXIS.T@rest[name]
    for i in (1,2,3,4):q[i]=AXIS.T@np.array([(-1 if i%2 else 1)*.03,-.03,1.68])
    frames=[{'frame_index':i,'timestamp':i/30,'roi':[0,0,160,120],'person_bbox':[0,0,160,120],
             'tracking':{'state':'tracked','track_id':1},'tracking_segment':0,
             'outputs':{'pred_keypoints_3d':q.tolist(),'pred_keypoints_2d':np.full((70,2),50.).tolist()}} for i in range(count)]
    return {'schema':'sam3d_mhr70','joint_names':names,'video':{'fps':30,'width':160,'height':120},'frames':frames}


def test_reference_parents_roles_and_nonzero_lengths():
    d=definition();b=d['bones'];assert len(b)==22 and b[0]['name']=='root'
    assert len({v['unity_role'] for v in b if v['unity_role']})==21
    assert all(np.linalg.norm(np.subtract(v['tail'],v['head']))>0 for v in b)


def test_axis_handedness_fixed_lengths_no_rotations_and_no_input_mutation():
    raw=sample_raw();before=copy.deepcopy(raw);out=convert(raw)
    assert raw==before and out['root_motion'] is False and out['bone_rotations'] is None
    np.testing.assert_allclose(AXIS@AXIS.T,np.eye(3));assert np.linalg.det(AXIS)==pytest.approx(1)
    bones=out['skeleton']['bones'];names=[b['name'] for b in bones]
    for row in out['frames']:
        assert all(v is not None for v in row['positions'])
        for i,b in enumerate(bones):
            if b['parent']:
                j=names.index(b['parent']);want=np.linalg.norm(np.subtract(b['head'],bones[j]['head']))
                assert np.linalg.norm(np.subtract(row['positions'][i],row['positions'][j]))==pytest.approx(want)
    left=names.index('hand_l');right=names.index('hand_r')
    assert out['frames'][0]['positions'][left][0]>out['frames'][0]['positions'][right][0]


def test_camera_translation_is_removed_not_inferred_as_root_motion():
    raw=sample_raw();a=convert(raw)
    for r in raw['frames']:r['outputs']['pred_keypoints_3d']=(np.asarray(r['outputs']['pred_keypoints_3d'])+[3,4,5]).tolist()
    b=convert(raw)
    np.testing.assert_allclose(a['frames'][0]['positions'],b['frames'][0]['positions'],atol=1e-8)
    assert a['frames'][0]['source_pelvis_camera_m']!=b['frames'][0]['source_pelvis_camera_m']


def test_prefix_and_lost_frames_remain_empty_and_keep_timestamps():
    raw=sample_raw();raw['frames'][0].update(outputs=None,roi=None,tracking={'state':'uninitialized'})
    raw['frames'][2]['tracking']['state']='lost';out=convert(raw)
    for i in (0,2):assert all(v is None for v in out['frames'][i]['positions'])
    assert out['frames'][3]['timestamp']==.1 and all(v is not None for v in out['frames'][3]['positions'])


def test_partial_nonfinite_source_does_not_invent_missing_hand():
    raw=sample_raw();raw['frames'][0]['outputs']['pred_keypoints_3d'][62]=[float('nan')]*3
    data=convert(raw);i=[b['name'] for b in data['skeleton']['bones']].index('hand_l')
    assert data['frames'][0]['positions'][i] is None
    json.dumps(data,allow_nan=False)


def test_sidecar_used_and_changes_are_attributed():
    raw=sample_raw();rows=[{'frame_index':i,'world_joints':copy.deepcopy(r['outputs']['pred_keypoints_3d']),
                         'changed_parts':[{'part':'left_arm'}]} for i,r in enumerate(raw['frames'])]
    rows[0]['world_joints'][62][2]+=.2
    out=convert(raw,rows,source_kind='part_estimates')
    assert out['source_kind']=='part_estimates' and out['frames'][0]['source_changes']==[{'part':'left_arm'}]
    assert out['frames'][0]['positions']!=convert(raw)['frames'][0]['positions']


def test_wrong_schema_order_timeline_and_cancel_are_rejected():
    raw=sample_raw();raw['joint_names'][62]='wrong'
    with pytest.raises(ValueError,match='schema'):convert(raw)
    raw=sample_raw();raw['frames'][1]['frame_index']=8
    with pytest.raises(ValueError,match='order'):convert(raw)
    with pytest.raises(KeyboardInterrupt):convert(sample_raw(),cancelled=lambda:True)


def job_fixture(tmp_path):
    from app.knee_job import digest
    source=tmp_path/'source.mp4';w=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*'mp4v'),30,(160,120))
    for _ in range(4):w.write(np.full((120,160,3),80,np.uint8))
    w.release();folder=tmp_path/'run';folder.mkdir();raw=sample_raw()
    for name,data in [('sam3d.json',raw),('report.json',{'status':'completed','frames_processed':4}),
                      ('sam-request.json',{'source':str(source),'source_sha256':digest(source)})]:
        (folder/name).write_text(json.dumps(data),encoding='utf-8')
    return source,folder


def test_job_cache_cancel_input_change_and_raw_preservation(tmp_path):
    from app.motion_job import ensure_motion
    source,folder=job_fixture(tmp_path);before=(folder/'sam3d.json').read_bytes()
    path,state=ensure_motion(folder,source);assert state=='computed'
    assert ensure_motion(folder,source)[1]=='reused'
    assert before==(folder/'sam3d.json').read_bytes()
    source.write_bytes(source.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='변경'):ensure_motion(folder,source)


def test_cancel_does_not_publish_and_foreign_sidecar_is_rejected(tmp_path):
    from app.motion_job import ensure_motion
    source,folder=job_fixture(tmp_path)
    with pytest.raises(KeyboardInterrupt):ensure_motion(folder,source,cancelled=lambda:True)
    assert not (folder/'motion').exists()
    with pytest.raises(ValueError,match='belong'):ensure_motion(folder,source,{'part_result_directory':tmp_path})


def test_sidecar_provenance_must_match_and_cache_can_recover(tmp_path):
    from app.motion_job import ensure_motion
    source,folder=job_fixture(tmp_path);side=folder/'parts';side.mkdir()
    (side/'part-joints.json').write_text(json.dumps({'source_sha256':'wrong','raw_sha256':'wrong','frames':[]}),encoding='utf-8')
    with pytest.raises(ValueError,match='provenance'):ensure_motion(folder,source,{'part_result_directory':side})
    path,_=ensure_motion(folder,source);(path.parent/'report.json').write_text('{broken',encoding='utf-8')
    assert ensure_motion(folder,source)[1]=='computed'


def test_gui_paired_skeleton_seek_clear_and_orbit(tmp_path):
    from tkinterdnd2 import TkinterDnD
    from app.gui import PrototypeApp
    from app.motion_job import ensure_motion
    source,folder=job_fixture(tmp_path);ensure_motion(folder,source)
    root=TkinterDnD.Tk();root.withdraw();app=PrototypeApp(root)
    try:
        app.result_dir=folder;app.source=source;app.open_video(source)
        assert app.skeleton_panel.points.shape==(4,22,3)
        app.seek_var.set(2);app.seek_end();assert app.skeleton_panel.position==app.position==2
        yaw=app.skeleton_panel.yaw;app.skeleton_panel.drag=(0,0)
        app.skeleton_panel.orbit(NS(x=20,y=10));assert app.skeleton_panel.yaw!=yaw
        app.skeleton_panel.clear();assert app.skeleton_panel.points is None
    finally:app.stop_video();root.destroy()


def test_gui_output_automatically_builds_and_loads_motion(tmp_path,monkeypatch):
    import shutil
    import app.gui as gui
    import app.automatic_postprocess as auto
    from tkinterdnd2 import TkinterDnD
    from test_gui import pump
    source,fixture=job_fixture(tmp_path);out=tmp_path/'new_result'
    def run(source_arg,output,*args,**kwargs):
        shutil.copytree(fixture,output);shutil.copyfile(source,output/'overlay.mp4')
        return {'frames_processed':4,'frames_with_target':4,'warnings':[]}
    monkeypatch.setattr(gui,'run_job',run);monkeypatch.setattr(gui,'new_output',lambda *a,**k:out)
    monkeypatch.setattr(auto,'process_sam_result',lambda *a,**k:{'automatic_postprocess':{'status':'completed_with_estimates'}})
    root=TkinterDnD.Tk();root.withdraw();app=gui.PrototypeApp(root)
    try:
        app.load_source(source);pump(root,lambda:not app.busy)
        app.start();pump(root,lambda:not app.busy)
        assert (out/'motion/motion.json').is_file()
        assert app.skeleton_panel.points.shape==(4,22,3)
        assert app.skeleton_panel.position==app.position
    finally:app.stop_video();root.destroy()
