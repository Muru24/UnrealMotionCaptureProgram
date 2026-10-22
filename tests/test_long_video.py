from types import SimpleNamespace as NS
import json

import cv2
import numpy as np
import pytest

from app.gui_jobs import read_source
from app.processing import process_pose2d
from core.pose2d.interface import Pose2DResult
from core.pose2d.sam2_memory import trim_forward_memory
from core.video.decoder import VideoInputError
from core.video.limits import validate_duration


@pytest.mark.parametrize('seconds,frames', [(60,3600),(180,5400),(300,9000),(300,18000)])
def test_supported_timelines(seconds,frames):
    validate_duration(NS(duration_seconds_estimate=seconds,frame_count=frames))


@pytest.mark.parametrize('seconds,frames', [(300.01,9001),(301,9030),(300,18001)])
def test_excess_duration_or_frame_count_has_clear_error(seconds,frames):
    with pytest.raises(VideoInputError,match='5분.*18,000'):
        validate_duration(NS(duration_seconds_estimate=seconds,frame_count=frames))


def test_caller_error_type_is_preserved():
    from core.pose3d.interface import Pose3DError
    with pytest.raises(Pose3DError,match='5분'):
        validate_duration(NS(duration_seconds_estimate=301,frame_count=9030),Pose3DError)


@pytest.mark.parametrize('stride,num_mem,pointers',[(1,7,16),(3,7,16),(5,12,64)])
def test_forward_eviction_preserves_every_next_frame_memory_lookup(stride,num_mem,pointers):
    predictor=NS(num_maskmem=num_mem,memory_temporal_stride_for_eval=stride,
                 max_obj_ptrs_in_encoder=pointers)
    initial=object();recent={};state={'output_dict_per_obj':{0:{
        'cond_frame_outputs':{0:initial},'non_cond_frame_outputs':recent}}}
    full={}
    for current in range(18000):
        if current:
            full[current]=recent[current]=object()
        trim_forward_memory(predictor,state,current)
        following=current+1
        required={following-1}
        required.update(((following-2)//stride)*stride-(rel-2)*stride
                        for rel in range(2,num_mem))
        required.update(following-offset for offset in range(1,pointers))
        for index in required:
            if index>0:
                assert recent.get(index) is full.get(index)
        assert state['output_dict_per_obj'][0]['cond_frame_outputs'][0] is initial
        assert len(recent)<=max(32,num_mem*stride+num_mem,pointers)


def test_five_minute_real_mp4_load_extract_and_decode_without_gpu(tmp_path):
    source=tmp_path/'5분 입력.mp4'
    writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*'mp4v'),60,(32,32))
    assert writer.isOpened()
    frame=np.full((32,32,3),80,np.uint8)
    for _ in range(18000):writer.write(frame)
    writer.release()
    metadata,first=read_source(source)
    assert metadata.duration_seconds_estimate==300 and metadata.frame_count==18000
    assert first.shape==(32,32,3)
    backend=NS(infer=lambda image:Pose2DResult(None,(),0))
    out=tmp_path/'result'
    report=process_pose2d(source,out,backend)
    data=json.loads((out/'pose2d.json').read_text(encoding='utf-8'))
    assert report['frames_processed']==len(data['frames'])==18000
    assert data['frames'][-1]['frame_index']==17999
    assert data['frames'][-1]['timestamp']==pytest.approx(17999/60)
    cap=cv2.VideoCapture(str(out/'overlay.mp4'));count=0
    while cap.read()[0]:count+=1
    cap.release()
    assert count==18000


def test_gui_rejects_overlong_before_first_frame_preview(monkeypatch):
    import app.gui_jobs as jobs
    monkeypatch.setattr(jobs,'inspect_video',lambda source:NS(
        duration_seconds_estimate=301,frame_count=9030))
    with pytest.raises(VideoInputError,match='5분'):
        jobs.read_source('unused.mp4')


def test_completion_accepts_long_timeline_without_filling_a_lost_target():
    from core.pose3d.completion import complete
    count=18000
    raw={'video':{'fps':60},'coordinates':'camera_relative','joint_names':['test'],
         'frames':[{'frame_index':i,'timestamp':i/60,'person_bbox':None,
                    'landmarks':[{'x':None,'y':None,'z':None,'valid':False}]}
                   for i in range(count)]}
    tracking={'frames':[{'frame_index':i,'tracking':{'state':'lost'}} for i in range(count)]}
    result=complete(raw,tracking,chains=(),leg_chains=(),foot_pairs=())
    assert len(result['frames'])==count
    assert result['frames'][-1]['timestamp']==17999/60
    assert all(row['joints'][0]['xyz'] is None for row in result['frames'])
