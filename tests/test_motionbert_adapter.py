import copy,numpy as np,pytest
from core.pose3d.motionbert_adapter import coco_to_h36m,normalize_clip,flip_h36m,segments,mhr_comparison_points

def test_adapter_maps_left_right_and_explicit_head_proxy_without_mutation():
 p=np.arange(34,dtype=float).reshape(17,2)+30;s=np.ones(17);old=p.copy();x=coco_to_h36m(p,s,320,240)
 np.testing.assert_allclose(x[1,:2],(p[12]-[160,120])/120)
 np.testing.assert_allclose(x[4,:2],(p[11]-[160,120])/120)
 assert x[10,2]==.5 and x.shape==(17,3);np.testing.assert_array_equal(p,old)


def test_invalid_coordinates_and_offscreen_confidence():
 p=np.ones((17,2));p[16]=[-1,3];x=coco_to_h36m(p,np.ones(17),320,240);assert x[3,2]==0
 with pytest.raises(ValueError):coco_to_h36m(np.zeros((70,2)),np.ones(17),320,240)
 with pytest.raises(ValueError):coco_to_h36m(np.full((17,2),np.nan),np.ones(17),320,240)


def test_clip_normalization_and_inverse_keep_geometry_and_hide_low_scores():
 x=np.ones((4,17,3));x[...,:2]=np.arange(136).reshape(4,17,2)/100;x[0,0,2]=.1;old=x.copy()
 y,params=normalize_clip(x)
 valid=x[...,2]>=.3
 np.testing.assert_allclose((y[...,:2]*params['scale']/2+params['center'])[valid],x[...,:2][valid],atol=1e-6)
 assert np.max(np.abs(y[...,:2]))<=1
 assert y[0,0,2]==0;np.testing.assert_array_equal(x,old)
 with pytest.raises(ValueError):normalize_clip(np.zeros((2,17,3)))


def test_flip_is_involution_and_preserves_confidence_pairing():
 x=np.arange(3*17*3).reshape(3,17,3).astype(float);old=x.copy()
 np.testing.assert_array_equal(flip_h36m(flip_h36m(x)),x);np.testing.assert_array_equal(x,old)


def rows():return [{'frame_index':i,'target_id':1,'tracking_segment':0,'scene_index':0,'h36m_input':np.ones((17,3)).tolist()} for i in range(10)]

@pytest.mark.parametrize('field',['target_id','tracking_segment','scene_index'])
def test_segments_split_boundaries(field):
 r=rows()
 for row in r[4:]:row[field]=2
 assert segments(r)==[list(range(4)),list(range(4,10))]


def test_missing_observation_and_clip_limit_are_not_interpolated():
 r=rows();r[4]['h36m_input']=None
 assert segments(r,maxlen=3)==[[0,1,2],[3],[5,6,7],[8,9]]
 r[2]['frame_index']=7
 with pytest.raises(ValueError):segments(r)


def test_independent_job_retains_tracking_and_native_formats(tmp_path,monkeypatch):
 import app.independent_pose_job as job
 from test_knee_job import fixture
 from app.fullbody_job import write
 from app.completion_job import read
 from app.knee_job import digest
 source,folder,q,p,cam=fixture(tmp_path);raw=read(folder/'sam3d.json')
 for row in raw['frames']:row.update(roi=[0,0,320,240],tracking={'state':'tracked','track_id':1})
 write(folder/'sam3d.json',raw);before=digest(folder/'sam3d.json')
 class Backend:
  def __init__(self,*a):pass
  def pose(self,image,bboxes):return np.asarray([p[[0,1,2,3,4,5,6,7,8,62,41,9,10,11,12,13,14]]]),np.ones((1,17))
  def close(self):pass
 def child(script,out,*args):
  req=read(out/'motionbert-request.json');result=[]
  for segment in req['segments']:
   result.extend({'frame_index':i,'world_joints_normalized':mhr_comparison_points(q).tolist(),'image_xy_proxy':np.zeros((17,2)).tolist()} for i in segment['indices'])
  write(out/'motionbert-joints.json',{'frames':result})
 monkeypatch.setattr(job,'RTMPoseBackend',Backend);monkeypatch.setattr(job,'gpu_child',child)
 out=job.run_independent(folder,source);report=read(out/'report.json')
 assert report['status']=='completed_independent_model_comparison' and report['clip_lengths']==[3]
 assert digest(folder/'sam3d.json')==before and not report['tracking_modified'] and report['joint_format']=='H36M17_separate_from_MHR70'
 assert (out/'independent-comparison.mp4').is_file()

def test_job_cancel_and_failure_do_not_publish_video(tmp_path,monkeypatch):
 import app.independent_pose_job as job
 from test_knee_job import fixture
 from app.fullbody_job import write
 from app.completion_job import read
 source,folder,*_=fixture(tmp_path);raw=read(folder/'sam3d.json')
 for row in raw['frames']:row.update(roi=[0,0,320,240],tracking={'state':'tracked','track_id':1})
 write(folder/'sam3d.json',raw)
 class Backend:
  def __init__(self,*a):pass
  def pose(self,*a,**kw):raise ValueError('bad independent observation')
  def close(self):pass
 monkeypatch.setattr(job,'RTMPoseBackend',Backend)
 with pytest.raises(ValueError):job.run_independent(folder,source)
 out=next(folder.glob('independent_*'));assert read(out/'report.json')['status']=='failed' and not (out/'independent-comparison.mp4').exists()
 with pytest.raises(KeyboardInterrupt):job.run_independent(folder,source,cancelled=lambda:True)
 assert any(read(p/'report.json')['status']=='cancelled' for p in folder.glob('independent_*'))


def test_mhr_comparison_is_read_only_and_keeps_hips_and_wrist_labels():
 q=np.arange(210,dtype=float).reshape(70,3);old=q.copy();points=mhr_comparison_points(q)
 np.testing.assert_array_equal(points[1],q[10]);np.testing.assert_array_equal(points[13],q[62])
 np.testing.assert_array_equal(points[0],(q[9]+q[10])/2);np.testing.assert_array_equal(q,old)
 with pytest.raises(ValueError):mhr_comparison_points(np.zeros((17,3)))
