import numpy as np,pytest
from core.pose2d.mask_prompt import reduced_prompt
from app.leg_candidate_worker import predict_candidate

def test_reduced_prompt_preserves_person_and_excludes_only_named_positive_regions():
 p=np.zeros((30,30),bool);p[5:25,5:25]=1;m=np.zeros_like(p);m[5:15,5:25]=1;old=p.copy()
 reduced,info=reduced_prompt(p,{'cape':(m,2)})
 assert reduced.sum()==200 and info['remaining_person_fraction']==.5 and not info['visible_body_verified']
 np.testing.assert_array_equal(p,old)
 assert not np.any(reduced&~p)

def test_excessive_removal_empty_and_unchanged_masks_are_not_prompted():
 p=np.ones((30,30),bool)
 assert reduced_prompt(p,{'cape':(p,2)})[0] is None
 assert reduced_prompt(p,{'cape':(p,-1)})[0] is None
 with pytest.raises(ValueError):reduced_prompt(np.zeros_like(p),{})
 with pytest.raises(ValueError):reduced_prompt(p,{'cape':(np.ones((3,3)),2)})

def test_prompt_adapter_passes_binary_mask_and_identical_pixels_without_old_path_change():
 calls=[]
 class Estimator:
  def process_one_image(self,image,**kwargs):calls.append((image.copy(),kwargs));return ['pose']
 e=Estimator();frame=np.arange(12*10*3,dtype=np.uint8).reshape(12,10,3);old=frame.copy();roi=[0,0,10,12];mask=np.ones((1,12,10),np.uint8)
 assert predict_candidate(e,frame,roi)==['pose'];assert 'masks' not in calls[0][1]
 predict_candidate(e,frame,roi,mask)
 np.testing.assert_array_equal(calls[0][0],calls[1][0]);np.testing.assert_array_equal(frame,old)
 np.testing.assert_array_equal(calls[1][1]['masks'],mask);np.testing.assert_array_equal(calls[0][1]['bboxes'],calls[1][1]['bboxes'])

def prepare(tmp_path):
 from test_internal_mask import tracked_fixture
 from app.fullbody_job import write
 from app.knee_job import digest
 source,folder,tracking,config=tracked_fixture(tmp_path);internal=folder/'internal_test';internal.mkdir()
 write(internal/'request.json',{**config,'source_sha256':digest(source),'raw_sha256':digest(folder/'sam3d.json'),'tracking_sha256':digest(folder/'sam-tracking.json')})
 write(internal/'report.json',{'status':'completed_diagnostic'})
 import cv2
 mask=np.zeros((240,320),np.uint8);mask[:120,:]=255;(internal/'cape.png').write_bytes(cv2.imencode('.png',mask)[1].tobytes())
 write(internal/'regions.json',{'frames':[{'frame_index':i,'objects':{'cape':{'file':'cape.png','object_logit':2}}} for i in range(3)]})
 # The fixture's raw SAM target has the same ROI used for all control variants.
 return source,folder,internal

@pytest.mark.parametrize('mode',['indices','stale','cancel'])
def test_invalid_requests_do_not_start_gpu(tmp_path,monkeypatch,mode):
 import app.mask_prompt_job as job
 from app.fullbody_job import write
 from app.completion_job import read
 source,folder,internal=prepare(tmp_path)
 monkeypatch.setattr(job,'gpu_child',lambda *a:pytest.fail('Must reject before GPU'))
 if mode=='stale':
  r=read(internal/'request.json');r['source_sha256']='stale';write(internal/'request.json',r)
 with pytest.raises(KeyboardInterrupt if mode=='cancel' else ValueError):job.run_mask_prompts(folder,source,internal,[1,1] if mode=='indices' else [1],cancelled=lambda:mode=='cancel')

def test_controlled_job_samples_same_roi_and_preserves_unsampled_frames(tmp_path,monkeypatch):
 import app.mask_prompt_job as job
 from app.completion_job import read
 from app.fullbody_job import write
 from app.knee_job import digest
 source,folder,internal=prepare(tmp_path);raw=read(folder/'sam3d.json');raw['joint_names']=[str(i) for i in range(70)]
 for row in raw['frames']:row.update(roi=[0,0,320,240],tracking={'state':'tracked','track_id':1})
 write(folder/'sam3d.json',raw);r=read(internal/'request.json');r['raw_sha256']=digest(folder/'sam3d.json');write(internal/'request.json',r)
 before=digest(folder/'sam3d.json')
 def child(script,out,*a):
  req=read(out/'request.json');poses=[]
  assert set(req['leg_rois']['1'])=={'unconditioned','person-mask','accessory-reduced'}
  assert all(roi==req['leg_rois']['1']['unconditioned'] for roi in req['leg_rois']['1'].values())
  base=raw['frames'][1]['outputs']
  for name,path in req['mask_files']['1'].items():assert (out/path).is_file()
  write(out/'candidates.json',{'joint_names':raw['joint_names'],'frames':[{'frame_index':1,'candidates':{name:{'world_joints':base['pred_keypoints_3d'],'image_joints':base['pred_keypoints_2d']} for name in req['leg_rois']['1']}}]})
 monkeypatch.setattr(job,'gpu_child',child)
 out=job.run_mask_prompts(folder,source,internal,[1]);report=read(out/'report.json')
 assert report['inference_count']==3 and report['status']=='completed_mask_prompt_experiment'
 assert digest(folder/'sam3d.json')==before
 rows=read(out/'person-mask-joints.json')['frames'];assert rows[0]['world_joints'] is None and rows[1]['world_joints'] is not None and rows[2]['world_joints'] is None
 from app.result_library import list_previews
 assert out/'person-mask.mp4' in list_previews(folder.parent,folder)


def test_gpu_failure_does_not_publish_comparison(tmp_path,monkeypatch):
 import app.mask_prompt_job as job
 from app.completion_job import read
 from app.fullbody_job import write
 from app.knee_job import digest
 source,folder,internal=prepare(tmp_path);raw=read(folder/'sam3d.json')
 for row in raw['frames']:row.update(roi=[0,0,320,240],tracking={'state':'tracked','track_id':1})
 write(folder/'sam3d.json',raw);r=read(internal/'request.json');r['raw_sha256']=digest(folder/'sam3d.json');write(internal/'request.json',r)
 def fail(*a):raise RuntimeError('GPU failed')
 monkeypatch.setattr(job,'gpu_child',fail)
 with pytest.raises(RuntimeError):job.run_mask_prompts(folder,source,internal,[1])
 out=next(folder.glob('mask_prompt_*'));assert read(out/'report.json')['status']=='failed' and not list(out.glob('*.mp4'))
