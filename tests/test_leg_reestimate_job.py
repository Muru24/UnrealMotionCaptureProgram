import json,shutil,time
import cv2,numpy as np,pytest
from app.leg_reestimate_job import seed_shoes,leg_rois,run_leg_reestimation
from app.knee_job import digest
from test_knee_job import candidate_fixture

def prepared(tmp_path):
    source,folder,selection,raw,variants=candidate_fixture(tmp_path)
    raw['joint_names']=[str(i) for i in range(70)];(folder/'sam3d.json').write_text(json.dumps(raw))
    p=selection/'selected-joints.json';data=json.loads(p.read_text(encoding='utf-8'));data['raw_sha256']=digest(folder/'sam3d.json');p.write_text(json.dumps(data))
    return source,folder,selection,raw,data

def test_seed_shoes_uses_current_frame_and_rejects_overlap(tmp_path):
    _,_,_,raw,data=prepared(tmp_path);boots=seed_shoes(data['frames'][0],raw['video'])
    assert len(boots)==2 and all(b['box'][2]>b['box'][0] for b in boots)
    data['frames'][0]['image_joints'][14]=data['frames'][0]['image_joints'][13]
    with pytest.raises(ValueError,match='겹칩니다'):seed_shoes(data['frames'][0],raw['video'])

def test_outside_first_ankle_is_not_used(tmp_path):
    _,_,_,raw,data=prepared(tmp_path);data['frames'][0]['image_joints'][13]=[-10,0]
    with pytest.raises(ValueError):seed_shoes(data['frames'][0],raw['video'])

def test_no_shoe_observation_produces_no_rois():
    assert leg_rois(np.zeros((70,2)),[],[0,0,320,240],320,240)=={}

def test_wrong_selection_rejected_before_gpu(tmp_path):
    source,folder,selection,_,_=prepared(tmp_path);path=selection/'selected-joints.json';data=json.loads(path.read_text(encoding='utf-8'));data['source_sha256']='wrong';path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='원본'):run_leg_reestimation(folder,source,selection)
    assert not list(folder.glob('leg_reestimate_*'))

def test_cancel_before_loading(tmp_path):
    with pytest.raises(KeyboardInterrupt):run_leg_reestimation(tmp_path,tmp_path/'absent',None,lambda:True)

def test_fresh_job_full_timeline_without_raw_changes(tmp_path,monkeypatch):
    import app.leg_reestimate_job as job
    source,folder,selection,raw,data=prepared(tmp_path);before=(folder/'sam3d.json').read_bytes();calls=[]
    def child(script,out,*args):
        calls.append(script)
        if script=='shoe_worker.py':
            records=[]
            for i,row in enumerate(data['frames']):
                boots=[]
                for obj,a in ((2,13),(3,14)):
                    mask=np.zeros((240,320),np.uint8);x,y=np.round(row['image_joints'][a]).astype(int);mask[y-5:y+6,x-5:x+6]=255
                    target=out/f'boot-{obj}';target.mkdir(exist_ok=True);(target/f'{i:06d}.png').write_bytes(cv2.imencode('.png',mask)[1].tobytes());boots.append({'id':obj,'accepted':True})
                records.append({'frame_index':i,'boots':boots})
            (out/'boot-records.json').write_text(json.dumps(records))
        else:
            request=json.loads((out/'request.json').read_text(encoding='utf-8'));frames=[]
            for i in map(int,request['leg_rois']):
                frames.append({'frame_index':i,'candidates':{name:{'world_joints':data['frames'][i]['world_joints'],'image_joints':data['frames'][i]['image_joints']} for name in ('body-shoe','leg-focus')}})
            (out/'candidates.json').write_text(json.dumps({'joint_names':raw['joint_names'],'frames':frames}))
    monkeypatch.setattr(job,'gpu_child',child)
    out,report=run_leg_reestimation(folder,source,selection)
    assert calls==['shoe_worker.py','leg_candidate_worker.py'] and report['status']=='completed_with_estimates'
    assert (folder/'sam3d.json').read_bytes()==before
    rows=json.loads((out/'leg-joints.json').read_text(encoding='utf-8'))['frames'];assert len(rows)==3
    assert report['shoe_seed_identity_verified'] is False
    cap=cv2.VideoCapture(str(out/'leg-overlay.mp4'));n=0
    while cap.read()[0]:n+=1
    cap.release();assert n==3

