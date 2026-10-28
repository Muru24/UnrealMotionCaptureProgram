import json
from types import SimpleNamespace as NS
import cv2,numpy as np,pytest
from core.motion.hand_crop import hand_roi,associate_hand,insert_hand
from app.hand_preview_job import hand_chains
from test_hand_preview_job import named_hands,fixture


def candidate(x=50,y=50,score=.9):
 q=np.tile([float(x),float(y)],(21,1));q[9]+=[0,20];q[5]+=[-10,10];q[17]+=[10,10]
 return {'image_joints':q.tolist(),'world_joints':np.ones((21,3)).tolist(),'handedness_score':score}


def test_association_uses_wrist_not_handedness_score_and_rejects_outliers():
 near=candidate(51,50,.6);far=candidate(70,50,.99)
 assert associate_hand([far,near],np.array([50.,50.]),[0,0,100,100])['handedness_score']==.6
 assert associate_hand([candidate(95,50)],np.array([50.,50.]),[0,0,100,100]) is None
 bad=candidate();bad['image_joints'][0]=[float('nan'),50]
 assert associate_hand([bad],np.array([50.,50.]),[0,0,100,100]) is None


def test_roi_bounds_and_hand_insertion_preserve_all_other_joints():
 chains=hand_chains(named_hands());p=np.tile([50.,50.],(70,1));p[49]+=[0,15];p[53]+=[0,20]
 roi=hand_roi(p,chains,'left',160,120);assert 0<=roi[0]<roi[2]<=160 and 0<=roi[1]<roi[3]<=120
 before=p.copy();out=insert_hand(p,chains,'left',candidate())
 left={i for chain in chains['left'] for i in chain}
 for i in set(range(70))-left:np.testing.assert_array_equal(out[i],p[i])
 np.testing.assert_array_equal(p,before)
 p[62]=[-20,50];assert hand_roi(p,chains,'left',160,120) is None


def test_hand_comparison_missing_detection_preserves_timeline_and_raw(tmp_path,monkeypatch):
 import mediapipe as mp
 import app.hand_refine_job as job
 from app.knee_job import digest
 source,folder=fixture(tmp_path);before=(folder/'sam3d.json').read_bytes();model=tmp_path/'models/hand_landmarker';model.mkdir(parents=True);p=model/'hand_landmarker.task';p.write_bytes(b'model');(model/'manifest.json').write_text(json.dumps({'sha256':digest(p)}));monkeypatch.setattr(job,'ROOT',tmp_path)
 class Detector:
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def detect(self,image):return NS(hand_landmarks=[],hand_world_landmarks=[],handedness=[])
 monkeypatch.setattr(mp.tasks.vision.HandLandmarker,'create_from_options',lambda options:Detector())
 path=job.reestimate_hands(folder);report=json.loads((path.parent/'report.json').read_text())
 assert report['status']=='completed' and report['automatic_animation_replacement'] is False
 assert len(report['frames'])==4 and report['candidate_frames']=={'left':0,'right':0}
 cap=cv2.VideoCapture(str(path));assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT))==4;cap.release()
 assert (folder/'sam3d.json').read_bytes()==before
 flag=[False]
 with pytest.raises(KeyboardInterrupt):job.reestimate_hands(folder,lambda:flag[0],lambda a,b:flag.__setitem__(0,a>=2))
 assert any(json.loads(p.read_text())['status']=='cancelled' for p in folder.glob('hand_crop_*/report.json'))

def test_gui_hand_refinement_uses_comparison_worker(tmp_path,monkeypatch):
    from tkinterdnd2 import TkinterDnD
    from app.gui import PrototypeApp
    import app.hand_refine_job as job
    from test_motion_skeleton import job_fixture
    from test_gui import pump
    source,folder=job_fixture(tmp_path);calls=[]
    monkeypatch.setattr(job,'reestimate_hands',lambda path,cancelled,progress:(calls.append(path) or source))
    root=TkinterDnD.Tk();root.withdraw();app=PrototypeApp(root)
    try:
        app.result_dir=folder;app.generate_hand_preview(refine=True);assert app.busy
        assert not hasattr(app,'hand_refine_button')
        assert str(app.cancel_button.cget('state'))=='normal'
        pump(root,lambda:not app.busy)
        assert calls==[folder] and app.saved_preview_path==source
        assert '재추정 비교 완료' in app.status_text.get() and '미적용' in app.status_text.get()
    finally:app.stop_video();root.destroy()
