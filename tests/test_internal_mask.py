import copy
import numpy as np
import pytest
from core.pose2d.internal_mask import validate_prompts,assess_region,joint_region_evidence
from app.internal_mask_job import local_file,load_mask,run_internal_masks
from test_part_reestimation import prepared
from app.fullbody_job import write


def test_prompt_validation_accepts_positive_and_negative_points():
    validate_prompts([{'name':'hair','points':[[1,1],[4,4]],'labels':[1,0]}],10,10)

@pytest.mark.parametrize('objects',[
 [],[{'name':'../cape','points':[[1,1]],'labels':[1]}],
 [{'name':'cape','points':[[10,1]],'labels':[1]}],
 [{'name':'cape','points':[[1,1]],'labels':[0]}],
 [{'name':'cape','points':[[float('nan'),1]],'labels':[1]}],
 [{'name':'cape','points':[[1,1]],'labels':[1]}, {'name':'cape','points':[[2,2]],'labels':[1]}]])
def test_invalid_prompts_are_rejected(objects):
    with pytest.raises(ValueError):validate_prompts(objects,10,10)


def test_clips_to_person_and_never_authorizes_pose_exclusion():
    person=np.zeros((20,20),bool);person[4:16,4:16]=1
    mask=np.zeros_like(person);mask[5:10,5:10]=1
    before=mask.copy();inside,info=assess_region(mask,person,2)
    assert info['status']=='prompted_region_unverified' and not info['use_for_pose_exclusion'] and not info['semantic_label_verified']
    np.testing.assert_array_equal(mask,before)
    mask[:]=1;inside,info=assess_region(mask,person,2)
    assert not np.any(inside&~person) and 'region_leaks_outside_person' in info['reasons'] and 'region_covers_most_of_person' in info['reasons']


def test_presence_and_abrupt_change_remain_review():
    person=np.ones((30,30),bool);mask=np.zeros_like(person);mask[:10,:10]=1
    _,info=assess_region(mask,person,-1);assert 'object_not_present' in info['reasons']
    old=np.zeros_like(person);old[:4,:4]=1
    _,info=assess_region(mask,person,1,old);assert 'abrupt_region_area_change' in info['reasons']


def test_joint_overlap_is_a_hint_and_rejected_regions_do_not_vote():
    person=np.ones((30,30),bool);mask=np.zeros_like(person);mask[5:15,5:15]=1
    inside,info=assess_region(mask,person,2);points=np.full((70,2),20.);points[11]=[10,10]
    hits=joint_region_evidence(points,{'cape':(inside,info)})
    assert hits==[{'joint_index':11,'regions':['cape'],'action':'review_only','anatomical_error_confirmed':False}]
    bad=copy.deepcopy(info);bad['status']='review'
    assert not joint_region_evidence(points,{'cape':(inside,bad)})


def test_mask_paths_and_dimensions_are_bounded(tmp_path):
    import cv2
    root=tmp_path/'root';root.mkdir();outside=tmp_path/'outside.png';outside.write_bytes(b'bad')
    with pytest.raises(ValueError):local_file(root,'../outside.png')
    image=np.zeros((10,10),np.uint8);p=root/'a.png';p.write_bytes(cv2.imencode('.png',image)[1].tobytes())
    with pytest.raises(ValueError):load_mask(p,20,20)


def tracked_fixture(tmp_path):
    import cv2
    source,folder,selection,raw,review=prepared(tmp_path);mask=folder/'person.png'
    mask.write_bytes(cv2.imencode('.png',np.ones((240,320),np.uint8)*255)[1].tobytes())
    tracking={'frames':[{'frame_index':i,'roi':[0,0,320,240],'tracking':{'state':'tracked','track_id':1},'scene':{'index':0},'mask':{'file':'person.png'}} for i in range(3)]}
    write(folder/'sam-tracking.json',tracking)
    config={'start':0,'end_exclusive':3,'seed_frame':1,'objects':[{'name':'cape','points':[[10,10]],'labels':[1]}]}
    return source,folder,tracking,config

@pytest.mark.parametrize('mode',['scene','missing','cancel','interval'])
def test_invalid_interval_never_starts_gpu(tmp_path,monkeypatch,mode):
    import app.internal_mask_job as job
    source,folder,tracking,config=tracked_fixture(tmp_path)
    if mode=='scene':tracking['frames'][2]['scene']['index']=1
    if mode=='missing':tracking['frames'][2]['roi']=None
    if mode=='interval':config['end_exclusive']=4
    write(folder/'sam-tracking.json',tracking)
    monkeypatch.setattr(job,'gpu_child',lambda *a:pytest.fail('Must reject before GPU'))
    with pytest.raises(KeyboardInterrupt if mode=='cancel' else ValueError):
        run_internal_masks(folder,source,config,cancelled=lambda:mode=='cancel')


def test_diagnostic_job_keeps_raw_pose_and_exports_clip(tmp_path,monkeypatch):
    import cv2
    import app.internal_mask_job as job
    from app.knee_job import digest
    from app.completion_job import read
    source,folder,tracking,config=tracked_fixture(tmp_path);before=digest(folder/'sam3d.json')
    def child(script,out,*args):
        frames=[]
        for i in range(3):
            mask=np.zeros((240,320),np.uint8);mask[20:40,20:40]=255
            p=out/f'{i}.png';p.write_bytes(cv2.imencode('.png',mask)[1].tobytes())
            frames.append({'frame_index':i,'objects':{'cape':{'file':p.name,'object_logit':1}}})
        write(out/'regions.json',{'frames':frames})
    monkeypatch.setattr(job,'gpu_child',child)
    out=run_internal_masks(folder,source,config)
    assert read(out/'report.json')['status']=='completed_diagnostic' and (out/'internal-mask-overlay.mp4').is_file()
    assert digest(folder/'sam3d.json')==before
    assert all(not r['pose_modified'] for r in read(out/'internal-mask-review.json')['frames'])
    from app.result_library import list_previews
    assert out/'internal-mask-overlay.mp4' in list_previews(folder.parent,folder)

def test_gpu_failure_does_not_publish_preview_or_modify_pose(tmp_path,monkeypatch):
    import app.internal_mask_job as job
    from app.knee_job import digest
    from app.completion_job import read
    source,folder,tracking,config=tracked_fixture(tmp_path);before=digest(folder/'sam3d.json')
    def fail(*a):raise RuntimeError('GPU stopped')
    monkeypatch.setattr(job,'gpu_child',fail)
    with pytest.raises(RuntimeError):run_internal_masks(folder,source,config)
    out=next(folder.glob('internal_*'))
    assert read(out/'report.json')['status']=='failed' and not (out/'internal-mask-overlay.mp4').exists()
    assert digest(folder/'sam3d.json')==before
