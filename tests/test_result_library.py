import json
from pathlib import Path
import pytest
from app.result_library import list_results,list_previews,trash_result,list_trash,restore_result

def test_library_lists_nested_previews_and_bad_reports(tmp_path):
    result=tmp_path/'한글 결과';result.mkdir()
    (result/'report.json').write_text('[]')
    (result/'overlay.mp4').write_bytes(b'video')
    child=result/'leg_reestimate_1';child.mkdir();(child/'leg-overlay.mp4').write_bytes(b'leg')
    rows=list_results(tmp_path)
    assert len(rows)==1 and rows[0]['status']=='리포트 없음'
    assert list_previews(tmp_path,result)==[child/'leg-overlay.mp4',result/'overlay.mp4']

def test_trash_restore_preserves_files_and_never_overwrites(tmp_path):
    result=tmp_path/'result1';result.mkdir();(result/'data.bin').write_bytes(b'original')
    entry=trash_result(tmp_path,result)
    assert not result.exists() and list_results(tmp_path)==[]
    assert len(list_trash(tmp_path))==1
    result.mkdir()
    with pytest.raises(ValueError):restore_result(tmp_path,entry)
    result.rmdir()
    assert restore_result(tmp_path,entry)==result
    assert (result/'data.bin').read_bytes()==b'original' and list_trash(tmp_path)==[]

def test_moves_reject_root_outside_and_traversal(tmp_path):
    root=tmp_path/'outputs';root.mkdir();outside=tmp_path/'outside';outside.mkdir()
    for path in (root,outside):
        with pytest.raises(ValueError):trash_result(root,path)
    result=root/'result';result.mkdir();entry=trash_result(root,result)
    (entry/'metadata.json').write_text(json.dumps({'schema':'output_trash_v1','original_name':'../escape'}))
    with pytest.raises(ValueError):restore_result(root,entry)
    assert (entry/'result').is_dir()

def test_gui_library_previews_without_inference_and_releases_before_delete(tmp_path,monkeypatch):
    import cv2,numpy as np
    from tkinterdnd2 import TkinterDnD
    from app.gui import PrototypeApp
    from app.result_browser import ResultBrowser
    import app.result_browser as browser
    result=tmp_path/'saved';result.mkdir();video=result/'overlay.mp4'
    writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),30,(64,64))
    assert writer.isOpened()
    writer.write(np.zeros((64,64,3),np.uint8));writer.release()
    root=TkinterDnD.Tk();root.withdraw();app=PrototypeApp(root)
    monkeypatch.setattr(app,'launch_worker',lambda *a:pytest.fail('Preview must not infer'))
    try:
        dialog=app.result_panel;dialog.root=tmp_path;dialog.refresh()
        assert not hasattr(app,'library_button')
        assert str(dialog.window.master)==str(app.preview_split)
        dialog.tree.selection_set('0');dialog.select();dialog.preview()
        assert app.result_dir==result and app.capture is not None and app.source is None
        assert dialog.window.winfo_exists()
        app.set_busy(True);assert str(dialog.delete_button['state'])=='disabled';app.set_busy(False)
        dialog.tree.selection_set('0');monkeypatch.setattr(browser.messagebox,'askyesno',lambda *a,**k:True)
        dialog.delete()
        assert app.capture is None and app.result_dir is None and not result.exists()
        dialog.trash_tree.selection_set('0');dialog.restore();assert video.exists()
        dialog.window.destroy()
    finally:app.close()
