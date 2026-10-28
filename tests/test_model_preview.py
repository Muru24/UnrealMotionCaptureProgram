import hashlib,json,time
import cv2
import numpy as np
import pytest
from app.model_preview import prepare_model_preview,describe,discover_models


def clip(path,fps=20,count=8,base=30,size=(160,120)):
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),fps,size)
    assert writer.isOpened()
    for i in range(count):writer.write(np.full((size[1],size[0],3),base+10*i,np.uint8))
    writer.release()


def legacy(tmp_path):
    source=tmp_path/'source.mp4';clip(source)
    folder=tmp_path/'result';folder.mkdir();track=folder/'overlay.mp4';clip(track,10,4,80)
    path=folder/'model-comparison.mp4'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),10,(1536,640))
    assert writer.isOpened()
    for i in range(4):
        frame=np.zeros((640,1536,3),np.uint8);frame[40:,1024:]=150+i*10;writer.write(frame)
    writer.release()
    path.with_suffix('.json').write_text(json.dumps({'status':'completed','panels':['original','tracking','model'],
        'source':str(source),'tracking':str(track),'frames':4,'fps':10}))
    return source,folder,track,path


def test_result_defaults_to_newest_completed_model(tmp_path):
    import os
    from app.model_preview import model_asset
    source,folder,track,old=legacy(tmp_path)
    new=folder/'model-preview-engine.mp4';clip(new)
    new.with_suffix('.json').write_text(json.dumps({'status':'completed','schema':'model_preview_v1',
        'source':str(source),'tracking':str(track)}))
    os.utime(old,(10,10));os.utime(new,(20,20))
    assert model_asset(folder,track).path==new


def test_legacy_migration_preserves_original_and_reuses_verified_model_only(tmp_path):
    source,folder,track,path=legacy(tmp_path)
    signature=hashlib.sha256(path.read_bytes()).hexdigest()
    output=prepare_model_preview(path)
    assert output!=path and describe(output).source==source and not describe(output).legacy
    reader=cv2.VideoCapture(str(output));ok,frame=reader.read();reader.release()
    assert ok and frame.shape==(600,512,3) and abs(frame.mean()-150)<6
    assert hashlib.sha256(path.read_bytes()).hexdigest()==signature
    assert prepare_model_preview(path)==output
    found=discover_models(tmp_path)
    assert len(found)==1 and found[0][1].path==output


def test_unknown_layout_and_cancellation_do_not_publish_model(tmp_path):
    source,folder,track,path=legacy(tmp_path)
    with pytest.raises(KeyboardInterrupt):prepare_model_preview(path,lambda:True)
    assert not list(folder.glob('model-preview*.mp4'))
    stop=[False]
    def progress(done,total):stop[0]=done>=2
    with pytest.raises(KeyboardInterrupt):prepare_model_preview(path,lambda:stop[0],progress)
    assert not list(folder.glob('*model-preview*.mp4'))
    path.with_suffix('.json').write_text(json.dumps({'status':'completed','panels':['original','tracking']}))
    with pytest.raises(ValueError):prepare_model_preview(path)
    assert not list(folder.glob('model-preview*.mp4'))


def test_new_render_export_also_saves_separate_model_asset(tmp_path):
    from tools.compose_model_preview import run
    source=tmp_path/'source.mp4';clip(source,20,3,30)
    tracking=tmp_path/'overlay.mp4';clip(tracking,20,3,80)
    frames=tmp_path/'모델 프레임';frames.mkdir()
    (frames/'render.json').write_text(json.dumps({'fps':20,'frames':3}))
    for i in range(3):
        ok,png=cv2.imencode('.png',np.full((120,160,3),50+i*10,np.uint8));assert ok
        png.tofile(frames/f'{i+1:05d}.png')
    run(source,tracking,frames,tmp_path/'model-comparison.mp4')
    asset=describe(tmp_path/'model-preview.mp4')
    assert asset and not asset.legacy and asset.source==source
    cap=cv2.VideoCapture(str(asset.path));ok,frame=cap.read();count=cap.get(cv2.CAP_PROP_FRAME_COUNT);cap.release()
    assert ok and frame.shape==(120,160,3) and count==3


def test_jpeg_intermediates_cleanup_only_after_verified_video(tmp_path):
    from app.model_preview import encode_model_frames,cleanup_model_frames
    frames=tmp_path/'frames';frames.mkdir()
    (frames/'render.json').write_text(json.dumps({'fps':20,'frames':3,'image_extension':'jpg'}))
    for i in range(3):
        ok,data=cv2.imencode('.jpg',np.full((120,160,3),60+i*10,np.uint8));assert ok
        data.tofile(frames/f'{i+1:05d}.jpg')
    (frames/'keep.txt').write_text('preserve')
    target=tmp_path/'model-preview.mp4'
    assert cleanup_model_frames(frames,target)==0 and len(list(frames.glob('*.jpg')))==3
    encode_model_frames(tmp_path/'original.mp4',tmp_path/'overlay.mp4',frames,target)
    assert cleanup_model_frames(frames,target)>0
    assert target.is_file() and not list(frames.glob('*.jpg'))
    assert (frames/'keep.txt').read_text()=='preserve' and (frames/'render.json').is_file()


def test_gui_model_pair_uses_original_time_and_async_migration(tmp_path):
    from tkinterdnd2 import TkinterDnD
    from app.gui import PrototypeApp
    source,folder,track,path=legacy(tmp_path)
    root=TkinterDnD.Tk();root.withdraw();app=PrototypeApp(root)
    try:
        app.preview_saved_result(folder,path)
        app.seek_var.set(4);app.seek_end()
        app.studio.show_stage(2)
        deadline=time.monotonic()+10
        while app.busy:
            root.update();time.sleep(.01)
            assert time.monotonic()<deadline
        assert app.model_capture is not None and app.tracking_capture is None
        assert app.preview_path==source and app.preview_is_original
        assert app.position==4 and app.model_capture.last_index==2
        app.seek_var.set(4);app.seek_end()
        assert abs(app.frame.mean()-70)<6 and app.model_capture.last_index==2
        reference=cv2.VideoCapture(str(app.model_capture.path));reference.set(cv2.CAP_PROP_POS_FRAMES,2)
        ok,expected=reference.read();reference.release()
        assert ok and np.array_equal(app.model_frame,expected)
        separated=app.model_capture.path;decoder=app.model_capture
        app.studio.show_stage(1)
        assert app.model_capture is None and not decoder.capture.isOpened()
        app.studio.show_stage(0);assert app.tracking_capture is not None
        app.studio.show_stage(2);assert not app.busy and app.model_capture.path==separated
        app.stop_video();source.rename(tmp_path/'moved.mp4')
        app.preview_saved_result(folder,separated)
        assert not app.preview_is_original and app.preview_is_model
        assert app.preview_path==separated and app.model_capture is None
    finally:
        app.cancel_event.set()
        if app.worker:app.worker.join(10)
        app.stop_video();root.destroy()
