import json,time,shutil
import pytest
from test_knee_job import candidate_fixture
from app.automatic_postprocess import process_sam_result


def test_fast_candidates_are_explicit_and_profile_cache_is_separate(tmp_path,monkeypatch):
    import app.automatic_postprocess as auto
    from app.candidate_job import latest_selection
    source,folder,selected,_,_=candidate_fixture(tmp_path)
    source_hash=auto.load_context(folder,source)[1]
    assert latest_selection(folder,source_hash)==selected
    assert latest_selection(folder,source_hash,'body') is None
    report=json.loads((selected/'report.json').read_text())
    report['candidate_inference_type']='body'
    (selected/'report.json').write_text(json.dumps(report))
    assert latest_selection(folder,source_hash) is None
    assert latest_selection(folder,source_hash,'body')==selected
    calls=[]
    monkeypatch.setattr(auto,'latest_selection',lambda *a:None)
    monkeypatch.setattr(auto,'run_candidates',lambda *a,**kw:(calls.append(kw) or selected,{}))
    monkeypatch.setattr(auto,'latest_part_result',lambda *a:folder)
    monkeypatch.setattr(auto,'latest_leg_result',lambda *a:None)
    monkeypatch.setattr(auto,'ensure_reconnection',lambda *a:(folder,'computed'))
    result=process_sam_result(folder,source,candidate_inference_type='body')
    assert calls==[{'inference_type':'body'}]
    assert result['automatic_postprocess']['candidate_inference_type']=='body'


def test_unknown_candidate_profile_does_not_create_results(tmp_path):
    from app.candidate_job import run_candidates
    with pytest.raises(ValueError):run_candidates(tmp_path,tmp_path/'missing.mp4',inference_type='invalid')
    with pytest.raises(ValueError):process_sam_result(tmp_path,tmp_path/'missing.mp4',candidate_inference_type='invalid')
    assert not list(tmp_path.iterdir())

def test_automatic_stages_run_in_order(tmp_path,monkeypatch):
    import app.automatic_postprocess as auto
    source,folder,selected,_,_=candidate_fixture(tmp_path);calls=[];leg=folder/'leg_result';leg.mkdir()
    monkeypatch.setattr(auto,'latest_selection',lambda *a:None);monkeypatch.setattr(auto,'latest_leg_result',lambda *a:None)
    monkeypatch.setattr(auto,'latest_part_result',lambda *a:None)
    monkeypatch.setattr(auto,'run_candidates',lambda *a:(calls.append('candidate') or selected,{}))
    monkeypatch.setattr(auto,'run_part_reestimation',lambda *a:(calls.append('part') or leg,{}))
    monkeypatch.setattr(auto,'ensure_reconnection',lambda *a:(calls.append('reconnect') or leg,'computed'))
    result=process_sam_result(folder,source)
    assert calls==['candidate','part','reconnect'] and result['automatic_postprocess']['status']=='completed_with_estimates'
    report=result['automatic_postprocess']
    assert set(report['stage_seconds'])==set(report['stages'])
    assert all(t>=0 for t in report['stage_seconds'].values())
    assert report['seconds']>=sum(report['stage_seconds'].values())

def test_completed_stages_are_reused(tmp_path,monkeypatch):
    import app.automatic_postprocess as auto
    source,folder,selected,_,_=candidate_fixture(tmp_path);leg=folder/'leg_result';leg.mkdir()
    raw,source_hash,_=auto.load_context(folder,source)
    packet,_=auto.ensure_fullbody(folder,source,selected,raw,source_hash)
    auto.ensure_joint_review(folder,source,packet,source_hash)
    monkeypatch.setattr(auto,'latest_leg_result',lambda *a:leg/'leg-overlay.mp4')
    monkeypatch.setattr(auto,'latest_part_result',lambda *a:leg)
    monkeypatch.setattr(auto,'run_candidates',lambda *a:pytest.fail('must reuse candidate'))
    monkeypatch.setattr(auto,'run_part_reestimation',lambda *a:pytest.fail('must reuse parts'))
    monkeypatch.setattr(auto,'ensure_reconnection',lambda *a:(leg,'reused'))
    result=process_sam_result(folder,source)
    assert set(result['automatic_postprocess']['stages'].values())=={'reused'}

def test_part_failure_keeps_completed_selection(tmp_path,monkeypatch):
    import app.automatic_postprocess as auto
    source,folder,selected,_,_=candidate_fixture(tmp_path)
    monkeypatch.setattr(auto,'latest_leg_result',lambda *a:None)
    monkeypatch.setattr(auto,'latest_part_result',lambda *a:None)
    def fail(*a):raise ValueError('feet outside first frame')
    monkeypatch.setattr(auto,'run_part_reestimation',fail)
    result=process_sam_result(folder,source)
    assert result['candidate_selection_directory']==str(selected) and 'leg_result_directory' not in result
    assert result['automatic_postprocess']['status']=='partial'
    assert result['automatic_postprocess']['stage_seconds']['part_reestimation']>=0
    assert json.loads((folder/'automatic-report.json').read_text(encoding='utf-8'))['stages']['part_reestimation']=='failed'

def test_candidate_failure_does_not_start_leg_job(tmp_path,monkeypatch):
    import app.automatic_postprocess as auto
    source,folder,*_=candidate_fixture(tmp_path)
    monkeypatch.setattr(auto,'latest_selection',lambda *a:None)
    def fail(*a):raise RuntimeError('candidate failed')
    monkeypatch.setattr(auto,'run_candidates',fail);monkeypatch.setattr(auto,'run_part_reestimation',lambda *a:pytest.fail('should not run'))
    result=process_sam_result(folder,source)
    assert result['automatic_postprocess']['status']=='partial' and 'candidate_selection_directory' not in result

def test_cancel_between_stages_is_not_failure(tmp_path,monkeypatch):
    import app.automatic_postprocess as auto
    source,folder,*_=candidate_fixture(tmp_path);state=[False]
    def find(*a):state[0]=True;return folder/'selected'
    monkeypatch.setattr(auto,'latest_selection',find)
    with pytest.raises(KeyboardInterrupt):process_sam_result(folder,source,lambda:state[0])
    assert json.loads((folder/'automatic-report.json').read_text(encoding='utf-8'))['status']=='cancelled'

@pytest.mark.parametrize('fast',[False,True])
def test_gui_output_runs_automatic_pipeline_and_has_no_manual_controls(tmp_path,monkeypatch,fast):
    import app.gui as gui
    import app.automatic_postprocess as auto
    from tkinterdnd2 import TkinterDnD
    source,folder,selected,_,_=candidate_fixture(tmp_path);leg=folder/'leg_result';leg.mkdir();shutil.copy2(source,leg/'leg-overlay.mp4');calls=[]
    shutil.copy2(source,selected/'fullbody-reference.mp4')
    shutil.copy2(source,selected/'joint-review.mp4')
    shutil.copy2(source,leg/'part-overlay.mp4')
    shutil.copy2(source,leg/'reconnection-overlay.mp4')
    monkeypatch.setattr(gui,'new_output',lambda *a:folder)
    monkeypatch.setattr(gui,'run_job',lambda *a:(calls.append('extract') or {'frames_processed':3,'frames_with_target':3,'warnings':[]}))
    def post(*a,**kwargs):
        assert kwargs==({'candidate_inference_type':'body'} if fast else {})
        calls.append('automatic');return {'candidate_selection_directory':str(selected),'leg_result_directory':str(leg),'part_result_directory':str(leg),'reconnection_directory':str(leg),'automatic_postprocess':{'status':'completed_with_estimates','errors':{}}}
    monkeypatch.setattr(auto,'process_sam_result',post)
    root=TkinterDnD.Tk();root.withdraw();app=gui.PrototypeApp(root)
    try:
        assert not app.fast_candidates.get()
        app.fast_candidates.set(fast)
        for name in ('joint_button','knee_button','leg_trial_button','leg_reestimate_button','select_candidates_button','auto_candidates'):assert not hasattr(app,name)
        assert app.settings().stage=='sam3d' and app.settings().anchors is None
        app.source=source;app.start();deadline=time.monotonic()+10
        while app.busy:
            root.update();time.sleep(.01);assert time.monotonic()<deadline
        assert calls==['extract','automatic']
        assert app.result_kind.get()=='재관측 연결 비교' and app.capture is not None
        assert '다리 재추정 비교' in app.kind_box['values']
        assert '전신 기준축' in app.kind_box['values']
        assert '관절 검사' in app.kind_box['values']
        app.result_kind.set('관절 검사');app.change_view();assert app.capture is not None
        app.result_kind.set('전신 기준축');app.change_view();assert app.capture is not None
    finally:app.pause();app.stop_video();root.destroy()

def test_gui_existing_sam_automatically_resumes_and_opens_latest(tmp_path,monkeypatch):
    import app.gui as gui
    import app.automatic_postprocess as auto
    from tkinterdnd2 import TkinterDnD
    source,folder,selected,_,_=candidate_fixture(tmp_path);leg=folder/'leg_result';leg.mkdir();shutil.copy2(source,leg/'leg-overlay.mp4');calls=[]
    shutil.copy2(source,selected/'fullbody-reference.mp4')
    shutil.copy2(source,selected/'joint-review.mp4')
    shutil.copy2(source,leg/'part-overlay.mp4')
    shutil.copy2(source,leg/'reconnection-overlay.mp4')
    monkeypatch.setattr(gui.filedialog,'askopenfilename',lambda **kw:str(folder/'sam3d.json'))
    def post(*a):
        calls.append(a[:2]);return {'candidate_selection_directory':str(selected),'leg_result_directory':str(leg),'part_result_directory':str(leg),'reconnection_directory':str(leg),'automatic_postprocess':{'status':'completed_with_estimates','errors':{}}}
    monkeypatch.setattr(auto,'process_sam_result',post)
    root=TkinterDnD.Tk();root.withdraw();app=gui.PrototypeApp(root)
    try:
        app.open_sam_result();deadline=time.monotonic()+10
        while app.busy:
            root.update();time.sleep(.01);assert time.monotonic()<deadline
        assert calls and app.result_dir==folder and app.source==source
        assert app.result_kind.get()=='재관측 연결 비교' and app.capture is not None
        assert '전신 기준축' in app.kind_box['values']
        assert '관절 검사' in app.kind_box['values']
    finally:app.pause();app.stop_video();root.destroy()
