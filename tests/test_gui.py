from pathlib import Path
import threading
import time
from types import SimpleNamespace as NS
import tkinter as tk

import cv2
import numpy as np
import pytest

from app.gui_jobs import JobSettings, inspect_candidates, new_output, parse_drop, read_source, run_job


def test_drop_preserves_spaces_korean_and_braces():
    tcl=tk.Tcl()
    path='C:/영상 폴더/검술 {테스트} (1).mp4'
    assert parse_drop(tcl,tcl.call('list',path))==Path(path)
    with pytest.raises(ValueError,match='하나'):
        parse_drop(tcl,tcl.call('list',path,'C:/second.mp4'))
    with pytest.raises(ValueError):parse_drop(tcl,'')


def test_output_name_is_new_local_and_never_precreated(tmp_path):
    a=new_output(Path('C:/video/name 한글 % &.mp4'),'pose3d',tmp_path)
    b=new_output(Path('C:/video/name 한글 % &.mp4'),'pose3d',tmp_path)
    assert a.parent==b.parent==tmp_path and a!=b
    assert not a.exists() and not b.exists()
    assert a.name.startswith('name 한글')
    assert '%' not in a.name and '&' not in a.name


@pytest.fixture
def gui_clip(tmp_path):
    path=tmp_path/'한글 공백 {영상}.mp4'
    w=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),30,(320,240))
    assert w.isOpened()
    for _ in range(4):w.write(np.full((240,320,3),80,np.uint8))
    w.release()
    return path


def test_source_validation_and_first_frame(gui_clip):
    metadata,frame=read_source(gui_clip)
    assert metadata.frame_count==4 and frame.shape==(240,320,3)
    from core.video.decoder import VideoInputError
    with pytest.raises(VideoInputError):read_source('https://example.com/video.mp4')


def test_worker_closes_backend_on_processing_failure(monkeypatch,gui_clip,tmp_path):
    import app.processing3d
    closed=[]
    backend=NS(close=lambda:closed.append(True))
    def fail(*args,**kwargs):raise RuntimeError('model failure')
    monkeypatch.setattr(app.processing3d,'process_pose3d',fail)
    with pytest.raises(RuntimeError,match='failure'):
        run_job(gui_clip,tmp_path/'new',JobSettings(),lambda:False,lambda *args:None,
                backend_factory=lambda settings:backend)
    assert closed==[True]


def test_cancel_before_loading_does_not_initialize_model(gui_clip,tmp_path):
    calls=[]
    with pytest.raises(KeyboardInterrupt):
        run_job(gui_clip,tmp_path/'unused',JobSettings(),lambda:True,lambda *args:None,
                backend_factory=lambda settings:calls.append(True))
    assert calls==[] and not (tmp_path/'unused').exists()


def test_candidate_worker_closes_backend_even_when_cancelled(gui_clip):
    closed=[]; stop=[False]
    def detect(frame):stop[0]=True;return np.asarray([[20,20,200,200]])
    backend=NS(detect=detect,close=lambda:closed.append(True))
    with pytest.raises(KeyboardInterrupt):
        inspect_candidates(gui_clip,JobSettings(),lambda:stop[0],lambda s:backend)
    assert closed==[True]


@pytest.mark.parametrize('args', [{'stage':'bad'}, {'target_index':-1}, {'target_index':True}])
def test_job_settings_reject_invalid_values(args):
    with pytest.raises(ValueError):JobSettings(**args)


def pump(root,predicate,timeout=5):
    deadline=time.monotonic()+timeout
    while not predicate():
        root.update()
        if time.monotonic()>deadline:raise AssertionError('GUI worker timed out')
        time.sleep(.01)
    root.update()


def test_gui_drop_load_preview_seek_and_invalid_replacement(gui_clip):
    from tkinterdnd2 import TkinterDnD
    from app.gui import PrototypeApp
    root=TkinterDnD.Tk();root.withdraw()
    app=PrototypeApp(root)
    try:
        app.drop(NS(data=root.tk.call('list',str(gui_clip))))
        pump(root,lambda:not app.busy)
        assert app.source==gui_clip.resolve() and app.capture is not None
        assert str(app.start_button['state'])=='normal'
        app.seek_var.set(2);app.seek_end()
        assert app.position==2
        app.toggle_play();assert app.playing
        app.toggle_play();assert not app.playing
        app.drop(NS(data=root.tk.call('list',str(gui_clip.with_suffix('.txt')))))
        pump(root,lambda:not app.busy)
        assert app.source is None and str(app.start_button['state'])=='disabled'
        assert '실패' in app.status_text.get()
    finally:app.stop_video();root.destroy()


def test_gui_cancels_active_job_before_destroy(monkeypatch):
    from tkinterdnd2 import TkinterDnD
    from app.gui import PrototypeApp
    root=TkinterDnD.Tk();root.withdraw()
    app=PrototypeApp(root)
    exited=threading.Event()
    def slow_operation():
        while not app.cancel_event.is_set():time.sleep(.005)
        exited.set();raise KeyboardInterrupt
    app.launch_worker('completed',slow_operation)
    app.close()
    deadline=time.monotonic()+5
    while not exited.is_set():
        root.update();time.sleep(.01)
        assert time.monotonic()<deadline
    app.worker.join(1)
    # poll owns destruction, after the native model's thread has exited.
    while app.busy:
        try:root.update()
        except tk.TclError:break
        time.sleep(.02)
    assert not app.worker.is_alive()


