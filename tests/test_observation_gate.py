import copy,numpy as np,pytest
from core.pose3d.observation_gate import gate_observations,assess_refinement
from core.pose3d.motionbert_adapter import COCO_TO_MHR
from app.sam3d_prompt_adapter import validate_hints,compatible_decoder

def sample(tmp_path):
 from test_knee_job import fixture
 from app.completion_job import read
 source,folder,q,p,cam=fixture(tmp_path);raw=read(folder/'sam3d.json');rows=[]
 for i,row in enumerate(raw['frames']):
  row.update(roi=[0,0,320,240],tracking={'state':'tracked','track_id':1},scene={'index':0})
  rows.append({'frame_index':i,'target_id':1,'tracking_segment':0,'scene_index':0,'coco_image_joints':(p[COCO_TO_MHR]+[10,0]).tolist(),'coco_scores':np.full(17,.9).tolist()})
 return raw,{'frames':rows},q,p

def test_only_context_supported_independent_points_are_hints(tmp_path):
 raw,ind,q,p=sample(tmp_path);old=copy.deepcopy(ind);gate=gate_observations(raw,ind,lambda i,p:[])
 assert list(gate['frames'])==[1] and len(gate['frames'][1])==2 and ind==old
 assert all(not e['accuracy_verified'] for e in gate['events'])

@pytest.mark.parametrize('mode',['score','garment','missing_pixels','jump','independent_id'])
def test_unreliable_observations_are_held_without_lowering_threshold(tmp_path,mode):
 raw,ind,*_=sample(tmp_path);support=lambda i,p:[]
 if mode=='score':
  for row in ind['frames']:row['coco_scores']=[.54]*17
 if mode=='garment':support=lambda i,p:['accessory_overlap_or_occlusion']
 if mode=='missing_pixels':support=lambda i,p:None
 if mode=='jump':ind['frames'][1]['coco_image_joints']=(np.asarray(ind['frames'][1]['coco_image_joints'])+[300,0]).tolist()
 if mode=='independent_id':
  for row in ind['frames']:row['target_id']=99
 assert not gate_observations(raw,ind,support)['frames']

@pytest.mark.parametrize('mode',['target','segment','scene','missing'])
def test_temporal_context_does_not_cross_boundaries(tmp_path,mode):
 raw,ind,*_=sample(tmp_path)
 if mode=='target':raw['frames'][0]['tracking']['track_id']=2
 if mode=='segment':raw['frames'][0]['tracking_segment']=3
 if mode=='scene':raw['frames'][0]['scene']['index']=1
 if mode=='missing':ind['frames'][0]['coco_image_joints']=None
 assert not gate_observations(raw,ind,lambda i,p:[])['frames']

def test_postcheck_requires_hint_improvement_without_large_body_change(tmp_path):
 raw,ind,q,p=sample(tmp_path);control={'world_joints':q.tolist(),'image_joints':p.tolist()};guided={'world_joints':q.tolist(),'image_joints':(p+[10,0]).tolist()};hint=[{'mhr_joint_index':13,'image_position':(p[13]+[10,0]).tolist()}]
 assert assess_refinement(control,guided,hint)['accepted_as_model_hypothesis']
 assert not assess_refinement(control,control,hint)['accepted_as_model_hypothesis']
 bad=copy.deepcopy(guided);bad['world_joints'][11][0]+=3
 assert not assess_refinement(control,bad,hint)['accepted_as_model_hypothesis']
 with pytest.raises(ValueError):assess_refinement(control,guided,[])

def test_native_hint_validation_and_precise_decoder_compatibility():
 validate_hints([{'mhr_joint_index':13,'image_position':[100,200]}])
 with pytest.raises(ValueError):validate_hints([{'mhr_joint_index':70,'image_position':[1,2]}])
 with pytest.raises(ValueError):validate_hints([{'mhr_joint_index':13,'image_position':[float('nan'),2]}])
 def decoder(x,value=2):return x+value
 adapted=compatible_decoder(decoder);assert adapted(3,full_output=None)==5
 with pytest.raises(ValueError):adapted(3,full_output={'not':'empty'})
 with pytest.raises(TypeError):adapted(3,unrelated=1)
 def newer(x,full_output=None):return full_output
 assert compatible_decoder(newer)(1,full_output='supported')=='supported'

def test_invalid_order_and_cancel_do_not_generate_hints(tmp_path):
 raw,ind,*_=sample(tmp_path)
 with pytest.raises(KeyboardInterrupt):gate_observations(raw,ind,lambda i,p:[],cancelled=lambda:True)
 ind['frames'][1]['frame_index']=7
 with pytest.raises(ValueError):gate_observations(raw,ind,lambda i,p:[])

def prepared_job(tmp_path):
 from app.fullbody_job import write
 from app.knee_job import digest
 raw,ind,q,p=sample(tmp_path);folder=tmp_path/'run';source=tmp_path/'input.mp4';write(folder/'sam3d.json',raw)
 independent=folder/'independent_test';independent.mkdir();internal=folder/'internal_test';internal.mkdir()
 write(independent/'independent-2d.json',ind)
 write(independent/'report.json',{'status':'completed_independent_model_comparison','source_sha256':digest(source),'input_hashes':{str(folder/'sam3d.json'):digest(folder/'sam3d.json')}})
 import cv2
 (folder/'person.png').write_bytes(cv2.imencode('.png',np.ones((240,320),np.uint8)*255)[1].tobytes())
 write(folder/'sam-tracking.json',{'frames':[{'frame_index':i,'roi':[0,0,320,240],'tracking':{'state':'tracked','track_id':1},'mask':{'file':'person.png'}} for i in range(3)]})
 write(internal/'request.json',{'seed_frame':1,'start':0,'end_exclusive':3,'source_sha256':digest(source),'raw_sha256':digest(folder/'sam3d.json'),'tracking_sha256':digest(folder/'sam-tracking.json')})
 write(internal/'report.json',{'status':'completed_diagnostic'});write(internal/'regions.json',{'frames':[]})
 raw['joint_names']=[str(i) for i in range(70)];write(folder/'sam3d.json',raw)
 # Keep both provenance chains synchronized with the fixture's named joints.
 from app.completion_job import read
 for path in (internal/'request.json',independent/'report.json'):
  data=read(path)
  if 'raw_sha256' in data:data['raw_sha256']=digest(folder/'sam3d.json')
  else:data['input_hashes'][str(folder/'sam3d.json')]=digest(folder/'sam3d.json')
  write(path,data)
 return source,folder,independent,internal,q,p


def test_guided_job_selects_only_eligible_points_and_preserves_raw(tmp_path,monkeypatch):
 import app.guided_observation_job as job
 from app.completion_job import read
 from app.fullbody_job import write
 from app.knee_job import digest
 source,folder,independent,internal,q,p=prepared_job(tmp_path);before=digest(folder/'sam3d.json')
 def child(script,out,*args):
  req=read(out/'request.json');assert list(req['point_prompts'])==['1'] and len(req['point_prompts']['1']['guided-body'])<=2
  assert req['inference_types']=={'body-control':'body','guided-body':'body'}
  write(out/'candidates.json',{'joint_names':[str(i) for i in range(70)],'frames':[{'frame_index':1,'candidates':{'body-control':{'world_joints':q.tolist(),'image_joints':p.tolist()},'guided-body':{'world_joints':q.tolist(),'image_joints':(p+[10,0]).tolist()}}}]})
 monkeypatch.setattr(job,'gpu_child',child);out=job.run_guided(folder,source,independent,internal)
 assert read(out/'report.json')['results'][0]['accepted_as_model_hypothesis'] and digest(folder/'sam3d.json')==before
 rows=read(out/'guided-joints.json')['frames'];assert rows[0]['world_joints'] is None and rows[1]['world_joints'] is not None and rows[2]['world_joints'] is None
 from app.result_library import list_previews
 assert out/'guided-comparison.mp4' in list_previews(folder.parent,folder)


def test_no_eligible_observation_does_not_initialize_gpu(tmp_path,monkeypatch):
 import app.guided_observation_job as job
 from app.completion_job import read
 from app.fullbody_job import write
 source,folder,independent,internal,q,p=prepared_job(tmp_path)
 data=read(independent/'independent-2d.json')
 for row in data['frames']:row['coco_scores']=[.1]*17
 write(independent/'independent-2d.json',data)
 monkeypatch.setattr(job,'gpu_child',lambda *a:pytest.fail('No hint must mean no GPU'))
 out=job.run_guided(folder,source,independent,internal)
 assert read(out/'report.json')['status']=='completed_no_eligible_hints' and not (out/'guided-comparison.mp4').exists()


def test_guided_worker_failure_is_not_published(tmp_path,monkeypatch):
 import app.guided_observation_job as job
 from app.completion_job import read
 source,folder,independent,internal,q,p=prepared_job(tmp_path)
 def fail(*a):raise RuntimeError('native prompt failure')
 monkeypatch.setattr(job,'gpu_child',fail)
 with pytest.raises(RuntimeError):job.run_guided(folder,source,independent,internal)
 out=next(folder.glob('guided_*'));assert read(out/'report.json')['status']=='failed' and not (out/'guided-comparison.mp4').exists()
