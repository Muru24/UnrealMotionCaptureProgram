import json,os
from pathlib import Path
import pytest
from app.final_results import list_final_results,export_final,digest


def variant(root,name,edited=False,completed=True):
    folder=root/'capture';folder.mkdir(exist_ok=True);out=folder/name;out.mkdir()
    preview=out/'model-preview.mp4';preview.write_bytes(b'video')
    preview.with_suffix('.json').write_text(json.dumps({'schema':'model_preview_v1','status':'completed','source':str(root/'clip.mp4'),'tracking':None,'frames':10,'fps':30}))
    source=out if edited else out/'hand-stable';source.mkdir(exist_ok=True)
    (source/'animation.blend').write_bytes(b'final animation')
    marker=out/'edit-report.json' if edited else source/'hand-stability.json'
    marker.write_text(json.dumps({'status':'completed' if completed else 'failed','frames':10}))
    (out/('Edited_Manny.fbx' if edited else 'Manny_Animation.fbx')).write_bytes(b'fbx')
    return preview


def test_only_completed_latest_final_per_capture_preferring_edits(tmp_path):
    auto=variant(tmp_path,'model-auto');edit=variant(tmp_path,'edit-one',True)
    os.utime(edit,(10,10));os.utime(auto,(20,20));variant(tmp_path,'edit-failed',True,False)
    raw=tmp_path/'raw';raw.mkdir();(raw/'overlay.mp4').write_bytes(b'not final')
    rows=list_final_results(tmp_path)
    assert len(rows)==1 and rows[0].preview==edit and rows[0].edited


def test_custom_edited_model_uses_its_own_delivery_fbx(tmp_path):
    preview=variant(tmp_path,'model-custom',True)
    legacy=preview.parent/'Edited_Manny.fbx';legacy.rename(preview.parent/'Model_Animation.fbx')
    info=json.loads(preview.with_suffix('.json').read_text());info['model_id']='user_test'
    preview.with_suffix('.json').write_text(json.dumps(info))
    row=list_final_results(tmp_path)[0]
    assert row.edited and row.fbx.name=='Model_Animation.fbx'
    dest=tmp_path/'delivery';dest.mkdir();out=export_final(row,dest,['fbx'])
    assert (out/'Model_Animation.fbx').read_bytes()==b'fbx'


def test_export_selected_formats_never_overwrites_or_copies_diagnostics(tmp_path):
    variant(tmp_path,'edit-final',True);row=list_final_results(tmp_path)[0]
    dest=tmp_path/'delivery';dest.mkdir();(dest/'keep.txt').write_text('keep')
    a=export_final(row,dest,['blend','fbx','mp4']);b=export_final(row,dest,['blend'])
    assert a!=b and (dest/'keep.txt').read_text()=='keep'
    assert {p.name for p in a.iterdir()}=={'Manny_Animation.blend','Manny_Animation.fbx','model-preview.mp4','export-info.json'}
    assert digest(a/'Manny_Animation.blend')==digest(row.blend)
    info=json.loads((a/'export-info.json').read_text());assert info['status']=='completed' and info['edited']
    assert str(tmp_path) not in (a/'export-info.json').read_text()


def test_cancel_cleans_only_own_partial_export_and_preserves_source(tmp_path):
    variant(tmp_path,'edit-final',True);row=list_final_results(tmp_path)[0]
    dest=tmp_path/'delivery';dest.mkdir();(dest/'keep.txt').write_text('keep');before=digest(row.blend);calls=[0]
    def cancelled():calls[0]+=1;return calls[0]>=4
    with pytest.raises(KeyboardInterrupt):export_final(row,dest,['blend','mp4'],cancelled)
    assert [p.name for p in dest.iterdir()]==['keep.txt'] and digest(row.blend)==before
    with pytest.raises(ValueError):export_final(row,dest,[])
    with pytest.raises(ValueError):export_final(row,dest,['other'])
