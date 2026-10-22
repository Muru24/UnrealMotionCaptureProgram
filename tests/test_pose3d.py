import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS

import cv2
import numpy as np
import pytest

from app.processing3d import process_pose3d
from core.pose2d.interface import COCO17, Keypoint2D, Pose2DResult, TrackingInfo
from core.pose2d.tracker import TargetTracker
from core.pose3d.interface import (COCO_TO_MP, LANDMARK33, Landmark3D, Pose3DError,
                                  Pose3DResult, missing_landmarks)
from core.pose3d.mediapipe_backend import (MODEL_SHA256, MediaPipeBackend,
                                          candidate_box, convert_landmarks, validate_model)
from core.pose3d.mediapipe_backend import duplicate_observation


def observations():
    image = [NS(x=.3+i*.01, y=.2+i*.01, z=.02, visibility=.9, presence=.8) for i in range(33)]
    world = [NS(x=i*.01, y=i*.02, z=-.2) for i in range(33)]
    return image, world


def test_native_units_pixel_conversion_and_joint_mapping():
    image, world = observations()
    points = convert_landmarks(image, world, 720, 1280)
    assert points[11].x == pytest.approx(.11)  # never multiply native meters by image scale
    assert points[11].image_x == pytest.approx(.41*720)
    assert points[11].image_y == pytest.approx(.31*1280)
    assert points[11].image_z_normalized == .02
    assert points[11].visibility == .9 and points[11].presence == .8
    assert tuple(LANDMARK33[i] for i in COCO_TO_MP) == COCO17


@pytest.mark.parametrize('field,value,reason', [
    ('x', float('nan'), 'nonfinite_or_missing'), ('x', -1., 'out_of_frame'),
    ('visibility', .1, 'low_visibility'), ('presence', .2, 'low_presence'),
    ('visibility', None, 'nonfinite_or_missing'),
])
def test_bad_observations_are_masked_without_inventing_positions(field, value, reason):
    image, world = observations()
    setattr(image[4], field, value)
    points = convert_landmarks(image, world, 100, 200)
    assert not points[4].valid and points[4].reason == reason
    assert points[4].x == world[4].x  # invalid flags do not overwrite finite raw measurements
    json.dumps([p.__dict__ for p in points], allow_nan=False)


def test_nonfinite_world_and_missing_pose_not_zero_motion():
    image, world = observations()
    world[0].z = float('inf')
    points = convert_landmarks(image, world, 720, 1280)
    assert points[0].z is None and not points[0].valid
    missing = missing_landmarks('target_unavailable')
    assert len(missing) == 33 and all(p.x is None and not p.valid for p in missing)
    with pytest.raises(Pose3DError, match='33'):
        convert_landmarks(image[:-1], world, 720, 1280)


def test_invisible_hair_or_extrapolated_point_does_not_expand_candidate():
    image, world = observations()
    points = convert_landmarks(image, world, 720, 1280)
    before = candidate_box(points, 720, 1280)
    points = list(points)
    points[0] = replace(points[0], image_x=700., image_y=1., visibility=.1, valid=False)
    after = candidate_box(points, 720, 1280)
    assert after[2] <= before[2] and after[1] >= before[1]
    assert candidate_box(missing_landmarks('missing'), 720, 1280) is None


def test_manifest_cannot_authorize_unknown_weights_or_traversal(tmp_path):
    (tmp_path/'manifest.json').write_text(json.dumps({'file': '../evil.task', 'sha256': MODEL_SHA256}))
    with pytest.raises(Pose3DError, match='manifest'):
        validate_model(tmp_path)
    (tmp_path/'manifest.json').write_text(json.dumps({'file':'pose_landmarker_full.task', 'sha256':MODEL_SHA256}))
    (tmp_path/'pose_landmarker_full.task').write_bytes(b'wrong model')
    with pytest.raises(Pose3DError, match='integrity'):
        validate_model(tmp_path)
    with pytest.raises(Pose3DError, match='local'):
        validate_model(Path('//host/models'))


def test_tracking_does_not_fill_lost_frames_or_choose_another_pose(monkeypatch):
    backend = MediaPipeBackend.__new__(MediaPipeBackend)
    backend.tracker = TargetTracker(target_index=0)
    image, world = observations()
    points = convert_landmarks(image, world, 320, 240)
    box = np.array([30., 20., 160., 230.], dtype=np.float32)
    frames = [[(box, points)], [], [(box, points)]]
    monkeypatch.setattr(backend, '_candidates', lambda *args: frames.pop(0))
    monkeypatch.setattr(backend, '_recover_candidates', lambda *args: [])
    resets = []
    monkeypatch.setattr(backend, 'close', lambda: resets.append('close'))
    monkeypatch.setattr(backend, '_create_landmarker', lambda: resets.append('create'))
    frame = np.full((240, 320, 3), 100, np.uint8)
    a, b, c = [backend.infer(frame, i*33) for i in range(3)]
    assert a.pose2d.tracking.state == c.pose2d.tracking.state == 'tracked'
    assert b.pose2d.tracking.state == 'uncertain'
    assert all(p.x is None and not p.valid for p in b.landmarks)
    assert resets == ['close', 'create']


def test_timestamp_validation_prevents_native_call():
    backend = MediaPipeBackend.__new__(MediaPipeBackend)
    backend.landmarker = object()
    backend._last_timestamp = 33
    with pytest.raises(Pose3DError, match='increase'):
        backend._candidates(np.zeros((32,32,3),np.uint8),33)


def test_overlapping_bodies_are_not_deduplicated_only_because_boxes_match():
    points=convert_landmarks(*observations(),320,240)
    box=np.array([10.,10.,200.,230.],dtype=np.float32)
    assert duplicate_observation((box,points),(box,points))
    shifted=tuple(replace(p,image_x=p.image_x+30) for p in points)
    assert not duplicate_observation((box,points),(box,shifted))


def test_select_second_candidate_preserves_its_world_observations(monkeypatch):
    backend=MediaPipeBackend.__new__(MediaPipeBackend)
    backend.tracker=TargetTracker(target_index=1)
    left=convert_landmarks(*observations(),320,240)
    right=tuple(replace(p,x=p.x+.25,image_x=p.image_x+160) for p in left)
    boxes=[(np.array([10.,10.,145.,230.],dtype=np.float32),left),
           (np.array([170.,10.,310.,230.],dtype=np.float32),right)]
    monkeypatch.setattr(backend,'_candidates',lambda *args: boxes)
    result=backend.infer(np.full((240,320,3),90,np.uint8),0)
    assert result.landmarks is right
    assert result.pose2d.person_bbox[0]==170.


def test_korean_model_path_is_given_to_sdk_as_verified_buffer(monkeypatch):
    import mediapipe as mp
    backend=MediaPipeBackend.__new__(MediaPipeBackend)
    backend.model_bytes=b'verified local task'
    backend.max_people=4
    observed=[]
    monkeypatch.setattr(mp.tasks.vision.PoseLandmarker,'create_from_options',lambda o: observed.append(o) or object())
    backend._create_landmarker()
    assert observed[0].base_options.model_asset_path is None
    assert observed[0].base_options.model_asset_buffer==backend.model_bytes


@pytest.fixture
def clip3d(tmp_path):
    path=tmp_path/'한글 입력.mp4'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),30,(320,240))
    assert writer.isOpened()
    for _ in range(4): writer.write(np.full((240,320,3),80,np.uint8))
    writer.release()
    return path


class Stub3D:
    name='stub3d'
    selection_config={}
    def __init__(self, missing=False, fail_after=None):
        self.calls=0
        self.missing=missing
        self.fail_after=fail_after
    def reset_tracking(self): self.calls=0
    def infer(self, frame, timestamp):
        if self.calls == self.fail_after: raise Pose3DError('inference failed')
        self.calls+=1
        points = convert_landmarks(*observations(), 320,240)
        box=(20.,20.,250.,220.)
        if self.missing:
            points=missing_landmarks('target_unavailable'); box=None
        info=TrackingInfo('lost' if self.missing else 'tracked','test',1,6 if self.missing else 0,self.missing)
        coco=tuple(Keypoint2D(points[i].image_x or 0.,points[i].image_y or 0.,.8,points[i].valid) for i in COCO_TO_MP)
        return Pose3DResult(Pose2DResult(box,coco,0 if self.missing else 1,info),points)


def test_guidance_sidecar_never_overwrites_raw_world(clip3d,tmp_path):
    a,b=tmp_path/'raw',tmp_path/'guided'
    process_pose3d(clip3d,a,Stub3D())
    backend=Stub3D()
    report=process_pose3d(clip3d,b,backend,anchors={0:{'left_wrist':[120,150]}})
    assert json.loads((a/'pose3d.json').read_text())['frames']==json.loads((b/'pose3d.json').read_text())['frames']
    guided=json.loads((b/'guidance2d.json').read_text())
    assert guided['frames'][0]['joints']['left_wrist']['state']=='manual'
    assert len(guided['frames'])==4 and backend.joint_guide is None
    assert 'manual_2d_guidance_world_unchanged' in report['warnings']


def test_guidance_cancel_closes_sidecar_and_clears_state(clip3d,tmp_path):
    out=tmp_path/'cancel_guided';backend=Stub3D()
    with pytest.raises(KeyboardInterrupt):
        process_pose3d(clip3d,out,backend,anchors={0:{'left_wrist':[120,150]},3:{'left_wrist':[120,150]}},
                       cancelled=lambda:backend.calls==2)
    doc=json.loads((out/'guidance2d.json').read_text())
    assert doc['status']=='cancelled' and len(doc['frames'])==2
    assert backend.joint_guide is None
    report=json.loads((out/'report.json').read_text())
    assert report['unused_anchor_frames']==[3] and 'joint_anchors_unapplied' in report['warnings']


def test_second_pass_preserves_raw_and_writes_playable_comparison(clip3d,tmp_path):
    from app.completion_job import run_completion
    source=tmp_path/'raw';process_pose3d(clip3d,source,Stub3D())
    before=(source/'pose3d.json').read_bytes()
    out,counts=run_completion(source)
    assert (source/'pose3d.json').read_bytes()==before
    data=json.loads((out/'completion3d.json').read_text())
    assert len(data['frames'])==4 and sum(counts.values())==4*33
    cap=cv2.VideoCapture(str(out/'completion3d.mp4'));n=0
    while cap.read()[0]:n+=1
    cap.release();assert n==4


def test_cancel_second_pass_marks_partial_without_overwriting_raw(clip3d,tmp_path):
    from app.completion_job import run_completion
    source=tmp_path/'raw';process_pose3d(clip3d,source,Stub3D())
    before=(source/'pose3d.json').read_bytes();calls=[0]
    def stop():
        calls[0]+=1
        return calls[0]>7
    with pytest.raises(KeyboardInterrupt):run_completion(source,stop)
    folders=list(source.glob('completion_*'));assert len(folders)==1
    report=json.loads((folders[0]/'report.json').read_text())
    assert report['status']=='cancelled' and report['frames_written']==2
    assert not (folders[0]/'completion3d.json').exists()
    assert (source/'pose3d.json').read_bytes()==before


def test_second_pass_rejects_cancelled_first_pass(clip3d,tmp_path):
    from app.completion_job import run_completion
    source=tmp_path/'partial';backend=Stub3D()
    with pytest.raises(KeyboardInterrupt):
        process_pose3d(clip3d,source,backend,cancelled=lambda:backend.calls==2)
    with pytest.raises(ValueError,match='Finish first-pass'):
        run_completion(source)
    assert not list(source.glob('completion_*'))


def test_export_alignment_and_two_playable_videos(clip3d,tmp_path):
    out=tmp_path/'결과'
    report=process_pose3d(clip3d,out,Stub3D())
    assert report['frames_processed']==report['frames_with_target']==4
    docs=[json.loads((out/n).read_text()) for n in ['pose3d.json','pose2d.json','tracking.json']]
    for d in docs:
        assert d['status']=='completed'
        assert [f['frame_index'] for f in d['frames']]==[0,1,2,3]
        assert d['frames'][-1]['timestamp']==pytest.approx(.1)
    assert docs[0]['root_motion'] is False and len(docs[0]['joint_names'])==33
    assert len(docs[1]['frames'][0]['keypoints'])==17
    for name,size in [('overlay.mp4',(320,240)),('preview3d.mp4',(1280,720))]:
        cap=cv2.VideoCapture(str(out/name)); frames=[]
        while True:
            ok,f=cap.read()
            if not ok: break
            frames.append(f)
        cap.release()
        assert len(frames)==4 and frames[0].shape[1::-1]==size


@pytest.mark.parametrize('mode', ['cancel','fail','missing'])
def test_partial_and_missing_outputs_remain_truthful(clip3d,tmp_path,mode):
    out=tmp_path/mode
    backend=Stub3D(missing=mode=='missing',fail_after=2 if mode=='fail' else None)
    if mode=='missing':
        report=process_pose3d(clip3d,out,backend)
        assert report['frames_with_target']==0 and report['valid_joint_ratio']==0
    else:
        with pytest.raises(KeyboardInterrupt if mode=='cancel' else Pose3DError):
            process_pose3d(clip3d,out,backend,cancelled=lambda: mode=='cancel' and backend.calls==2)
    report=json.loads((out/'report.json').read_text())
    for name in ['pose3d.json','pose2d.json','tracking.json']:
        d=json.loads((out/name).read_text())
        assert d['status']==report['status']
        assert len(d['frames'])==report['frames_processed']
    if mode=='missing':
        assert all(p['x'] is None for f in json.loads((out/'pose3d.json').read_text())['frames'] for p in f['landmarks'])
    else: assert report['status']==('cancelled' if mode=='cancel' else 'failed')


def test_new_output_only(clip3d,tmp_path):
    out=tmp_path/'existing'; out.mkdir(); (out/'sentinel').write_text('keep')
    with pytest.raises(Pose3DError,match='never overwritten'):
        process_pose3d(clip3d,out,Stub3D())
    assert (out/'sentinel').read_text()=='keep'


def test_duplicate_observation_diagnostics_are_visible_even_with_valid_joints(clip3d,tmp_path):
    backend=Stub3D()
    backend.last_diagnostics={'raw_pose_count':2,'candidate_count':1,'duplicates_suppressed':1,
                              'box_sources':['segmentation'],
                              'suppression':[{'raw_index':1,'kept_raw_index':0,'reason':'test'}]}
    out=tmp_path/'diagnostics'
    report=process_pose3d(clip3d,out,backend)
    assert report['status']=='completed_with_warnings'
    assert report['duplicates_suppressed']==4
    assert report['frames_with_segmentation_boxes']==4
    assert 'duplicate_candidates_suppressed' in report['warnings']
    tracking=json.loads((out/'tracking.json').read_text())
    assert all(f['observation']['raw_pose_count']==2 for f in tracking['frames'])


@pytest.mark.parametrize('args', [
    ['x.mp4','--pose3d'], ['x.mp4','--pose2d','--pose3d','--output','new'],
    ['x.mp4','--pose3d','--list-targets','--output','new'],
    ['x.mp4','--pose3d','--max-people','0','--output','new'],
])
def test_cli_rejects_invalid_combinations(args):
    from app.cli import main
    with pytest.raises(SystemExit) as exc: main(args)
    assert exc.value.code==2


def test_local_model_runs_with_python_network_blocked(clip3d,monkeypatch):
    import socket
    import urllib.request
    directory=Path(__file__).resolve().parents[1]/'models/pose3d'
    if not (directory/'pose_landmarker_full.task').exists(): pytest.skip('local model not installed')
    def blocked(*args,**kwargs): raise AssertionError('runtime network is forbidden')
    monkeypatch.setattr(socket.socket,'connect',blocked)
    monkeypatch.setattr(urllib.request,'urlopen',blocked)
    backend=MediaPipeBackend(directory,max_people=1)
    cap=cv2.VideoCapture(str(clip3d)); ok,frame=cap.read(); cap.release()
    try:
        result=backend.infer(frame,0)
        assert len(result.landmarks)==33
        assert result.pose2d.person_bbox is None
        backend.tracker.box=np.array([40.,30.,240.,210.])
        result=backend.infer(frame,33)
        assert len(result.landmarks)==33
        assert result.pose2d.person_bbox is None
        assert backend.last_diagnostics['recovery']['raw_pose_count']==0
    finally: backend.close()


def test_report_separates_retry_attempts_from_accepted_observations(clip3d,tmp_path):
    for missing in [False,True]:
        backend=Stub3D(missing=missing)
        backend.last_diagnostics={'recovery':{'raw_pose_count':0 if missing else 1,
                                              'candidate_count':0 if missing else 1,
                                              'roi':[0,0,320,240]}}
        report=process_pose3d(clip3d,tmp_path/str(missing),backend)
        assert report['recovery_attempts']==4
        assert report['recovered_frames']==(0 if missing else 4)
        assert report['status']=='completed_with_warnings'
        assert 'local_crop_recovery_used' in report['warnings']
