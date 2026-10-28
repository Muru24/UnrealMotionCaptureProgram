import json
import cv2,numpy as np,pytest
from app.hand_preview_job import hand_chains,draw_hands,generate_hand_preview
from test_motion_skeleton import job_fixture


def named_hands():
    names=[f'body-{i}' for i in range(70)]
    for side,start,wrist in [('right',21,41),('left',42,62)]:
        names[wrist]=side+'-wrist'
        for f,finger in enumerate(['thumb','index','middle','ring','pinky']):
            for j,joint in enumerate(['tip','first-joint','second-joint','third-joint']):names[start+f*4+j]=f'{side}-{finger}-{joint}'
    return names


def fixture(tmp_path):
    source,folder=job_fixture(tmp_path);p=folder/'sam3d.json';raw=json.loads(p.read_text());raw['joint_names']=named_hands()
    for r in raw['frames']:
        q=np.tile([80.,60.],(70,1));q[:,0]+=np.arange(70)%5*3;q[:,1]+=np.arange(70)%7*2
        r['outputs']['pred_keypoints_2d']=q.tolist()
    p.write_text(json.dumps(raw),encoding='utf-8');return source,folder


def test_named_chain_follows_wrist_to_tip_and_rejects_missing_names():
    chains=hand_chains(named_hands())
    assert chains['right'][0]==[41,24,23,22,21]
    assert chains['left'][4]==[62,61,60,59,58]
    with pytest.raises(ValueError):hand_chains(['unknown']*70)


def test_preview_missing_and_outside_joints_do_not_crash_or_invent_points():
    chains=hand_chains(named_hands());im=np.zeros((120,160,3),np.uint8)
    rendered,counts=draw_hands(im,None,chains);assert rendered.shape==(720,1320,3)
    assert counts=={'left':0,'right':0}
    q=np.tile([-100.,-100.],(70,1));_,counts=draw_hands(im,q,chains);assert counts=={'left':0,'right':0}


def test_preview_keeps_timeline_raw_and_source_and_cancel_does_not_publish(tmp_path):
    source,folder=fixture(tmp_path);before=(folder/'sam3d.json').read_bytes();video_before=source.read_bytes();progress=[]
    path=generate_hand_preview(folder,progress=lambda a,b:progress.append((a,b)))
    cap=cv2.VideoCapture(str(path));count=0
    while True:
        ok,frame=cap.read()
        if not ok:break
        count+=1;assert frame.shape==(720,1320,3)
    cap.release();assert count==4 and progress[-1]==(4,4)
    assert json.loads((path.parent/'report.json').read_text())['status']=='completed'
    assert (folder/'sam3d.json').read_bytes()==before and source.read_bytes()==video_before
    with pytest.raises(KeyboardInterrupt):generate_hand_preview(folder,cancelled=lambda:True)
    assert len(list(folder.glob('hands_*')))==1
    source.write_bytes(video_before+b'changed')
    with pytest.raises(ValueError,match='변경'):generate_hand_preview(folder)


def test_gui_hand_preview_worker_and_busy_state(tmp_path,monkeypatch):
    from tkinterdnd2 import TkinterDnD
    from app.gui import PrototypeApp
    import app.hand_preview_job as job
    from test_gui import pump
    source,folder=job_fixture(tmp_path);calls=[]
    def generate(path,cancelled,progress):calls.append(path);return source
    monkeypatch.setattr(job,'generate_hand_preview',generate)
    root=TkinterDnD.Tk();root.withdraw();app=PrototypeApp(root)
    try:
        app.result_dir=folder;app.generate_hand_preview();assert app.busy
        assert not hasattr(app,'hand_preview_button')
        assert str(app.cancel_button.cget('state'))=='normal'
        pump(root,lambda:not app.busy)
        assert calls==[folder] and app.saved_preview_path==source
        assert app.result_kind.get()=='저장 영상'
        assert '손 관절 미리보기 완료' in app.status_text.get()
    finally:app.stop_video();root.destroy()

def test_cancel_mid_preview_records_partial_and_preserves_raw(tmp_path):
    _,folder=fixture(tmp_path);before=(folder/'sam3d.json').read_bytes();flag=[False]
    def progress(done,total):
        if done==2:flag[0]=True
    with pytest.raises(KeyboardInterrupt):generate_hand_preview(folder,cancelled=lambda:flag[0],progress=progress)
    report=json.loads(next(folder.glob('hands_*/report.json')).read_text())
    assert report['status']=='cancelled' and len(report['frames'])==2
    assert (folder/'sam3d.json').read_bytes()==before
