import json
from pathlib import Path
import pytest
import app.builtin_models as models
import app.finger_job as fingers
import app.hand_refine_job as refine


def test_model_check_retries_without_publishing_failed_candidate(tmp_path,monkeypatch):
    calls=[]
    def job(script,args,*a):
        calls.append(args);candidate=Path(args[3]);candidate.mkdir()
        assert not (tmp_path/'hand-stable').exists()
        if len(calls)==1:raise RuntimeError('sole regression')
        (candidate/'animation.blend').write_bytes(b'checked')
        (candidate/'model-quality.json').write_text('{"status":"completed"}')
    monkeypatch.setattr(models,'blender_job',job)
    stable=models.finalize_model(tmp_path/'source.blend',tmp_path/'motion.blend',tmp_path/'profile.json',tmp_path,True)
    assert stable.joinpath('animation.blend').read_bytes()==b'checked'
    assert [args[-1] for args in calls]==['1.0','0.5']
    assert json.loads((stable/'model-quality.json').read_text())['attempts']==2


def test_failed_model_checks_never_publish_final(tmp_path,monkeypatch):
    calls=[]
    def fail(*a):calls.append(a);raise ValueError('invalid weights')
    monkeypatch.setattr(models,'blender_job',fail)
    with pytest.raises(RuntimeError):models.finalize_model('input.blend','motion.blend','profile.json',tmp_path,True)
    assert len(calls)==2 and not (tmp_path/'hand-stable').exists()


@pytest.mark.parametrize('cancelled',[True,False])
def test_automatic_hands_records_missing_model_fallback_and_cancellation(tmp_path,monkeypatch,cancelled):
    monkeypatch.setattr(fingers,'ROOT',tmp_path)
    raw=tmp_path/'sam3d.json';raw.write_text('{}');source=tmp_path/'video.mp4';source.write_bytes(b'video')
    (tmp_path/'sam-request.json').write_text(json.dumps({'source':str(source)}))
    out=tmp_path/'fingers';out.mkdir();(out/'report.json').write_text('{}');calls=[]
    monkeypatch.setattr(fingers,'export_fingers',lambda *a,**kw:calls.append(kw) or out/'animation.blend')
    if cancelled:
        with pytest.raises(KeyboardInterrupt):fingers.export_automatic_fingers(tmp_path/'body.blend',raw,lambda:True)
        assert not calls
    else:
        fingers.export_automatic_fingers(tmp_path/'body.blend',raw)
        report=json.loads((out/'automatic-hands.json').read_text(encoding='utf-8'))
        assert report['status']=='degraded' and report['grip_solver_applied'] is False
        assert calls==[{}] and report['errors']


def test_hand_retry_selects_crop_and_reuses_matching_provenance(tmp_path,monkeypatch):
    monkeypatch.setattr(fingers,'ROOT',tmp_path)
    model=tmp_path/'models/hand_landmarker/hand_landmarker.task';model.parent.mkdir(parents=True);model.write_bytes(b'model')
    solver=tmp_path/'app/hand_refine_job.py';solver.parent.mkdir();solver.write_bytes(b'solver')
    raw=tmp_path/'sam3d.json';raw.write_text('{}');source=tmp_path/'video.mp4';source.write_bytes(b'video')
    (tmp_path/'sam-request.json').write_text(json.dumps({'source':str(source)}));calls=[]
    def crop(*a,**kw):
        calls.append(kw);assert kw=={'comparison':False}
        if len(calls)==1:raise RuntimeError('temporary decoder failure')
        p=tmp_path/'hand_crop_1/report.json';p.parent.mkdir();p.write_text(json.dumps({'status':'completed','schema':'hand_crop_comparison_v1',
            'source_sha256':fingers.digest(source),'raw_sha256':fingers.digest(raw),'model_sha256':fingers.digest(model),'crop_solver_sha256':fingers.digest(solver)}));return p
    monkeypatch.setattr(refine,'reestimate_hands',crop)
    out=tmp_path/'finger-result';out.mkdir();(out/'report.json').write_text('{"selected_hand_frames":{"l":5,"r":0}}')
    choices=[];monkeypatch.setattr(fingers,'export_fingers',lambda *a,**kw:choices.append(kw) or out/'animation.blend')
    for _ in range(2):fingers.export_automatic_fingers(tmp_path/'body.blend',raw)
    assert len(calls)==2 and choices[0]['crop_report']==choices[1]['crop_report']
    assert json.loads((out/'automatic-hands.json').read_text(encoding='utf-8'))['refinement']=='reused'


def test_partial_checks_remain_visible_in_saved_model_metadata(tmp_path):
    variant=tmp_path/'model-result';stable=variant/'hand-stable';stable.mkdir(parents=True)
    (stable/'model-quality.json').write_text('{"status":"completed","warnings":["sole uncertain"]}')
    (tmp_path/'automatic-hands.json').write_text('{"status":"degraded"}')
    (tmp_path/'automatic-report.json').write_text('{"status":"partial"}')
    preview=variant/'model-preview.mp4';preview.with_suffix('.json').write_text('{"model_id":"user_test"}')
    models.attach_quality(preview,stable,tmp_path/'animation.blend')
    meta=json.loads(preview.with_suffix('.json').read_text(encoding='utf-8'))
    assert meta['model_id']=='user_test' and meta['weapon_grip_applied'] is False
    assert len(meta['model_quality_warnings'])==3
