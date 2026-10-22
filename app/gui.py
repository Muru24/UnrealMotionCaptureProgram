"""Small local desktop prototype around the existing M1/M2 processors."""

from pathlib import Path
from dataclasses import replace
import json
import logging
import os
from queue import Empty, Queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2
from PIL import Image, ImageTk
from tkinterdnd2 import COPY, DND_FILES, REFUSE_DROP, TkinterDnD

from app.gui_jobs import (JobSettings, ROOT, inspect_candidates, new_output,
                          parse_drop, read_source, run_job)


class PrototypeApp:
    def __init__(self, root):
        self.root = root
        self.source = self.result_dir = None
        self.saved_preview_path=None
        self.candidate_dir=None
        self.leg_result_path=None;self.part_result_path=None;self.reconnection_path=None;self.leg_phase=None
        self.worker = None
        self.events = Queue()
        self.cancel_event = threading.Event()
        self.closing = False
        self.busy = False
        self.capture = None
        self.playing = False
        self.play_timer = None
        self.frame = self.photo = None
        self.video_count = 0
        self.video_fps = 30.
        self.position = 0
        self.target_frame = None
        self.run_output = None
        self.was_playing = False
        self.mode = tk.StringVar(value='SAM 3D + SAM 2 마스크 (시험)')
        self.single = tk.BooleanVar(value=True)
        self.fast_candidates = tk.BooleanVar(value=False)
        self.target = tk.StringVar(value='자동 선택')
        self.file_text = tk.StringVar(value='MP4 영상을 이곳에 드래그하세요')
        self.info_text = tk.StringVar(value='또는 영상 선택 버튼으로 파일을 열 수 있습니다.')
        self.status_text = tk.StringVar(value='준비 · 영상을 넣어 주세요')
        self.detail_text = tk.StringVar(value='결과는 새 폴더에 자동 저장됩니다.')
        self.result_kind = tk.StringVar(value='3D 미리보기')
        self.time_text = tk.StringVar(value='00:00 / 00:00')
        self.seek_var = tk.DoubleVar(value=0)
        root.title('Video to Motion · MVP5 v0.8.0')
        root.geometry('1400x850')
        root.minsize(1200, 700)
        root.configure(bg='#101722')
        root.protocol('WM_DELETE_WINDOW', self.close)
        self._build()
        self.settings_changed()
        for widget in (root, self.drop_area, self.file_label, self.canvas):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind('<<Drop>>', self.drop)
        root.after(80, self.poll)

    def _build(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('.', font=('맑은 고딕',10), background='#101722', foreground='#e6edf6')
        style.configure('TFrame', background='#101722')
        style.configure('Panel.TFrame', background='#1b2637')
        style.configure('Treeview',background='#1b2637',fieldbackground='#1b2637',
                        foreground='#e6edf6',bordercolor='#3d5879',lightcolor='#1b2637',
                        darkcolor='#1b2637',rowheight=27)
        style.map('Treeview',background=[('selected','#3478eb')],
                  foreground=[('selected','#ffffff')])
        style.configure('Treeview.Heading',background='#293b52',foreground='#eef5ff',
                        bordercolor='#3d5879',lightcolor='#293b52',darkcolor='#293b52')
        style.map('Treeview.Heading',background=[('active','#3b5474')])
        style.configure('TNotebook',background='#101722',bordercolor='#3d5879')
        style.configure('TNotebook.Tab',background='#1b2637',foreground='#a7bdd6',
                        lightcolor='#1b2637',padding=(10,7))
        style.map('TNotebook.Tab',background=[('selected','#293b52'),('active','#213147')],
                  foreground=[('selected','#eef5ff'),('active','#eef5ff')])
        style.configure('Vertical.TScrollbar',background='#293b52',troughcolor='#101722',
                        arrowcolor='#a7bdd6',bordercolor='#101722',lightcolor='#293b52',darkcolor='#293b52')
        style.map('Vertical.TScrollbar',background=[('active','#3b5474'),('pressed','#3478eb')])
        style.configure('TPanedwindow',background='#101722')
        style.configure('Sash',background='#293b52',lightcolor='#293b52',
                        darkcolor='#293b52',sashthickness=6)
        style.configure('TButton', background='#293b52', foreground='#eef5ff', padding=(12,7), borderwidth=0)
        style.map('TButton', background=[('active','#3b5474'),('disabled','#202a38')],
                  foreground=[('disabled','#718096')])
        style.configure('Accent.TButton', background='#3478eb', padding=(20,9))
        style.map('Accent.TButton', background=[('active','#4b90ff'),('disabled','#253a58')])
        style.configure('TCheckbutton', background='#101722', foreground='#d5e3f6')
        style.map('TCheckbutton', background=[('active','#101722')])
        style.configure('TCombobox', fieldbackground='#213147', background='#293b52', foreground='#edf3ff', padding=5)
        style.map('TCombobox', fieldbackground=[('readonly','#213147')], foreground=[('readonly','#edf3ff')])
        style.configure('Horizontal.TProgressbar', background='#4b90ff', troughcolor='#263247', borderwidth=0)
        self.root.option_add('*TCombobox*Listbox.background','#213147')
        self.root.option_add('*TCombobox*Listbox.foreground','#edf3ff')
        main=ttk.Frame(self.root, padding=20)
        main.pack(fill='both', expand=True)
        main.columnconfigure(0,weight=1)
        main.rowconfigure(3,weight=1)
        header=ttk.Frame(main)
        header.grid(row=0,column=0,sticky='ew',pady=(0,14))
        ttk.Label(header,text='VIDEO TO UNREAL',font=('Segoe UI',20,'bold')).pack(side='left')
        ttk.Label(header,text='MVP4  0.7.8',foreground='#8cabc9').pack(side='right')
        self.drop_area=tk.Frame(main,bg='#1b2637',highlightbackground='#3d5879',highlightthickness=1)
        self.drop_area.grid(row=1,column=0,sticky='ew',pady=(0,12))
        self.file_label=tk.Label(self.drop_area,textvariable=self.file_text,bg='#1b2637',fg='#f0f5fc',
                                  font=('맑은 고딕',13,'bold'),anchor='w',padx=16,pady=12)
        self.file_label.pack(side='top',fill='x')
        bottom=tk.Frame(self.drop_area,bg='#1b2637')
        bottom.pack(fill='x',padx=16,pady=(0,12))
        tk.Label(bottom,textvariable=self.info_text,bg='#1b2637',fg='#a7bdd6',anchor='w').pack(side='left')
        self.choose_button=ttk.Button(bottom,text='영상 선택',command=self.choose)
        self.choose_button.pack(side='right')
        options=ttk.Frame(main)
        options.grid(row=2,column=0,sticky='ew',pady=(0,12))
        self.mode_box=ttk.Combobox(options,textvariable=self.mode,values=('3D 모션 + 원본 뼈대','SAM 3D Body (GPU 시험)','SAM 3D + SAM 2 마스크 (시험)','2D 뼈대만 (M1)'),
                                   state='readonly',width=24)
        self.mode_box.pack(side='left')
        self.mode_box.bind('<<ComboboxSelected>>',self.settings_changed)
        self.single_check=ttk.Checkbutton(options,text='영상에 한 명만 등장',variable=self.single,
                                           command=self.settings_changed)
        self.single_check.pack(side='left',padx=14)
        self.candidate_button=ttk.Button(options,text='대상 확인',command=self.find_candidates,state='disabled')
        self.candidate_button.pack(side='left',padx=(0,8))
        self.target_box=ttk.Combobox(options,textvariable=self.target,values=('자동 선택',),
                                     state='readonly',width=13)
        self.target_box.pack(side='left')
        self.fast_check=ttk.Checkbutton(options,text='빠른 후보 추론(시험)',variable=self.fast_candidates,
            command=lambda:self.detail_text.set('빠른 후보: 처리시간을 줄이지만 팔·손목 추정이 달라질 수 있습니다.' if self.fast_candidates.get() else '기존 품질의 후보 추론을 사용합니다.'))
        self.fast_check.pack(side='left',padx=8)
        self.start_button=ttk.Button(options,text='출력',style='Accent.TButton',command=self.start,state='disabled')
        self.start_button.pack(side='right')
        self.preview_split=ttk.Panedwindow(main,orient='horizontal')
        self.preview_split.grid(row=3,column=0,sticky='nsew')
        viewer=ttk.Frame(self.preview_split)
        self.preview_split.add(viewer,weight=3)
        viewer.columnconfigure(0,weight=1)
        viewer.rowconfigure(1,weight=1)
        bar=ttk.Frame(viewer)
        bar.grid(row=0,column=0,sticky='ew',pady=(0,8))
        ttk.Label(bar,text='미리보기',font=('맑은 고딕',11,'bold')).pack(side='left')
        self.kind_box=ttk.Combobox(bar,textvariable=self.result_kind,values=('원본 영상',),
                                   state='disabled',width=18)
        self.kind_box.pack(side='right')
        self.kind_box.bind('<<ComboboxSelected>>',self.change_view)
        self.open_sam_button=ttk.Button(bar,text='SAM 결과 열기',command=self.open_sam_result)
        self.open_sam_button.pack(side='right',padx=4)
        paired=ttk.Panedwindow(viewer,orient='horizontal')
        paired.grid(row=1,column=0,sticky='nsew')
        self.canvas=tk.Canvas(paired,bg='#080d14',highlightthickness=0)
        paired.add(self.canvas,weight=1)
        from app.skeleton_panel import SkeletonPanel
        self.skeleton_panel=SkeletonPanel(paired,self.generate_motion)
        self.animation_button=ttk.Button(self.skeleton_panel,text='Blender 애니메이션 저장',command=self.generate_animation)
        self.animation_button.grid(row=3,column=0,sticky='ew',pady=(6,0))
        self.engine_button=ttk.Button(self.skeleton_panel,text='Unreal · Unity FBX 저장',command=lambda:self.generate_animation(engine=True))
        self.engine_button.grid(row=4,column=0,sticky='ew',pady=(6,0))
        paired.add(self.skeleton_panel,weight=1)
        self.canvas.bind('<Configure>',lambda e:self.render_frame())
        self.canvas.create_text(450,160,text='영상을 넣고 출력 버튼을 누르세요',fill='#7690ab',font=('맑은 고딕',16),tags='placeholder')
        controls=ttk.Frame(viewer)
        controls.grid(row=2,column=0,sticky='ew',pady=(8,0))
        controls.columnconfigure(1,weight=1)
        self.play_button=ttk.Button(controls,text='재생',command=self.toggle_play,state='disabled',width=8)
        self.play_button.grid(row=0,column=0,padx=(0,10))
        self.seek=ttk.Scale(controls,from_=0,to=1,variable=self.seek_var,state='disabled')
        self.seek.grid(row=0,column=1,sticky='ew')
        self.seek.bind('<ButtonPress-1>',self.seek_begin)
        self.seek.bind('<ButtonRelease-1>',self.seek_end)
        self.seek.bind('<KeyRelease>',self.seek_end)
        ttk.Label(controls,textvariable=self.time_text,width=16,anchor='e').grid(row=0,column=2,padx=(8,0))
        status=ttk.Frame(main)
        status.grid(row=4,column=0,sticky='ew',pady=(14,0))
        self.status_label=ttk.Label(status,textvariable=self.status_text,font=('맑은 고딕',11,'bold'))
        self.status_label.pack(anchor='w')
        self.progress=ttk.Progressbar(status,mode='determinate',maximum=100)
        self.progress.pack(fill='x',pady=(7,5))
        ttk.Label(status,textvariable=self.detail_text,foreground='#9bb0c9',wraplength=880).pack(anchor='w')
        footer=ttk.Frame(main)
        footer.grid(row=5,column=0,sticky='ew',pady=(12,0))
        ttk.Label(footer,text='SAM 후처리 자동 실행 · 주황색은 추정 · 원시 결과 보존 · 결과는 무음',
                  foreground='#8a9fb8',font=('맑은 고딕',9)).pack(side='left')
        self.cancel_button=ttk.Button(footer,text='취소',command=self.cancel,state='disabled')
        self.cancel_button.pack(side='right')
        self.folder_button=ttk.Button(footer,text='결과 폴더 열기',command=self.open_folder,state='disabled')
        self.folder_button.pack(side='right',padx=8)
        from app.result_browser import ResultBrowser
        self.result_panel=ResultBrowser(self.preview_split,ROOT/'outputs',self.preview_saved_result,self.before_result_delete,lambda:self.busy)
        self.preview_split.add(self.result_panel.window,weight=1)

    def preview_saved_result(self,folder,path):
        if self.busy:return
        self.stop_video()
        self.source=None;self.run_output=None;self.candidate_dir=None;self.leg_result_path=None;self.part_result_path=None;self.reconnection_path=None
        self.result_dir=Path(folder);self.saved_preview_path=Path(path)
        self.file_text.set(self.display_name(self.result_dir.name))
        self.info_text.set(str(self.saved_preview_path.relative_to(self.result_dir)))
        self.result_kind.set('저장 영상');self.kind_box.configure(values=('저장 영상',),state='readonly')
        self.folder_button.configure(state='normal');self.set_busy(False)
        self.status_text.set('저장된 결과 미리보기')
        self.open_video(self.saved_preview_path)

    def before_result_delete(self,folder):
        if self.busy:raise ValueError('작업 중에는 결과를 삭제할 수 없습니다.')
        folder=Path(folder).resolve()
        if any(p and Path(p).resolve().is_relative_to(folder) for p in (self.result_dir,self.saved_preview_path,self.run_output,self.source)):
            self.stop_video();self.skeleton_panel.clear();self.frame=None;self.render_frame()
            if self.source and Path(self.source).resolve().is_relative_to(folder):self.source=None
            self.result_dir=None;self.saved_preview_path=None;self.run_output=None
            self.candidate_dir=None;self.leg_result_path=None;self.part_result_path=None;self.reconnection_path=None
            self.kind_box.configure(values=('원본 영상',),state='disabled');self.result_kind.set('원본 영상')
            self.folder_button.configure(state='disabled');self.set_busy(False)
            self.status_text.set('결과 미리보기를 닫았습니다.')






    def open_sam_result(self):
        if self.busy:return
        path=filedialog.askopenfilename(parent=self.root,title='기존 SAM 결과의 sam3d.json 선택',filetypes=[('SAM 결과','sam3d.json')])
        if not path:return
        folder=Path(path).parent
        post_options={'candidate_inference_type':'body'} if self.fast_candidates.get() else {}
        def operation():
            from app.completion_job import read
            from app.knee_job import load_context
            from app.automatic_postprocess import process_sam_result
            source=Path(read(folder/'sam-request.json')['source']);raw,source_hash,_=load_context(folder,source)
            post=process_sam_result(folder,source,self.cancel_event.is_set,
                lambda done,total:self.events.put(('progress',(done,total))),lambda text:self.events.put(('legphase',text)),**post_options)
            from app.motion_job import add_motion_result
            post.update(add_motion_result(folder,source,post,self.cancel_event.is_set))
            return folder,source,raw['video'],post,raw.get('selection')
        self.launch_worker('samopened',operation)

    def settings(self):
        stage=('sam3d' if self.mode.get().startswith('SAM') else
               'pose3d' if self.mode.get().startswith('3D') else 'pose2d')
        selected=self.target.get()
        index=None if selected=='자동 선택' else int(selected.split()[-1])
        return JobSettings(stage,self.single.get(),index,None,
                           tracking_method='sam2' if 'SAM 2' in self.mode.get() else 'pose',
                           target_frame=getattr(self,'target_frame',None) if stage=='sam3d' and 'SAM 2' in self.mode.get() else None)

    def show_automatic_status(self,result):
        auto=result['automatic_postprocess']
        if auto['status']=='partial':
            self.status_text.set('기본 결과 생성 · 자동 후처리 일부 실패')
            self.detail_text.set('원시/완료된 후보 결과는 보존됩니다. '+ ' / '.join(auto['errors'].values()))
        else:
            self.status_text.set('자동 처리 완료 · 재관측 연결 결과를 확인하세요')
            self.detail_text.set('후보·관절 검사 → 팔·다리 선택 재추정 완료 · 주황색은 교체 추정 · 원시 결과 보존 · 정확도 미검증')
            if result.get('joint_review_file'):
                self.detail_text.set('재관측 연결 비교: 왼쪽 부위 추정 / 오른쪽 검사 후 연결. 모델 추정이며 정답 보장은 아닙니다. 관절 검사는 교체 전 진단입니다. · 원시 결과 보존')


    def settings_changed(self,event=None):
        self.target_frame=None
        self.target.set('자동 선택')
        self.target_box.configure(values=('자동 선택',))
        self.single_check.configure(state='normal' if self.mode.get().startswith('3D') else 'disabled')
        if self.source:
            self.status_text.set('설정 변경 · 필요하면 대상 확인 후 출력하세요')
        if not self.mode.get().startswith('3D'):
            self.detail_text.set('2D는 M1 비교용 경로입니다. 상업적 활용의 가중치 조건 검토는 별도입니다.')
        if self.mode.get().startswith('SAM'):
            self.single_check.configure(state='disabled')
            self.detail_text.set('SAM 출력 → 관절 검사 → 필요한 팔·다리 재추정 자동 실행 · 원시 결과 보존')
            if 'SAM 2' in self.mode.get():
                self.detail_text.set('SAM 2 마스크로 대상 추적 → SAM3D 자세 추정 · 시험 기능 · 가림/장면 전환 시 다른 대상 연결 가능')

    def choose(self):
        if self.busy:return
        name=filedialog.askopenfilename(parent=self.root,title='MP4 영상 선택',filetypes=[('MP4 영상','*.mp4')])
        if name:self.load_source(Path(name))

    def drop(self,event):
        if self.busy or self.closing:return REFUSE_DROP
        try:
            path=parse_drop(self.root.tk,event.data)
        except (ValueError,tk.TclError) as exc:
            self.status_text.set(str(exc));return REFUSE_DROP
        self.load_source(path)
        return COPY

    def launch_worker(self,kind,operation):
        if self.busy:return
        self.busy=True
        self.cancel_event.clear()
        self.set_busy(True)
        def work():
            try:
                result=operation()
                if kind!='completed' and self.cancel_event.is_set():
                    raise KeyboardInterrupt
                self.events.put((kind,result))
            except KeyboardInterrupt:
                self.events.put(('cancelled',None))
            except Exception as exc:
                logging.exception('Prototype worker failed: %s',kind)
                self.events.put(('error',str(exc)))
            finally:
                self.events.put(('finished',None))
        self.worker=threading.Thread(target=work,name='motion-worker',daemon=False)
        self.worker.start()

    def set_busy(self,value):
        self.skeleton_panel.convert_button.configure(state='disabled' if value else 'normal')
        self.animation_button.configure(state='disabled' if value else 'normal')
        self.engine_button.configure(state='disabled' if value else 'normal')
        self.result_panel.set_busy(value)
        self.open_sam_button.configure(state='disabled' if value else 'normal')
        for widget in (self.choose_button,self.candidate_button,self.start_button):
            widget.configure(state='disabled' if value else 'normal' if self.source or widget is self.choose_button else 'disabled')
        self.mode_box.configure(state='disabled' if value else 'readonly')
        self.fast_check.configure(state='disabled' if value else 'normal')
        self.target_box.configure(state='disabled' if value else 'readonly')
        self.single_check.configure(state='disabled' if value or self.settings().stage!='pose3d' else 'normal')
        self.cancel_button.configure(state='normal' if value else 'disabled')

    def load_source(self,path):
        if self.busy:return
        self.skeleton_panel.clear()
        self.target_frame=None
        self.saved_preview_path=None
        self.stop_video()
        self.frame=None
        self.render_frame()
        self.time_text.set('00:00 / 00:00')
        # Clear the previous input before validating the replacement, so an invalid
        # drop can never leave the Output button pointing at a stale source.
        self.source=None
        self.candidate_dir=None
        self.leg_result_path=None
        self.part_result_path=None;self.reconnection_path=None
        self.result_dir=None
        self.run_output=None
        self.folder_button.configure(state='disabled')
        self.kind_box.configure(state='disabled',values=('원본 영상',))
        self.result_kind.set('원본 영상')
        self.target.set('자동 선택')
        self.target_box.configure(values=('자동 선택',))
        self.file_text.set(self.display_name(path.name))
        self.info_text.set('영상 확인 중…')
        self.status_text.set('영상 정보를 읽는 중')
        self.progress.configure(value=0)
        self.launch_worker('loaded',lambda:(path,*read_source(path)))

    def find_candidates(self):
        if not self.source or self.busy:return
        self.pause()
        source,settings=self.source,self.settings()
        if settings.tracking_method=='sam2':
            settings=replace(settings,target_frame=self.position if self.position>0 else None)
        self.status_text.set('대상 후보 확인 중 · 시작 위치가 비어 있으면 등장 프레임을 찾습니다…')
        self.launch_worker('candidates',lambda:inspect_candidates(source,settings,self.cancel_event.is_set,include_frame_index=True))

    def start(self):
        if not self.source or self.busy:return
        post_options={'candidate_inference_type':'body'} if self.fast_candidates.get() else {}
        self.stop_video()
        self.candidate_dir=None
        self.leg_result_path=None
        self.part_result_path=None;self.reconnection_path=None
        source,settings=self.source,self.settings()
        output=new_output(source,settings.stage)
        self.run_output=output
        self.result_dir=None
        self.folder_button.configure(state='disabled')
        self.kind_box.configure(state='disabled')
        self.status_text.set('출력 중 · 로컬 모델을 준비하는 중…')
        self.detail_text.set('완료되면 이 창에서 결과를 재생할 수 있습니다.')
        self.progress.configure(value=0)
        def operation():
            progress=lambda done,total:self.events.put(('progress',(done,total)))
            report=run_job(source,output,settings,self.cancel_event.is_set,progress)
            if settings.stage=='sam3d':
                from app.automatic_postprocess import process_sam_result
                report.update(process_sam_result(output,source,self.cancel_event.is_set,progress,
                              lambda text:self.events.put(('legphase',text)),**post_options))
                from app.motion_job import add_motion_result
                self.events.put(('legphase','표준 스켈레톤 변환'))
                report.update(add_motion_result(output,source,report,self.cancel_event.is_set))
            return output,settings,report
        self.launch_worker('completed',operation)

    def cancel(self):
        if self.busy:
            self.cancel_event.set()
            self.status_text.set('취소 중 · 현재 프레임 처리가 끝나면 중단합니다')
            self.cancel_button.configure(state='disabled')

    def poll(self):
        try:
            while True:
                kind,data=self.events.get_nowait()
                if self.closing:
                    if kind=='finished':self.busy=False
                    continue
                if kind=='loaded':
                    path,metadata,frame=data
                    self.source=path.resolve()
                    self.file_text.set(self.display_name(path.name))
                    self.info_text.set(f'{metadata.width} × {metadata.height}  ·  {metadata.fps:.2f} fps  ·  약 {metadata.duration_seconds_estimate:.1f}초')
                    self.status_text.set('준비 · 출력 버튼을 누르세요')
                    self.detail_text.set('다중 인물 영상은 1인 옵션을 해제하고 대상 확인을 먼저 해 주세요.')
                    self.frame=frame;self.render_frame()
                    self.open_video(self.source)
                elif kind=='candidates':
                    frame,count,index=data
                    self.target_frame=index if count and self.settings().tracking_method=='sam2' else None
                    self.position=index;self.seek_var.set(index)
                    if self.capture is not None:self.capture.set(cv2.CAP_PROP_POS_FRAMES,index+1)
                    self.time_text.set(f'{self.clock(index/self.video_fps)} / {self.clock(self.video_count/self.video_fps)}')
                    self.frame=frame;self.render_frame()
                    self.target_box.configure(values=('자동 선택',)+tuple(f'대상 {i}' for i in range(count)))
                    self.target.set('대상 0' if count==1 else '자동 선택')
                    self.status_text.set(f'{index}프레임 · 후보 {count}명 · 번호를 선택한 뒤 출력하세요' if count else f'{index}프레임에 후보 없음 · 인물이 보이는 위치에서 다시 확인하세요')
                elif kind=='samopened':
                    folder,source,video,post,selection_kind=data;self.source=source;self.result_dir=folder
                    self.run_output=None
                    self.candidate_dir=Path(post['candidate_selection_directory']) if post.get('candidate_selection_directory') else None
                    self.leg_result_path=Path(post['leg_result_directory'])/'leg-overlay.mp4' if post.get('leg_result_directory') else None
                    self.part_result_path=Path(post['part_result_directory'])/'part-overlay.mp4' if post.get('part_result_directory') else None
                    self.mode.set('SAM 3D + SAM 2 마스크 (시험)' if selection_kind=='sam2_video_mask' else 'SAM 3D Body (GPU 시험)')
                    self.file_text.set(self.display_name(source.name));self.info_text.set(f'{video["width"]} × {video["height"]} · {video["fps"]:.2f} fps')
                    values=('원본 뼈대','원본 영상') if self.candidate_dir is None else ('후보 선택 비교','원본 뼈대','원본 영상')
                    if self.candidate_dir and (self.candidate_dir/'fullbody-reference.mp4').is_file():values=('전신 기준축',)+values
                    if self.candidate_dir and (self.candidate_dir/'joint-review.mp4').is_file():values=('관절 검사',)+values
                    if self.leg_result_path is not None:values=('다리 재추정 비교',)+values
                    if self.part_result_path is not None:values=('부위 재추정 비교',)+values
                    self.reconnection_path=Path(post['reconnection_directory'])/'reconnection-overlay.mp4' if post.get('reconnection_directory') else None
                    if self.reconnection_path is not None:values=('재관측 연결 비교',)+values
                    self.kind_box.configure(state='readonly',values=values)
                    self.result_kind.set(values[0]);self.change_view();self.folder_button.configure(state='normal')
                    self.show_automatic_status(post)
                    if post.get('motion_error'):self.skeleton_panel.clear('변환 실패: '+post['motion_error'])
                elif kind=='motionready':
                    self.load_standard_motion(Path(data));self.skeleton_panel.set_frame(self.position)
                    self.status_text.set('표준 스켈레톤 준비 완료 · 영상과 동기화')
                elif kind=='engineexportready':
                    output=Path(data)
                    corrected=output.parent/'corrected-motion.json'
                    if corrected.is_file():self.load_standard_motion(corrected);self.skeleton_panel.set_frame(self.position)
                    self.status_text.set('엔진용 FBX 저장 완료 · '+str(output))
                    messagebox.showinfo('엔진용 FBX 저장 완료','Motion_Unreal.fbx / Motion_Unity.fbx\n30fps · 기준 스켈레톤 애니메이션\n가림 구간 정보: export.json\n'+str(output))
                elif kind=='animationready':
                    corrected=Path(data).parent/'corrected-motion.json'
                    if corrected.is_file():self.load_standard_motion(corrected);self.skeleton_panel.set_frame(self.position)
                    self.status_text.set('Blender 애니메이션 저장 완료 · '+str(data))
                    messagebox.showinfo('애니메이션 저장 완료','Blender에서 열고 Space로 재생하세요.\n'+str(data))
                elif kind=='legphase':
                    self.leg_phase=data;self.status_text.set(data)
                elif kind=='progress':
                    if self.cancel_event.is_set():continue
                    done,total=data
                    self.progress.configure(value=min(99.,done/max(total,1)*100))
                    self.status_text.set(f'{self.leg_phase} · {done} / {total}' if self.leg_phase else f'추적·SAM 처리 중 · {done} / 약 {total} 단계' if self.settings().stage=='sam3d' else f'출력 중 · {done} / 약 {total} 프레임')
                elif kind=='completed':
                    output,settings,report=data
                    self.result_dir=output
                    warnings=report.get('warnings',[])
                    self.progress.configure(value=100)
                    count=report['frames_processed']; tracked=report['frames_with_target']
                    self.status_text.set('출력 생성됨 · 대상 유지가 부족하여 확인이 필요합니다' if tracked<count*.5 else
                                         '출력 완료 · 확인할 경고가 있습니다' if warnings else '출력 완료')
                    labels={'target_reselection_required':'대상 분실·모호성으로 재선택 필요',
                            'target_starts_after_frame_zero':'대상 등장 전 구간은 비어 있는 상태로 보존',
                            'target_unavailable_in_some_frames':'일부 프레임의 대상 추정 누락',
                            'unreliable_joints_in_some_frames':'일부 관절 신뢰도 낮음',
                            'multiple_people_detected':'여러 대상 후보 검출',
                            'duplicate_candidates_suppressed':'중복 후보 통합 구간 확인 필요',
                            'local_crop_recovery_used':'인물 영역 재검출 구간 확인 필요',
                            'decoded_frame_count_differs_from_metadata':'영상 표기·실제 프레임 수 차이'}
                    warning_text=' / '.join(labels.get(w,w) for w in warnings)
                    self.detail_text.set(f'총 {count}프레임 / 대상 유지 {tracked}프레임 · 추적률은 관절 정확도가 아닙니다.\n'+
                                         (warning_text+'\n' if warning_text else '')+f'저장: {output.name}')
                    if settings.stage=='sam3d':
                        metrics=report.get('tracking_metrics')
                        continuity=('' if not metrics else
                            f'최대 끊김 {metrics["max_gap_seconds"]:.2f}초 · 박스 점프 {len(metrics["box_jump_events"])} · 몸 중심 점프 {len(metrics["body_jump_events"])} · 대상 변경 검토 {len(metrics["identity_review_events"])}개(확정 아님)\n')
                        self.detail_text.set(f'SAM {count}프레임 / 대상 추적 {tracked}프레임 · 관절 정확도 미검증\n'+
                                             continuity+
                                             (warning_text+'\n' if warnings else '')+
                                             f'후보 선택·다리 재추정 자동 실행 · 저장: {output.name}')
                    self.folder_button.configure(state='normal')
                    values=('3D 미리보기','원본 뼈대','원본 영상') if settings.stage=='pose3d' else ('원본 뼈대','원본 영상')
                    if (output/'mask-tracking.mp4').is_file():values+=('대상 마스크',)
                    if report.get('candidate_selection_directory'):
                        self.candidate_dir=Path(report['candidate_selection_directory']);values=('후보 선택 비교',)+values
                        if (self.candidate_dir/'fullbody-reference.mp4').is_file():values=('전신 기준축',)+values
                        if (self.candidate_dir/'joint-review.mp4').is_file():values=('관절 검사',)+values
                        self.status_text.set('출력·후보 선택 완료 · 후보 선택 비교를 표시합니다')
                        self.detail_text.set(f'왼쪽 원시 / 오른쪽 후보 선택 · 저장: {self.candidate_dir.name}')
                    if report.get('leg_result_directory'):
                        self.leg_result_path=Path(report['leg_result_directory'])/'leg-overlay.mp4';values=('다리 재추정 비교',)+values
                    if report.get('part_result_directory'):
                        self.part_result_path=Path(report['part_result_directory'])/'part-overlay.mp4';values=('부위 재추정 비교',)+values
                    if report.get('reconnection_directory'):
                        self.reconnection_path=Path(report['reconnection_directory'])/'reconnection-overlay.mp4';values=('재관측 연결 비교',)+values
                    if report.get('automatic_postprocess'):self.show_automatic_status(report)
                    self.kind_box.configure(state='readonly',values=values)
                    self.result_kind.set(values[0])
                    self.change_view()
                    self.play()
                    if report.get('motion_error'):self.skeleton_panel.clear('변환 실패: '+report['motion_error'])
                elif kind in ('error','cancelled'):
                    self.status_text.set('취소됨 · 저장된 부분 결과가 있으면 cancelled로 표시됩니다' if kind=='cancelled' else '처리 실패 · 입력과 설정을 확인해 주세요')
                    self.detail_text.set('새로 출력하면 기존 결과를 덮어쓰지 않습니다.' if kind=='cancelled' else data)
                    if self.source is None:self.info_text.set('유효한 로컬 MP4 파일 하나를 다시 넣어 주세요.')
                    if self.run_output and self.run_output.is_dir():
                        self.result_dir=self.run_output
                        self.folder_button.configure(state='normal')
                elif kind=='finished':
                    self.busy=False
                    self.leg_phase=None
                    self.set_busy(False)
                    self.result_panel.refresh()
        except Empty:
            pass
        if self.closing and not self.busy and not (self.worker and self.worker.is_alive()):
            self.stop_video();self.root.destroy();return
        self.root.after(80,self.poll)

    def open_video(self,path):
        self.stop_video()
        cap=cv2.VideoCapture()
        if not cap.open(str(path),cv2.CAP_FFMPEG,[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,5000,
                                                 cv2.CAP_PROP_READ_TIMEOUT_MSEC,5000]):
            cap.release();self.status_text.set('미리보기 영상을 열 수 없습니다');return
        self.capture=cap
        self.video_fps=max(1.,cap.get(cv2.CAP_PROP_FPS))
        self.video_count=max(1,int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        self.preview_path=Path(path)
        motion=self.result_dir/'motion/motion.json' if self.result_dir else None
        if motion is not None and motion.is_file():self.load_standard_motion(motion)
        else:self.skeleton_panel.clear('SAM 결과의 변환 버튼으로 기존 결과도 변환할 수 있습니다')
        self.seek.configure(to=self.video_count-1,state='normal')
        self.play_button.configure(state='normal')
        self.read_video_frame()

    def load_standard_motion(self,path):
        try:
            if path.name=='motion.json':
                from app.animation_job import latest_corrected_motion
                path=latest_corrected_motion(path)
            self.skeleton_panel.load(path)
            original=self.source is not None and getattr(self,'preview_path',None)==self.source
            if len(self.skeleton_panel.points)!=self.video_count and not original:
                self.skeleton_panel.clear('표본/구간 영상은 원본 타임라인과 달라 동기 표시하지 않습니다')
        except (OSError,ValueError,KeyError) as exc:self.skeleton_panel.clear(f'스켈레톤 읽기 실패: {exc}')

    def change_view(self,event=None):
        if self.result_kind.get()=='저장 영상' and self.saved_preview_path:
            self.open_video(self.saved_preview_path);return
        kind=self.result_kind.get()
        if kind=='재관측 연결 비교' and self.reconnection_path:
            self.open_video(self.reconnection_path);return
        if kind=='부위 재추정 비교' and self.part_result_path:
            self.open_video(self.part_result_path);return
        if kind=='관절 검사' and self.candidate_dir:
            self.open_video(self.candidate_dir/'joint-review.mp4');return
        if kind=='전신 기준축' and self.candidate_dir:
            self.open_video(self.candidate_dir/'fullbody-reference.mp4');return
        if kind=='다리 재추정 비교' and self.leg_result_path:
            self.open_video(self.leg_result_path);return
        if kind=='후보 선택 비교' and self.candidate_dir:
            self.open_video(self.candidate_dir/'candidate-overlay.mp4');return
        if kind=='대상 마스크' and self.result_dir:
            path=self.result_dir/'mask-tracking.mp4'
            if path.is_file():self.open_video(path)
            return
        path=self.source if kind=='원본 영상' else self.result_dir/('preview3d.mp4' if kind.startswith('3D') else 'overlay.mp4') if self.result_dir else None
        if path and path.is_file():self.open_video(path)


    def render_frame(self):
        if hasattr(self,'skeleton_panel'):self.skeleton_panel.set_frame(self.position)
        w,h=max(1,self.canvas.winfo_width()),max(1,self.canvas.winfo_height())
        if self.frame is None:
            self.canvas.delete('all')
            self.canvas.create_text(w//2,h//2,text='영상을 넣고 출력 버튼을 누르세요',fill='#7690ab',
                                     font=('맑은 고딕',16),tags='placeholder')
            return
        image=Image.fromarray(cv2.cvtColor(self.frame,cv2.COLOR_BGR2RGB))
        image.thumbnail((w,h),Image.Resampling.LANCZOS)
        self.photo=ImageTk.PhotoImage(image,master=self.root)
        self.canvas.delete('all')
        self.canvas.create_image(w//2,h//2,image=self.photo,anchor='center')

    def generate_animation(self,engine=False):
        if self.busy or not self.result_dir:return
        folder=Path(self.result_dir)
        if not (folder/'sam3d.json').is_file():
            self.status_text.set('완료된 SAM3D 결과를 선택해 주세요');return
        self.pause();self.status_text.set('접지·SLERP 떨림 보정 후 Blender 애니메이션 생성 중 · CPU 처리')
        def operation():
            from app.motion_job import ensure_motion
            from app.animation_job import export_animation
            source=Path(json.loads((folder/'sam-request.json').read_text(encoding='utf-8'))['source'])
            report=folder/'automatic-report.json'
            post=json.loads(report.read_text(encoding='utf-8')) if report.is_file() else {}
            motion,_=ensure_motion(folder,source,post,self.cancel_event.is_set)
            blend=export_animation(motion,self.cancel_event.is_set)
            if engine:
                from app.engine_export_job import export_engine_fbx
                return str(export_engine_fbx(blend,self.cancel_event.is_set))
            return str(blend)
        self.launch_worker('engineexportready' if engine else 'animationready',operation)

    def generate_motion(self):
        if self.busy or not self.result_dir:return
        folder=Path(self.result_dir)
        if not (folder/'sam3d.json').is_file():
            self.skeleton_panel.clear('완료된 SAM3D 결과를 선택해 주세요');return
        self.pause();self.status_text.set('기존 추출에서 표준 스켈레톤 변환 중 · 모델 재추론 없음')
        def operation():
            from app.motion_job import ensure_motion
            source=Path(json.loads((folder/'sam-request.json').read_text(encoding='utf-8'))['source'])
            report=folder/'automatic-report.json'
            post=json.loads(report.read_text(encoding='utf-8')) if report.is_file() else {}
            path,_=ensure_motion(folder,source,post,self.cancel_event.is_set)
            return str(path)
        self.launch_worker('motionready',operation)

    @staticmethod
    def display_name(name):
        return name if len(name)<=50 else name[:28]+'…'+name[-18:]

    @staticmethod
    def clock(seconds):
        seconds=max(0,int(seconds));return f'{seconds//60:02d}:{seconds%60:02d}'

    def read_video_frame(self):
        if self.capture is None:return False
        ok,frame=self.capture.read()
        if not ok:return False
        self.position=max(0,int(self.capture.get(cv2.CAP_PROP_POS_FRAMES))-1)
        self.frame=frame;self.render_frame()
        self.seek_var.set(self.position)
        self.time_text.set(f'{self.clock(self.position/self.video_fps)} / {self.clock(self.video_count/self.video_fps)}')
        return True

    def play(self):
        if self.capture is None:return
        if self.position>=self.video_count-1:
            self.capture.set(cv2.CAP_PROP_POS_FRAMES,0)
        if self.playing:return
        self.playing=True;self.play_button.configure(text='일시정지')
        self.tick()

    def tick(self):
        self.play_timer=None
        if not self.playing:return
        start=time.perf_counter()
        if not self.read_video_frame():self.pause();return
        delay=max(1,round(1000/self.video_fps-(time.perf_counter()-start)*1000))
        self.play_timer=self.root.after(delay,self.tick)

    def pause(self):
        self.playing=False
        if self.play_timer is not None:
            self.root.after_cancel(self.play_timer);self.play_timer=None
        self.play_button.configure(text='재생')

    def toggle_play(self):
        if self.playing:self.pause()
        else:self.play()

    def seek_begin(self,event=None):
        self.was_playing=self.playing;self.pause()

    def seek_end(self,event=None):
        if self.capture is None:return
        self.capture.set(cv2.CAP_PROP_POS_FRAMES,max(0,min(self.video_count-1,round(self.seek_var.get()))))
        self.read_video_frame()
        if self.was_playing:self.play()
        self.was_playing=False

    def stop_video(self):
        self.pause()
        if self.capture is not None:self.capture.release();self.capture=None
        self.play_button.configure(state='disabled')
        self.seek.configure(state='disabled')

    def open_folder(self):
        if self.result_dir and self.result_dir.is_dir():
            try:os.startfile(str(self.result_dir))
            except OSError:self.status_text.set('결과 폴더를 열 수 없습니다')

    def close(self):
        self.closing=True
        self.stop_video()
        if self.busy:
            self.cancel_event.set();self.set_busy(True)
            self.status_text.set('처리를 취소하고 종료하는 중…')
        else:self.root.destroy()


def main():
    root=TkinterDnD.Tk()
    PrototypeApp(root)
    root.mainloop()


if __name__=='__main__':
    main()
