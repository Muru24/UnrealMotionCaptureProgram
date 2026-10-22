import numpy as np,pytest
from core.pose2d.region_evidence import reconcile,soft_cost

def test_outside_hair_is_retained_only_when_attached_and_temporally_supported():
 p=np.zeros((40,40),bool);p[10:30,10:25]=1;m=np.zeros_like(p);m[12:20,5:18]=1
 first,info=reconcile(m,p,2);assert info['weight']==0
 kept,info=reconcile(m,p,2,first)
 assert kept[15,6] and info['outside_pixels_retained']>0 and 0<info['weight']<.5 and not info['hard_exclusion']
 assert soft_cost([[6,15]],{'hair':(kept,info)})>0

def test_detached_background_component_is_not_retained():
 p=np.zeros((40,40),bool);p[10:30,10:30]=1;m=np.zeros_like(p);m[:5,:5]=1
 kept,info=reconcile(m,p,3,m);assert not kept.any() and info['weight']==0

def test_large_cape_is_downweighted_not_declared_wrong():
 p=np.ones((40,40),bool);m=p.copy();kept,info=reconcile(m,p,2,m)
 assert kept.all() and info['weight']==pytest.approx(.15) and 'occlusion' in info['reason']
 assert 0<soft_cost([[10,10]],{'cape':(kept,info)})<.1

def test_missing_and_fast_unconfirmed_region_do_not_penalize():
 p=np.ones((40,40),bool);m=np.zeros_like(p);m[10:20,10:20]=1
 for logit,previous in ((-1,m),(1,np.zeros_like(m))):
  kept,info=reconcile(m,p,logit,previous);assert soft_cost([[15,15]],{'cape':(kept,info)})==0

def test_penalty_is_bounded_and_overlapping_masks_do_not_double_count():
 p=np.ones((40,40),bool);m=np.zeros_like(p);m[10:20,10:20]=1
 kept,info=reconcile(m,p,2,m)
 one=soft_cost([[15,15]],{'cape':(kept,info)})
 assert one==soft_cost([[15,15]],{'cape':(kept,info),'hair':(kept,info)}) and one<=.1
 assert soft_cost([[-1,15],[50,50]],{'cape':(kept,info)})==0

def test_bad_dimensions_and_nan_points_fail():
 with pytest.raises(ValueError):reconcile(np.ones((3,3)),np.ones((4,4)),1)
 with pytest.raises(ValueError):soft_cost([[float('nan'),2]],{})

def test_zero_cost_preserves_part_algorithm_and_high_cost_cannot_bypass_constraints(tmp_path):
 from test_part_reestimation import sequence
 from core.pose3d.part_reestimation import combine,make_plan
 p,r,f=sequence(tmp_path);plan=make_plan(p,r)
 a,_=combine(p,r,plan,f);b,_=combine(p,r,plan,f,region_cost=lambda i,p:0.)
 assert a==b
 with pytest.raises(ValueError):combine(p,r,plan,f,region_cost=lambda i,p:float('nan'))

def test_comparison_job_with_empty_plan_is_noop_and_listed(tmp_path):
 import cv2
 from test_internal_mask import tracked_fixture
 from app.joint_review_job import ensure_joint_review
 from app.fullbody_job import write
 from app.completion_job import read
 from app.knee_job import digest
 from app.part_reestimate_job import run_part_reestimation
 from app.region_compare_job import run_compare
 from app.result_library import list_previews
 source,folder,tracking,config=tracked_fixture(tmp_path)
 selection=next(folder.glob('candidates_*'))
 review,_=ensure_joint_review(folder,source,selection/'fullbody-candidates.json',digest(source))
 data=read(review);data['repair_requests']=[];write(review,data)
 parts,_=run_part_reestimation(folder,source,selection,review)
 internal=folder/'internal_test';internal.mkdir()
 write(internal/'request.json',{**config,'source_sha256':digest(source),'raw_sha256':digest(folder/'sam3d.json'),'tracking_sha256':digest(folder/'sam-tracking.json')})
 write(internal/'report.json',{'status':'completed_diagnostic'})
 mask=np.zeros((240,320),np.uint8);mask[10:40,10:40]=255;(internal/'mask.png').write_bytes(cv2.imencode('.png',mask)[1].tobytes())
 write(internal/'regions.json',{'frames':[{'frame_index':i,'objects':{'cape':{'file':'mask.png','object_logit':2}}} for i in range(3)]})
 original=digest(parts/'part-joints.json');out=run_compare(folder,source,selection,parts,internal)
 assert read(out/'report.json')['changed_frames_vs_parts']==[] and digest(parts/'part-joints.json')==original
 assert out/'region-candidate-overlay.mp4' in list_previews(folder.parent,folder)
 data=read(internal/'request.json');data['source_sha256']='stale';write(internal/'request.json',data)
 with pytest.raises(ValueError,match='Stale'):run_compare(folder,source,selection,parts,internal)
