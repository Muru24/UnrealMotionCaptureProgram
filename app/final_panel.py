"""Final model-only review and user-selected file delivery."""
import os,time
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog
import cv2
from PIL import Image,ImageTk
from app.gui_jobs import ROOT
from app.final_results import list_final_results,export_final


class FinalResultsPanel(ttk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent);self.app=app;self.rows=[];self.capture=None;self.current=None;self.frame=0;self.photo=None;self.timer=None;self.playing=False;self.exported=None;self.setting_time=False
        self.columnconfigure(0,weight=1);self.columnconfigure(1,minsize=316);self.rowconfigure(0,weight=1)
        view=tk.Frame(self,bg='#111a24',highlightbackground='#263545',highlightthickness=1,padx=16,pady=16);view.grid(row=0,column=0,sticky='nsew',padx=(0,16));view.columnconfigure(0,weight=1);view.rowconfigure(1,weight=1)
        ttk.Label(view,text='최종 애니메이션',font=('맑은 고딕',12,'bold'),style='Panel.TLabel').grid(row=0,column=0,sticky='w',pady=(0,12))
        self.canvas=tk.Canvas(view,bg='#0a141f',highlightthickness=0);self.canvas.grid(row=1,column=0,sticky='nsew');self.canvas.bind('<Configure>',lambda e:self.draw())
        controls=ttk.Frame(view,style='Panel.TFrame');controls.grid(row=2,column=0,sticky='ew',pady=(12,0));controls.columnconfigure(1,weight=1)
        self.play_button=ttk.Button(controls,text='▶ 재생',command=self.toggle,state='disabled');self.play_button.grid(row=0,column=0,padx=(0,8))
        self.time=tk.DoubleVar(value=0);self.seek=ttk.Scale(controls,from_=0,to=1,variable=self.time,command=self.scrub,state='disabled');self.seek.grid(row=0,column=1,sticky='ew')
        self.clock=ttk.Label(controls,text='00:00 / 00:00',style='Panel.TLabel');self.clock.grid(row=0,column=2,padx=(8,0))
        right=ttk.Frame(self);right.grid(row=0,column=1,sticky='nsew');right.columnconfigure(0,weight=1);right.rowconfigure(0,weight=1)
        results=tk.Frame(right,bg='#111a24',highlightbackground='#263545',highlightthickness=1,padx=15,pady=15);results.grid(row=0,column=0,sticky='nsew');results.columnconfigure(0,weight=1);results.rowconfigure(2,weight=1)
        ttk.Label(results,text='최종 결과 목록',font=('맑은 고딕',11,'bold'),style='Panel.TLabel').grid(row=0,column=0,sticky='w')
        ttk.Label(results,text='추출별 최신 완료본 · 편집본 우선',style='Panel.TLabel').grid(row=1,column=0,sticky='w',pady=(5,10))
        self.tree=ttk.Treeview(results,columns=('name','kind'),show='headings',height=5,selectmode='browse');self.tree.heading('name',text='애니메이션');self.tree.heading('kind',text='상태');self.tree.column('name',width=180);self.tree.column('kind',width=80,stretch=False);self.tree.grid(row=2,column=0,sticky='nsew')
        scroll=ttk.Scrollbar(results,command=self.tree.yview);scroll.grid(row=2,column=1,sticky='ns');self.tree.configure(yscrollcommand=scroll.set);self.tree.bind('<<TreeviewSelect>>',lambda e:self.select())
        card=tk.Frame(right,bg='#111a24',highlightbackground='#263545',highlightthickness=1,padx=15,pady=15);card.grid(row=1,column=0,sticky='ew',pady=(14,0))
        ttk.Label(card,text='내보내기',font=('맑은 고딕',11,'bold'),style='Panel.TLabel').pack(anchor='w')
        self.info=tk.StringVar(value='완료된 결과를 선택하세요.');ttk.Label(card,textvariable=self.info,style='Panel.TLabel',wraplength=270).pack(anchor='w',pady=(8,12))
        self.formats={key:tk.BooleanVar(value=True) for key in ('fbx','blend','mp4')}
        for key,text in [('fbx','FBX · 모델 애니메이션'),('blend','Blender · 편집 가능한 프로젝트'),('mp4','MP4 · 최종 미리보기')]:ttk.Checkbutton(card,text=text,variable=self.formats[key]).pack(anchor='w',pady=2)
        self.export_button=ttk.Button(card,text='↓  내보내기',style='Accent.TButton',command=self.export,state='disabled');self.export_button.pack(fill='x',pady=(14,0))
        self.open_button=ttk.Button(card,text='내보낸 폴더 열기',command=self.open_export)
        self.message=tk.StringVar(value='중간 추적·비교·진단 파일은 표시하지 않습니다.')
        ttk.Label(self,textvariable=self.message,wraplength=1050).grid(row=1,column=0,columnspan=2,sticky='w',pady=(12,0));self.image=None;self.draw()

    def refresh(self):
        prior=self.current.preview if self.current else None;self.rows=list_final_results(ROOT/'outputs');self.tree.delete(*self.tree.get_children())
        for i,row in enumerate(self.rows):self.tree.insert('','end',iid=str(i),values=(row.label,'편집 완료' if row.edited else '추출 완료'))
        selected=next((i for i,row in enumerate(self.rows) if row.preview==prior),0)
        if self.rows:self.tree.selection_set(str(selected));self.select()
        else:self.clear();self.message.set('최종 결과가 없습니다. 1번 전체 추출 또는 4번 편집 결과 출력을 완료하세요.')

    def select(self):
        keys=self.tree.selection()
        if not keys:return
        row=self.rows[int(keys[0])]
        if self.current and self.current.preview==row.preview and self.capture is not None:return
        self.pause();self.clear();self.current=row;cap=cv2.VideoCapture(str(row.preview))
        if not cap.isOpened():cap.release();self.message.set('최종 미리보기를 열 수 없습니다.');return
        self.capture=cap;self.fps=max(1.,cap.get(cv2.CAP_PROP_FPS));self.count=max(1,int(cap.get(cv2.CAP_PROP_FRAME_COUNT)));self.seek.configure(to=self.count-1,state='normal');self.play_button.configure(state='normal')
        from app.model_preview import metadata
        info=metadata(row.preview) or {};model_name=info.get('model_name','Unreal Manny')
        self.info.set(f'{row.label}\n{row.frames:,} 프레임 · {row.fps:.2f} FPS\n{row.frames/row.fps:.2f}초 · {model_name}\n'+('편집 적용 완료' if row.edited else '추출·보정 완료'))
        if info.get('model_quality_warnings'):self.info.set(self.info.get()+'\n확인 필요: '+' / '.join(info['model_quality_warnings']))
        self.read_frame(0);self.set_busy(self.app.busy)
        if not self.app.busy:
            self.app.status_text.set('최종 결과 준비됨 · '+row.label)
            self.app.studio.update_summary()

    def read_frame(self,index):
        if self.capture is None:return
        index=max(0,min(self.count-1,index));self.capture.set(cv2.CAP_PROP_POS_FRAMES,index);ok,image=self.capture.read()
        if not ok:self.pause();return
        self.image=image;self.frame=index;self.setting_time=True;self.time.set(index);self.setting_time=False
        self.clock.configure(text=f'{index/self.fps:05.2f} / {self.count/self.fps:05.2f}s');self.draw()

    def draw(self):
        self.canvas.delete('all');w=max(1,self.canvas.winfo_width());h=max(1,self.canvas.winfo_height())
        if self.image is None:self.canvas.create_text(w/2,h/2,text='완료된 모델 애니메이션만 표시됩니다',fill='#8fa4b8',width=max(1,w-30));return
        image=Image.fromarray(cv2.cvtColor(self.image,cv2.COLOR_BGR2RGB));image.thumbnail((w,h));self.photo=ImageTk.PhotoImage(image,master=self.app.root);self.canvas.create_image(w/2,h/2,image=self.photo,anchor='center')

    def scrub(self,value):
        if not self.setting_time and self.capture is not None:self.pause();self.read_frame(round(float(value)))

    def toggle(self):
        if self.playing:self.pause();return
        if self.capture is None:return
        self.playing=True;self.start_frame=self.frame if self.frame<self.count-1 else 0;self.start=time.monotonic();self.play_button.configure(text='Ⅱ 일시정지');self.tick()

    def tick(self):
        if not self.playing:return
        index=self.start_frame+int((time.monotonic()-self.start)*self.fps)
        if index>=self.count:self.pause();return
        self.read_frame(index);self.timer=self.after(max(10,round(1000/self.fps)),self.tick)

    def pause(self):
        self.playing=False
        if self.timer:self.after_cancel(self.timer);self.timer=None
        self.play_button.configure(text='▶ 재생')

    def clear(self):
        self.pause()
        if self.capture is not None:self.capture.release();self.capture=None
        self.current=None;self.image=None;self.frame=0;self.info.set('완료된 결과를 선택하세요.');self.clock.configure(text='00:00 / 00:00')
        self.exported=None;self.open_button.pack_forget()
        self.play_button.configure(state='disabled');self.seek.configure(state='disabled');self.export_button.configure(state='disabled');self.draw()

    def close_if_folder(self,folder):
        if self.current and self.current.preview.is_relative_to(folder):self.clear()

    def set_busy(self,busy):
        self.export_button.configure(state='normal' if self.current and self.capture is not None and not busy else 'disabled')

    def export(self):
        if self.app.busy or self.current is None:return
        formats=[k for k,v in self.formats.items() if v.get()]
        if not formats:self.message.set('내보낼 형식을 하나 이상 선택하세요.');return
        destination=filedialog.askdirectory(parent=self,title='최종 결과를 내보낼 폴더',mustexist=True)
        if not destination:return
        row=self.current;self.pause();self.app.leg_phase='최종 결과 내보내기';self.message.set('최종 파일 준비·복사 중…')
        self.app.progress.configure(value=0)
        self.app.launch_worker('finalexported',lambda:export_final(row,destination,formats,self.app.cancel_event.is_set,lambda a,b:self.app.events.put(('progress',(a,b)))))

    def exported_to(self,path):
        self.exported=Path(path);self.message.set('내보내기 완료: '+str(path));self.open_button.pack(fill='x',pady=(7,0))

    def open_export(self):
        if self.exported and self.exported.is_dir():os.startfile(str(self.exported))
