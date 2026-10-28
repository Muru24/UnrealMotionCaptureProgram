import json
from pathlib import Path
import pytest
from app import artifact_cache as cache
from app import animation_job as body
from app import finger_job as fingers

def test_verified_cache_refuses_corrupt_and_foreign_results(tmp_path):
    result=tmp_path/'out/animation.blend';result.parent.mkdir();result.write_bytes(b'valid')
    signature={'input':'video','version':1}
    cache.publish(tmp_path,'test',signature,result,['animation.blend'])
    assert cache.lookup(tmp_path,'test',signature)==result
    with pytest.raises(KeyboardInterrupt):cache.lookup(tmp_path,'test',signature,lambda:True)
    result.write_bytes(b'changed');assert cache.lookup(tmp_path,'test',signature) is None
    index=cache.index_path(tmp_path,'test',signature);row=json.loads(index.read_text());row['result']='../outside.blend';index.write_text(json.dumps(row))
    assert cache.lookup(tmp_path,'test',signature) is None

def test_body_export_reuses_verified_result_and_rebuilds_after_corruption(tmp_path,monkeypatch):
    from test_animation_job import motion
    source=motion(tmp_path);calls=[]
    class Process:
        returncode=0
        def poll(self):return 0
    def run(args,**kwargs):
        calls.append(args);out=Path(args[-1]);out.mkdir();(out/'animation.blend').write_bytes(b'body')
        (out/'animation.json').write_text(json.dumps({'frames':[{}],'frames_with_pose':1,'max_solved_head_error_m':0}));return Process()
    monkeypatch.setattr(body.subprocess,'Popen',run)
    first=body.export_animation(source,executable='blender.exe')
    assert body.export_animation(source,executable='blender.exe')==first and len(calls)==1
    first.write_bytes(b'corrupt')
    assert body.export_animation(source,executable='blender.exe')!=first and len(calls)==2

def test_finger_export_reuses_and_invalidates_on_solver_change(tmp_path,monkeypatch):
    from test_finger_job import fixture
    source,raw=fixture(tmp_path);calls=[]
    class Process:
        returncode=0
        def poll(self):return 0
    def run(args,**kwargs):
        calls.append(args);out=Path(args[-1]);out.mkdir();(out/'animation.blend').write_bytes(b'fingers')
        (out/'animation.json').write_text(json.dumps({'bone_names':list(range(52)),'frames':[{}]}));return Process()
    monkeypatch.setattr(fingers.subprocess,'Popen',run)
    first=fingers.export_fingers(source,raw,executable='blender.exe')
    assert fingers.export_fingers(source,raw,executable='blender.exe')==first and len(calls)==1
    original=fingers.digest
    monkeypatch.setattr(fingers,'digest',lambda p:'new-solver' if Path(p).name=='finger_limits.py' else original(p))
    assert fingers.export_fingers(source,raw,executable='blender.exe')!=first and len(calls)==2

def test_archive_backup_is_verified_and_never_changes_originals(tmp_path):
    from tools.archive_project_history import archive
    root=tmp_path/'project';root.mkdir();(root/'진행상황').mkdir();source=root/'진행상황/log.md';source.write_text('기록',encoding='utf-8')
    (root/'snapshots').mkdir();(root/'snapshots/old.zip').write_bytes(b'already archived')
    result=archive(root,tmp_path/'backup')
    assert result['status']=='verified_backup' and result['originals_changed'] is False
    assert source.read_text(encoding='utf-8')=='기록' and (root/'snapshots/old.zip').is_file()
    assert '진행상황/log.md' in result['compressed_files']
    with pytest.raises(ValueError):archive(root,root/'unsafe')
