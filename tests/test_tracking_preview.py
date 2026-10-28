import json
from pathlib import Path
import cv2
import numpy as np
from app.tracking_preview import CompanionVideo,tracking_assets


def video(path,fps,count,base):
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),fps,(160,120))
    assert writer.isOpened()
    for i in range(count):writer.write(np.full((120,160,3),base+i*10,np.uint8))
    writer.release()


def test_timestamp_seek_mismatched_fps_and_short_result(tmp_path):
    path=tmp_path/'track.mp4';video(path,10,3,80)
    companion=CompanionVideo(path)
    try:
        assert abs(companion.frame_at(.2).mean()-100)<6
        assert abs(companion.frame_at(0).mean()-80)<6
        assert companion.frame_at(.4) is None
        assert abs(companion.frame_at(.1).mean()-90)<6
    finally:companion.close()
    assert not companion.capture.isOpened()


def test_assets_require_explicit_source_and_single_tracking_video(tmp_path):
    source=tmp_path/'source.mp4';source.touch()
    result=tmp_path/'result';result.mkdir();track=result/'overlay.mp4';track.touch()
    (result/'model-comparison.mp4').touch()
    (result/'gui-preview.json').write_text(json.dumps({'source':str(source)}))
    assert tracking_assets(result)==(source,track)
    source.unlink()
    assert tracking_assets(result)==(None,track)
    track.unlink()
    assert tracking_assets(result)==(None,None)


def test_gui_stage_one_uses_independent_assets_and_releases_decoders(tmp_path):
    from tkinterdnd2 import TkinterDnD
    from app.gui import PrototypeApp
    source=tmp_path/'source.mp4';video(source,20,8,30)
    folder=tmp_path/'saved';folder.mkdir()
    tracking=folder/'overlay.mp4';video(tracking,10,3,80)
    combined=folder/'model-comparison.mp4';video(combined,20,8,180)
    (folder/'sam-request.json').write_text(json.dumps({'source':str(source)}))
    root=TkinterDnD.Tk();root.withdraw();app=PrototypeApp(root)
    try:
        app.source=source;app.open_video(source)
        app.events.put(('candidates',(np.full((120,160,3),200,np.uint8),1,2)))
        app.poll()
        assert abs(app.frame.mean()-50)<6
        assert app.candidate_preview_frame.mean()==200
        app.preview_saved_result(folder,combined)
        assert app.preview_path==source and app.preview_is_original
        assert app.tracking_capture.path==tracking
        assert abs(app.frame.mean()-30)<6 and abs(app.tracking_frame.mean()-80)<6
        app.seek_var.set(4);app.seek_end()
        assert abs(app.frame.mean()-70)<6 and abs(app.tracking_frame.mean()-100)<6
        old=app.tracking_capture
        app.studio.show_stage(2)
        assert not old.capture.isOpened()
        assert app.preview_path==source and app.position==4
        assert app.model_capture is None and not app.preview_is_model
        assert abs(app.frame.mean()-70)<6
        app.studio.show_stage(0)
        assert app.preview_path==source and app.position==4
        app.seek_var.set(7);app.seek_end()
        assert app.tracking_frame is None
        app.seek_var.set(0);app.seek_end()
        assert app.tracking_frame is not None
        app.stop_video()
        source.rename(tmp_path/'missing-original.mp4')
        app.preview_saved_result(folder,combined)
        assert not app.preview_is_original and app.preview_is_tracking
        assert app.preview_path==tracking
        assert '원본 경로' in app.detail_text.get()
        cap=app.capture
        app.before_result_delete(folder)
        assert not cap.isOpened() and app.tracking_capture is None
    finally:app.stop_video();root.destroy()


def test_stage_two_original_and_bones_follow_time_not_frame_number(tmp_path):
    from tkinterdnd2 import TkinterDnD
    from app.gui import PrototypeApp
    source=tmp_path/'source.mp4';video(source,20,8,30)
    folder=tmp_path/'saved';folder.mkdir()
    tracking=folder/'overlay.mp4';video(tracking,10,3,80)
    combined=folder/'comparison.mp4';video(combined,20,8,180)
    (folder/'sam-request.json').write_text(json.dumps({'source':str(source)}))
    motion=folder/'motion';motion.mkdir()
    bones=[{'name':'root','parent':None},{'name':'pelvis','parent':'root'},{'name':'head','parent':'pelvis'}]
    packet={'schema':'standard_motion_positions_v1','source_kind':'test','video':{'fps':10},
            'skeleton':{'bones':bones},'frames':[{'positions':[[0,0,0],[0,0,1],[i*.1,0,1.5]]} for i in range(3)]}
    path=motion/'motion.json';path.write_text(json.dumps(packet))
    root=TkinterDnD.Tk();root.withdraw();app=PrototypeApp(root)
    try:
        app.preview_saved_result(folder,combined)
        app.seek_var.set(4);app.seek_end()
        app.studio.show_stage(1)
        assert app.preview_path==source and app.preview_is_original
        assert app.tracking_capture is None and app.position==4
        assert abs(app.frame.mean()-70)<6
        assert app.skeleton_panel.position==2 and app.skeleton_panel.fps==10
        assert app.skeleton_panel.points[2,2,0]==np.float32(.2)
        assert not app.kind_box.winfo_manager()
        app.seek_var.set(7);app.seek_end()
        assert app.skeleton_panel.position>=len(app.skeleton_panel.points)
        assert any('범위' in app.skeleton_panel.canvas.itemcget(i,'text') for i in app.skeleton_panel.canvas.find_all())
        app.seek_var.set(0);app.seek_end()
        assert app.skeleton_panel.position==0
        app.studio.show_stage(2);assert app.preview_path==source
        app.studio.show_stage(1);assert app.preview_path==source
        app.seek_var.set(4);app.seek_end()
        app.events.put(('motionready',str(path)));app.poll()
        assert app.skeleton_panel.position==2
        other=tmp_path/'without-motion';other.mkdir()
        (other/'sam-request.json').write_text(json.dumps({'source':str(source)}))
        video(other/'overlay.mp4',10,3,80)
        app.preview_saved_result(other,other/'overlay.mp4')
        assert app.skeleton_panel.points is None
        assert '본 데이터 없음' in app.skeleton_panel.empty_message
    finally:app.stop_video();root.destroy()


def test_tracking_ready_can_preview_while_postprocessing_stays_busy(tmp_path):
    from tkinterdnd2 import TkinterDnD
    from app.gui import PrototypeApp
    source=tmp_path/'source.mp4';video(source,20,8,30)
    folder=tmp_path/'in-progress';folder.mkdir();video(folder/'overlay.mp4',20,8,80)
    (folder/'sam-request.json').write_text(json.dumps({'source':str(source)}))
    root=TkinterDnD.Tk();root.withdraw();app=PrototypeApp(root)
    try:
        app.source=source;app.run_output=folder;app.busy=True;app.set_busy(True)
        app.events.put(('trackingready',folder));app.poll()
        assert app.busy and app.source==source and app.result_dir==folder
        assert app.frame is not None and app.tracking_frame is not None
        assert str(app.start_button['state'])=='disabled'
        assert str(app.result_panel.delete_button['state'])=='disabled'
        assert str(app.play_button['state'])=='normal'
        app.seek_var.set(4);app.seek_end();assert app.position==4
        app.studio.show_stage(1)
        assert app.skeleton_panel.points is None and '본 생성 대기' in app.skeleton_panel.empty_message
    finally:app.busy=False;app.stop_video();root.destroy()
