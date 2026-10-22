import copy,numpy as np,pytest
from test_part_reestimation import sequence,prepared
from core.pose3d.manual_leg_geometry import project,fit_camera
from core.pose3d.temporal_hypotheses import generate,direction,rotation
from app.temporal_hypothesis_job import run_temporal
from app.part_reestimate_job import run_part_reestimation
from app.completion_job import read

def sample(tmp_path):
 p,r,_=sequence(tmp_path);rows=[]
 clean=copy.deepcopy(p['frames'][3]['candidates']['stable']);camera=fit_camera(clean['world_joints'],clean['image_joints'],320,240)
 for i in range(9):
  q=np.asarray(clean['world_joints']).copy()
  if i==4:q[11,0]+=.025
  rows.append({'frame_index':i,'world_joints':q.tolist(),'image_joints':project(q,camera).tolist(),'changed_parts':[],'provenance':'baseline'})
  r['frames'][i]['review_parts']=['left_leg'] if i==4 else []
 return p,r,{'frames':rows}

def test_two_sided_hypothesis_preserves_body_and_unrequested_frames(tmp_path):
 p,r,b=sample(tmp_path);old=copy.deepcopy(b);rows,d=generate(p,r,b,4,5)
 assert d['changed_frames']==[4] and b==old
 fixed=[j for j in range(70) if j not in (11,13,15,16,17)]
 np.testing.assert_array_equal(np.asarray(rows[4]['world_joints'])[fixed],np.asarray(b['frames'][4]['world_joints'])[fixed])
 assert rows[4]['provenance']=='unobserved_temporal_hypothesis_not_measurement'
 assert rows[3]==b['frames'][3] and rows[5]==b['frames'][5]

@pytest.mark.parametrize('field',['target_id','tracking_segment','scene_index','pose_track_start'])
def test_reference_search_never_crosses_identity_or_scene(tmp_path,field):
 p,r,b=sample(tmp_path);r['frames'][3][field]=999
 rows,d=generate(p,r,b,4,5);assert not d['changed_frames']
 assert d['events'][0]['rejected']=='no_bounded_two_sided_references'

def test_missing_and_long_reference_gap_are_not_filled(tmp_path):
 p,r,b=sample(tmp_path);saved=copy.deepcopy(b);b['frames'][3]['world_joints']=None;b['frames'][3]['image_joints']=None
 assert not generate(p,r,b,4,5)[1]['changed_frames']
 b=saved
 for i in range(2,7):r['frames'][i]['review_parts']=['left_leg']
 assert not generate(p,r,b,4,5,max_gap_seconds=.1)[1]['changed_frames']

def test_direction_slerp_and_body_rotation_preserve_norm_and_handedness():
 a=np.array([1.,0,0]);old=a.copy();d=direction(a,np.array([0.,1,0]),.5)
 np.testing.assert_allclose(d,[2**-.5,2**-.5,0]);np.testing.assert_array_equal(a,old)
 with pytest.raises(ValueError):direction(a,-a,.5)
 with pytest.raises(ValueError):direction(np.zeros(3),a,.5)
 q=rotation(np.eye(3),np.diag([-1.,-1.,1.]),.5)
 np.testing.assert_allclose(q.T@q,np.eye(3),atol=1e-7);assert np.linalg.det(q)==pytest.approx(1)

def test_cancel_and_bad_order(tmp_path):
 p,r,b=sample(tmp_path)
 with pytest.raises(KeyboardInterrupt):generate(p,r,b,4,5,cancelled=lambda:True)
 b['frames'][1]['frame_index']=77
 with pytest.raises(ValueError):generate(p,r,b,4,5)

def test_job_noop_outputs_are_separate_and_stale_baseline_rejected(tmp_path):
 from app.knee_job import digest
 from app.fullbody_job import write
 source,folder,selection,raw,review=prepared(tmp_path);parts,_=run_part_reestimation(folder,source,selection,review)
 before=digest(parts/'part-joints.json');out=run_temporal(folder,source,selection,parts,0,3)
 report=read(out/'report.json');assert report['status']=='completed_hypotheses'
 assert digest(parts/'part-joints.json')==before and (out/'limbs-hypothesis.mp4').is_file() and (out/'body-context-hypothesis.mp4').is_file()
 assert report['results']['limbs']['changed_frames']==[] and report['new_gpu_inference']==0
 data=read(parts/'part-joints.json');data['review_sha256']='stale';write(parts/'part-joints.json',data)
 with pytest.raises(ValueError,match='Stale'):run_temporal(folder,source,selection,parts,0,3)

def test_large_image_displacement_is_rejected(tmp_path):
 p,r,b=sample(tmp_path);q=np.asarray(b['frames'][4]['world_joints']);q[11,0]+=.7
 camera=fit_camera(b['frames'][4]['world_joints'],b['frames'][4]['image_joints'],320,240)
 b['frames'][4]['world_joints']=q.tolist();b['frames'][4]['image_joints']=project(q,camera).tolist()
 rows,d=generate(p,r,b,4,5);assert not d['changed_frames'] and any(e.get('rejected')=='unsupported_image_displacement' for e in d['events'])

def test_large_body_reference_change_is_not_committed(tmp_path):
 p,r,b=sample(tmp_path);camera=fit_camera(b['frames'][4]['world_joints'],b['frames'][4]['image_joints'],320,240)
 q=np.asarray(b['frames'][4]['world_joints']);q[[5,6,69],0]+=.6
 b['frames'][4]['world_joints']=q.tolist();b['frames'][4]['image_joints']=project(q,camera).tolist();r['frames'][4]['review_parts']=['torso']
 rows,d=generate(p,r,b,4,5,body_context=True)
 assert not d['changed_frames'] and any(e.get('rejected')=='body_reference_displacement_too_large' for e in d['events'])

def test_job_cancel_does_not_publish_completed_video(tmp_path):
 source,folder,selection,raw,review=prepared(tmp_path);parts,_=run_part_reestimation(folder,source,selection,review)
 with pytest.raises(KeyboardInterrupt):run_temporal(folder,source,selection,parts,0,3,cancelled=lambda:True)
 out=next(folder.glob('temporal_*'));assert read(out/'report.json')['status']=='cancelled' and not list(out.glob('*.mp4'))

def test_preview_highlights_only_new_coordinates_not_old_part_provenance(tmp_path,monkeypatch):
 import app.temporal_hypothesis_job as job
 from app.fullbody_job import write
 source,folder,selection,raw,review=prepared(tmp_path);parts,_=run_part_reestimation(folder,source,selection,review)
 data=read(parts/'part-joints.json');data['frames'][0]['changed_parts']=[{'part':'left_arm','variant':'previous_stage'}];write(parts/'part-joints.json',data)
 actual=job.render;seen=[]
 def capture(source,path,packet,rows,*args,**kwargs):
  seen.extend(rows);return actual(source,path,packet,rows,*args,**kwargs)
 monkeypatch.setattr(job,'render',capture)
 run_temporal(folder,source,selection,parts,0,3)
 assert seen and all(not row['changed_parts'] for row in seen)
