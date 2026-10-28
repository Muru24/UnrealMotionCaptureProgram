"""Native model/bone editor with live software-skinned preview and keyframes."""
import json,time,math
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
import numpy as np,cv2
from PIL import Image,ImageTk
from app.editable_animation import EditableAnimation,MODEL,euler_angles,quaternion,rotation,matrix_quaternion


class AnimationEditor(ttk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent);self.app=app;self.clip=None;self.preview=None;self.frame=0;self.selected=MODEL
        self.photo=None;self.updating=False;self.draft=False;self.playing=False;self.timer=None;self.render_timer=None
        self.yaw=-25.;self.pitch=12.;self.zoom=1.;self.center=np.array([0.,0.,.9]);self.drag=None;self.gizmos=[];self.projected=None
        self.modal=None;self.mouse=None;self.project_path=None;self.last_output=None;self.live_preview=True;self.auto_load=True
        self.columnconfigure(0,weight=1);self.rowconfigure(1,weight=1)
        bar=ttk.Frame(self);bar.grid(row=0,column=0,sticky='ew',pady=(0,10));bar.columnconfigure(0,weight=1)
        self.choice=tk.StringVar();self.box=ttk.Combobox(bar,textvariable=self.choice,state='readonly');self.box.grid(row=0,column=0,sticky='ew')
        self.box.bind('<<ComboboxSelected>>',lambda event:self.load_selected())
        ttk.Label(bar,text='모델 선택 시 자동 불러오기').grid(row=0,column=1,padx=(8,0))
        area=ttk.Panedwindow(self,orient='horizontal');area.grid(row=1,column=0,sticky='nsew')
        left=ttk.Frame(area,width=170);area.add(left,weight=0);left.rowconfigure(1,weight=1);left.columnconfigure(0,weight=1)
        ttk.Label(left,text='모델 / 본 목록').grid(row=0,column=0,sticky='w',pady=(0,5))
        self.tree=ttk.Treeview(left,show='tree',selectmode='browse',height=14);self.tree.grid(row=1,column=0,sticky='nsew')
        scroll=ttk.Scrollbar(left,command=self.tree.yview);scroll.grid(row=1,column=1,sticky='ns');self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind('<<TreeviewSelect>>',self.select_bone)
        middle=ttk.Frame(area);middle.columnconfigure(0,weight=1);middle.rowconfigure(1,weight=1);area.add(middle,weight=1)
        controls=ttk.Frame(middle);controls.grid(row=0,column=0,sticky='ew',pady=(0,5))
        self.mode=tk.StringVar(value='이동')
        for mode in ('이동','회전'):ttk.Radiobutton(controls,text=mode,variable=self.mode,value=mode,command=self.render).pack(side='left',padx=5)
        ttk.Button(controls,text='화면 맞춤',command=self.fit).pack(side='left',padx=5)
        self.show_bones=tk.BooleanVar(value=True);ttk.Checkbutton(controls,text='본 표시',variable=self.show_bones,command=self.render).pack(side='left')
        self.orientation=tk.StringVar(value='전역');ttk.Combobox(controls,textvariable=self.orientation,values=('전역','로컬'),state='readonly',width=5).pack(side='left',padx=3)
        options=ttk.Frame(middle);options.grid(row=1,column=0,sticky='ew')
        self.auto_key=tk.BooleanVar(value=True);ttk.Checkbutton(options,text='자동 키',variable=self.auto_key).pack(side='left',padx=3)
        self.ik=tk.BooleanVar(value=True);ttk.Checkbutton(options,text='손·발 연결 IK',variable=self.ik,command=self.change_ik).pack(side='left',padx=3)
        self.proportional=tk.BooleanVar(value=True);ttk.Checkbutton(options,text='연결 회전 비례 (O)',variable=self.proportional).pack(side='left',padx=3)
        self.radius=tk.IntVar(value=2);ttk.Spinbox(options,from_=1,to=5,width=2,textvariable=self.radius).pack(side='left')
        self.sync=tk.BooleanVar(value=True);ttk.Checkbutton(options,text='3번 실시간',variable=self.sync).pack(side='left',padx=3)
        self.canvas=tk.Canvas(middle,bg='#080e15',highlightthickness=0,takefocus=True);self.canvas.grid(row=1,column=0,sticky='nsew')
        middle.rowconfigure(1,weight=0);middle.rowconfigure(2,weight=1);self.canvas.grid_configure(row=2)
        self.canvas.bind('<Configure>',lambda e:self.render());self.canvas.bind('<Button-1>',self.pick)
        self.canvas.bind('<B1-Motion>',self.manipulate);self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<ButtonPress-3>',self.right_click)
        self.canvas.bind('<B3-Motion>',self.orbit);self.canvas.bind('<MouseWheel>',self.wheel)
        self.canvas.bind('<Motion>',self.motion);self.canvas.bind('<ButtonPress-2>',self.middle_click);self.canvas.bind('<B2-Motion>',self.orbit)
        for widget in (self.canvas,self.tree):widget.bind('<KeyPress>',self.shortcut)
        ttk.Label(middle,text='G 이동 / R 회전 → XYZ·숫자 → Enter 확정 · Esc 취소 · I 키 · 중클릭 시점 · Shift+중클릭 팬',wraplength=600).grid(row=3,column=0,sticky='w',pady=5)
        inspector=ttk.Frame(area,width=285,padding=(10,0,0,0));area.add(inspector,weight=0)
        self.bone_label=ttk.Label(inspector,text='선택: 모델 전체',wraplength=270);self.bone_label.pack(anchor='w',pady=(0,8))
        ttk.Label(inspector,text='원본에 더할 로컬 오프셋',foreground='#9daec3').pack(anchor='w')
        self.values=[tk.StringVar(value='0') for _ in range(6)];self.entries=[]
        for group,title in enumerate(('위치 (cm)','회전 XYZ (°)')):
            ttk.Label(inspector,text=title).pack(anchor='w',pady=(12,5));row=ttk.Frame(inspector);row.pack(fill='x')
            for axis,color in enumerate(('#ee6b71','#79d28b','#63a7ff')):
                col=ttk.Frame(row);col.pack(side='left',expand=True,fill='x',padx=2)
                ttk.Label(col,text='XYZ'[axis],foreground=color).pack()
                entry=ttk.Spinbox(col,from_=-3600,to=3600,increment=.5,textvariable=self.values[group*3+axis],width=7)
                entry.pack(fill='x');self.entries.append(entry)
                entry.bind('<Return>',lambda e:self.commit_pending());entry.bind('<FocusOut>',lambda e:self.commit_pending())
                entry.bind('<Control-s>',lambda e:self.save_shortcut())
                self.values[group*3+axis].trace_add('write',self.changed)
        self.buttons=[]
        actions=ttk.Frame(inspector);actions.pack(fill='x',pady=(8,0))
        self.edit_menu=ttk.Menubutton(actions,text='편집 동작 ⋯');self.edit_menu.pack(fill='x',pady=3)
        menu=tk.Menu(self.edit_menu,tearoff=False,bg='#111a23',fg='#edf3fb',activebackground='#153f68',activeforeground='white')
        self.edit_menu.configure(menu=menu)
        for text,command in [('현재 키 저장  I',self.key),('전체 구간 적용',lambda:self.key(True)),
                             ('현재 키 삭제',self.delete_key),('입력값 0으로',self.zero),
                             ('실행 취소',lambda:self.history(False)),('다시 실행',lambda:self.history(True)),
                             ('다른 이름으로 저장',self.save),('편집 파일 열기',self.open)]:menu.add_command(label=text,command=command)
        self.save_button=ttk.Button(actions,text='편집 저장',command=self.save_shortcut);self.save_button.pack(fill='x',pady=3)
        self.export_button=ttk.Button(actions,text='편집 결과 출력',command=self.export,style='Accent.TButton');self.export_button.pack(fill='x',pady=3)
        self.buttons=[self.save_button,self.export_button,self.edit_menu]
        ttk.Label(inspector,text='손·발 이동: IK로 팔꿈치·무릎 연결.\n부모 회전: 자식 본과 피부 함께 반영.\n자동 키: 조작 확정·프레임 이동 시 저장.\n3번에도 실시간 반영 / 파일은 출력으로 저장.',foreground='#9daec3',wraplength=270).pack(anchor='w',pady=(8,0))
        timeline=ttk.Frame(self);timeline.grid(row=2,column=0,sticky='ew',pady=(10,0));timeline.columnconfigure(2,weight=1)
        self.play_button=ttk.Button(timeline,text='▶ 재생',command=self.toggle);self.play_button.grid(row=0,column=0)
        self.frame_var=tk.IntVar(value=0);self.frame_box=ttk.Spinbox(timeline,from_=0,to=0,textvariable=self.frame_var,width=7,command=self.seek_entry)
        self.frame_box.grid(row=0,column=1,padx=6);self.frame_box.bind('<Return>',lambda e:self.seek_entry())
        self.time=tk.DoubleVar(value=0);self.slider=ttk.Scale(timeline,from_=0,to=1,variable=self.time,command=self.seek);self.slider.grid(row=0,column=2,sticky='ew')
        self.clock=ttk.Label(timeline,text='0 / 0 프레임',width=22);self.clock.grid(row=0,column=3,padx=6)
        self.key_canvas=tk.Canvas(timeline,height=24,bg='#111a23',highlightthickness=0);self.key_canvas.grid(row=1,column=2,sticky='ew');self.key_canvas.bind('<Configure>',lambda e:self.draw_keys());self.key_canvas.bind('<Button-1>',self.pick_key)
        self.message=tk.StringVar(value='모델을 선택하면 자동으로 열립니다. 원본은 보존됩니다.')
        ttk.Label(self,textvariable=self.message,wraplength=1100).grid(row=3,column=0,sticky='w',pady=6)
        self.paths=[];self.set_busy(False)

    def refresh(self):
        from app.model_preview import discover_models,model_asset
        from app.animation_edit_job import edit_source
        found=discover_models(self.app.result_panel.root);paths=[]
        for _,item in found:
            try:edit_source(item.path);paths.append(item.path)
            except FileNotFoundError:pass
        self.paths=paths;self.box.configure(values=[str(p.relative_to(self.app.result_panel.root)) for p in paths])
        current=model_asset(self.app.result_dir,self.app.requested_preview_path)
        index=paths.index(current.path) if current and current.path in paths else 0
        if paths and (not self.choice.get() or self.preview is None):self.box.current(index)
        self.set_busy(self.app.busy)
        if paths and self.clip is None and not self.app.busy and self.auto_load:self.after_idle(self.load_selected)

    def guard(self,operation):
        try:return operation()
        except (ValueError,OSError,KeyError,json.JSONDecodeError,tk.TclError) as exc:self.message.set(str(exc))

    def load_selected(self):
        if self.app.busy or not 0<=self.box.current()<len(self.paths):return
        if self.preview==self.paths[self.box.current()] and self.clip is not None:return
        if self.clip and (self.clip.dirty or self.draft) and not messagebox.askyesno('편집 전환','저장하지 않은 변경을 버리고 다른 모델을 불러올까요?',parent=self):return
        self.pause();preview=self.paths[self.box.current()]
        from app.animation_edit_job import prepare_scene
        self.message.set('편집용 모델·본·애니메이션 준비 중…');self.app.leg_phase='편집용 모델 준비'
        self.app.launch_worker('editorloaded',lambda:(prepare_scene(preview,self.app.cancel_event.is_set),preview))

    def loaded(self,cache,preview):
        self.clip=EditableAnimation(cache);self.preview=Path(preview).resolve();self.frame=0;self.selected=MODEL;self.draft=False
        self.project_path=None;self.modal=None;self.last_output=None
        self.app.stop_video();self.app.saved_preview_path=self.preview;self.app.requested_preview_path=self.preview;self.app.position=0
        self.app.result_dir=self.app.result_panel.root/self.preview.resolve().relative_to(self.app.result_panel.root.resolve()).parts[0]
        self.tree.delete(*self.tree.get_children());self.tree.insert('','end',iid=MODEL,text='모델 전체',open=True)
        for i,n in enumerate(self.clip.names):
            parent=self.clip.parents[i];self.tree.insert(MODEL if parent<0 else self.clip.names[parent],'end',iid=n,text=n,open=len(self.clip.names)<30)
        self.tree.selection_set(MODEL);self.slider.configure(to=max(1,self.clip.count-1));self.frame_box.configure(to=self.clip.count-1)
        self.fit();self.set_frame(0);self.set_busy(self.app.busy)
        self.message.set(f'{self.clip.count}프레임 · {len(self.clip.names)}본 · 프레임 번호는 0부터 시작 · 변형 확정 시 키 반영 · Ctrl+S로 편집 파일 저장')

    def set_busy(self,busy):
        ready=self.clip is not None and not busy
        self.box.configure(state='disabled' if busy else 'readonly')
        for widget in self.entries+self.buttons+[self.play_button,self.frame_box,self.slider]:widget.configure(state='normal' if ready else 'disabled')

    def select_bone(self,event=None):
        if not self.clip or not self.tree.selection():return
        if not self.commit_pending():return
        self.pause();self.selected=self.tree.selection()[0];self.fields();self.render()

    def fields(self):
        if not self.clip:return
        self.updating=True
        exact=self.clip.edits.get(self.selected,{}).get(str(self.frame));loc,q=self.clip.offset(self.selected,self.frame)
        angles=exact['rotation'] if exact else euler_angles(q)
        for v,n in zip(self.values,[* (loc*100),*angles]):v.set(f'{n:.3f}')
        self.bone_label.configure(text='선택: '+('모델 전체' if self.selected==MODEL else self.selected))
        self.ik.set(self.clip.limb_ik)
        self.draft=False;self.updating=False;self.draw_keys()

    def changed(self,*args):
        if self.updating or not self.clip:return
        self.pause();self.draft=True
        if self.render_timer:self.after_cancel(self.render_timer)
        self.render_timer=self.after(16,self.render)

    def inputs(self):
        v=[float(s.get()) for s in self.values];loc=np.array(v[:3])/100;rot=v[3:]
        self.clip.validate_value(self.selected,self.frame,loc,rot);return loc,rot

    def draft_values(self):
        if not self.draft:return None
        loc,rot=self.inputs()
        return self.clip.proportional_offsets(self.selected,self.frame,loc,rot,int(self.radius.get()) if self.proportional.get() else 0)

    def commit_pending(self):
        if not self.clip or not self.draft or not self.auto_key.get() or self.modal:return True
        if self.app.busy:return False
        try:self.inputs()
        except (ValueError,tk.TclError):self.message.set('유효한 위치·회전 숫자를 입력하세요.');return False
        self.key();return not self.draft

    def finish_edit(self):
        if self.modal:self.confirm_transform()
        return self.commit_pending()

    def change_ik(self):
        if self.clip and not self.app.busy:
            self.clip.snapshot();self.clip.limb_ik=self.ik.get();self.render()

    def save_shortcut(self):
        if not self.commit_pending():return 'break'
        if self.project_path:self.guard(lambda:self.clip.save(self.project_path));self.message.set('편집 파일 저장됨')
        else:self.save()
        return 'break'

    def key(self,whole=False):
        if not self.clip or self.app.busy:return
        def perform():
            loc,rot=self.inputs();values=self.clip.proportional_offsets(self.selected,self.frame,loc,rot,int(self.radius.get()) if self.proportional.get() else 0)
            self.clip.set_keys({n:(p,rot if n==self.selected and len(values)==1 else euler_angles(q)) for n,(p,q) in values.items()},self.frame,whole)
            self.fields();self.render();self.message.set('전체 구간 오프셋 적용됨 · 편집 파일을 저장하세요.' if whole else f'{self.frame}프레임 키 반영됨 · 3번 실시간 미리보기와 동기화')
        self.guard(perform)

    def delete_key(self):
        if self.clip and not self.app.busy:self.clip.delete_key(self.selected,self.frame);self.fields();self.render()

    def zero(self):
        if self.clip:
            for v in self.values:v.set('0')

    def history(self,redo):
        if self.modal:self.cancel_transform()
        if self.clip and not self.app.busy:self.clip.undo(redo);self.fields();self.render()

    def save(self):
        if not self.clip or self.app.busy:return
        if not self.finish_edit():return
        if self.draft:self.message.set('입력한 값을 먼저 현재 프레임 키로 저장하세요.');return
        path=filedialog.asksaveasfilename(parent=self,title='애니메이션 편집 파일 저장',defaultextension='.json',initialdir=self.preview.parent,initialfile='animation-edits.json',filetypes=[('애니메이션 편집','*.json')])
        if path:
            def perform():self.clip.save(path);self.project_path=Path(path);self.message.set('편집 파일 저장: '+path)
            self.guard(perform)

    def open(self):
        if not self.clip or self.app.busy:return
        path=filedialog.askopenfilename(parent=self,title='애니메이션 편집 파일 열기',filetypes=[('애니메이션 편집','*.json')])
        if path:
            def perform():self.clip.load(path);self.project_path=Path(path);self.fields();self.render();self.message.set('편집 파일 불러옴')
            self.guard(perform)

    def export(self):
        if not self.clip or self.app.busy:return
        if not self.finish_edit():return
        if self.draft:self.message.set('입력한 값을 먼저 현재 프레임 키로 저장하세요.');return
        self.pause();packet=self.clip.packet();preview=self.preview;cache=self.clip.cache
        from app.animation_edit_job import export_edit
        self.app.leg_phase='편집 결과 저장·렌더링';self.app.progress.configure(value=0)
        self.app.launch_worker('editorapplied',lambda:export_edit(preview,cache,packet,self.app.cancel_event.is_set,lambda a,b:self.app.events.put(('progress',(a,b)))))

    def set_frame(self,frame):
        if not self.clip:return
        if not self.commit_pending():return
        self.updating=True;self.frame=int(np.clip(frame,0,self.clip.count-1));self.frame_var.set(self.frame);self.time.set(self.frame);self.updating=False
        self.clock.configure(text=f'{self.frame} / {self.clip.count-1} · {self.frame/self.clip.fps:.2f}s');self.fields();self.render()

    def seek(self,value):
        if self.clip and not self.updating:self.pause();self.set_frame(round(float(value)))

    def seek_entry(self):
        if self.clip:self.guard(lambda:self.set_frame(int(self.frame_var.get())))

    def toggle(self):
        if self.playing:self.pause();return
        if not self.clip or self.app.busy:return
        if not self.finish_edit():return
        self.playing=True;self.play_button.configure(text='Ⅱ 일시정지');self.started=time.monotonic();self.start_frame=self.frame;self.tick()

    def tick(self):
        if not self.playing:return
        self.set_frame((self.start_frame+int((time.monotonic()-self.started)*self.clip.fps))%self.clip.count)
        self.timer=self.after(max(10,round(1000/self.clip.fps)),self.tick)

    def pause(self):
        self.playing=False
        if self.timer:self.after_cancel(self.timer);self.timer=None
        self.play_button.configure(text='▶ 재생')

    def draw_keys(self):
        self.key_canvas.delete('all')
        if not self.clip:return
        w=max(1,self.key_canvas.winfo_width())
        for f in self.clip.edits.get(self.selected,{}):
            x=int(f)/max(1,self.clip.count-1)*(w-8)+4;self.key_canvas.create_polygon(x,3,x+5,10,x,17,x-5,10,fill='#f5ba55',outline='')
        x=self.frame/max(1,self.clip.count-1)*(w-8)+4;self.key_canvas.create_line(x,0,x,23,fill='#36b4ff',width=2)

    def pick_key(self,e):
        if self.clip:self.pause();self.set_frame(round((e.x-4)/max(1,self.key_canvas.winfo_width()-8)*(self.clip.count-1)))

    def fit(self):
        if not self.clip:return
        v=self.clip.vertices(self.clip.transforms(self.frame));self.center=(v.min(0)+v.max(0))/2;self.zoom=1.;self.size=max(.5,float(np.max(v.max(0)-v.min(0))));self.render()

    def view_matrix(self):
        y,p=np.radians([self.yaw,self.pitch]);c,s=np.cos(y),np.sin(y)
        return np.array([[c,-s,0],[s*np.sin(p),c*np.sin(p),-np.cos(p)],[s*np.cos(p),c*np.cos(p),np.sin(p)]])

    def render_mesh(self,frame,w,h,draft=None):
        poses=self.clip.transforms(frame,draft);v=self.clip.vertices(poses);view=self.view_matrix();scale=min(w,h)/max(.5,getattr(self,'size',1.8))*self.zoom*.78
        def project(q):
            a=(np.asarray(q)-self.center)@view.T;return np.column_stack((a[:,0]*scale+w/2,a[:,1]*scale+h/2,a[:,2]))
        points=project(v);tri=self.clip.data['triangles'];screen=points[tri];order=np.argsort(screen[:,:,2].mean(1))[::-1]
        image=np.full((h,w,3),(21,14,8),np.uint8)
        for value in np.arange(-5,5.1,.5):
            a=project([[value,-5,0],[value,5,0],[-5,value,0],[5,value,0]])[:,:2].astype(int)
            cv2.line(image,tuple(a[0]),tuple(a[1]),(42,36,28),1);cv2.line(image,tuple(a[2]),tuple(a[3]),(42,36,28),1)
        normals=np.cross(v[tri[:,1]]-v[tri[:,0]],v[tri[:,2]]-v[tri[:,0]]);normals/=np.maximum(1e-9,np.linalg.norm(normals,axis=1))[:,None]
        light=np.array([.3,-.6,.75]);shade=.35+.65*np.abs(normals@light)
        for i in order:
            polygon=np.clip(screen[i,:,:2],-20000,20000).astype(np.int32)
            if polygon[:,0].max()<0 or polygon[:,0].min()>w or polygon[:,1].max()<0 or polygon[:,1].min()>h:continue
            color=tuple(int(x*shade[i]) for x in (202,183,159));cv2.fillConvexPoly(image,polygon,color,lineType=cv2.LINE_AA)
        return image,poses,project,scale

    def live_frame(self,seconds,width,height):
        if not self.clip or not self.live_preview or not self.sync.get():return None
        # Opening panel 4 alone must not replace the full-quality video with
        # the lightweight editor mesh. Live overrides begin with an edit.
        if not self.clip.edits and not self.draft:return None
        if self.app.requested_preview_path not in (self.preview,self.last_output):return None
        frame=round(seconds*self.clip.fps)
        if not 0<=frame<self.clip.count:return None
        try:draft=self.draft_values() if frame==self.frame else None
        except (ValueError,tk.TclError):draft=None
        return self.render_mesh(frame,max(64,min(640,width)),max(64,min(640,height)),draft)[0]

    def render(self):
        if self.render_timer:self.after_cancel(self.render_timer);self.render_timer=None
        w=max(1,self.canvas.winfo_width());h=max(1,self.canvas.winfo_height())
        if not self.clip:
            self.canvas.delete('all');self.canvas.create_text(w/2,h/2,text='모델 선택 → 자동 불러오기 → 본 위치·회전 조절',fill='#9daec3',width=max(1,w-20));return
        try:draft=self.draft_values()
        except (ValueError,tk.TclError):return
        self.canvas.delete('all');image,poses,project,scale=self.render_mesh(self.frame,w,h,draft);self.pixel_scale=scale;tri=self.clip.data['triangles']
        self.viewport_rgb=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
        self.photo=ImageTk.PhotoImage(Image.fromarray(self.viewport_rgb));self.canvas.create_image(0,0,anchor='nw',image=self.photo)
        self.projected=project(poses[:,:3,3]);self.gizmos=[]
        if self.show_bones.get():
            for i,parent in enumerate(self.clip.parents):
                x,y,_=self.projected[i]
                if parent>=0:self.canvas.create_line(*self.projected[parent,:2],x,y,fill='#6ba3bd',width=1)
                self.canvas.create_oval(x-2,y-2,x+2,y+2,fill='#ffd166' if self.clip.names[i]==self.selected else '#8dc3df',outline='')
        if self.selected==MODEL:center=poses[0,:3,3];axes=self.clip.data['object_matrices'][self.frame][:3,:3]
        else:
            i=self.clip.names.index(self.selected);center=poses[i,:3,3];axes=poses[i,:3,:3]
            if self.mode.get()=='이동':
                parent=self.clip.parents[i];parent_matrix=self.clip.data['object_matrices'][self.frame] if parent<0 else poses[parent]
                axes=(parent_matrix@self.clip.rest_local[i])[:3,:3]
        origin=project([center])[0,:2]
        if self.orientation.get()=='전역':axes=np.eye(3)
        self.pivot=origin
        for axis,color in enumerate(('#fa6874','#72e39a','#65aaff')):
            direction=axes[:,axis]/max(1e-9,np.linalg.norm(axes[:,axis]));end=project([center+direction*.25])[0,:2]
            self.canvas.create_line(*origin,*end,fill=color,width=3,arrow='last');self.canvas.create_text(*end,text='XYZ'[axis],fill=color,anchor='sw')
            self.gizmos.append((axis,origin.copy(),end.copy()))
        self.canvas.create_text(12,12,anchor='nw',fill='#d0deef',text=f'Frame {self.frame} · {"키 미저장" if self.draft else "편집됨" if self.clip.dirty else "저장됨"} · {len(tri)} preview faces')

    def pick(self,e):
        if not self.clip or self.app.busy:return
        self.canvas.focus_set()
        if self.modal:self.confirm_transform();return
        self.pause();point=np.array([e.x,e.y])
        for axis,a,b in self.gizmos:
            d=b-a;t=np.clip((point-a)@d/max(1,d@d),0,1)
            if np.linalg.norm(point-(a+t*d))<9 and t>.25:
                self.drag=('gizmo',axis,e.x,e.y,[v.get() for v in self.values],d/max(1,np.linalg.norm(d)));return
        if self.projected is not None:
            distances=np.linalg.norm(self.projected[:,:2]-point,axis=1);i=int(np.argmin(distances))
            if distances[i]<15:self.tree.selection_set(self.clip.names[i]);self.tree.see(self.clip.names[i])

    def manipulate(self,e):
        if not self.drag or self.drag[0]!='gizmo' or self.app.busy:return
        _,axis,x,y,start,direction=self.drag;distance=np.array([e.x-x,e.y-y])@direction
        index=axis if self.mode.get()=='이동' else axis+3
        amount=distance/max(1,self.pixel_scale)*100 if index<3 else distance*.6
        world=np.eye(3) if self.orientation.get()=='전역' else self.axis_basis()
        values=self.transformed_values(np.array(list(map(float,start))),world[:,axis],amount,self.mode.get())
        self.set_inputs(values);self.render()

    def orbit(self,e):
        if not self.drag or self.drag[0] not in ('orbit','pan'):return
        kind,x,y=self.drag
        if kind=='pan':self.center-=((e.x-x)*self.view_matrix()[0]+(e.y-y)*self.view_matrix()[1])/max(1,getattr(self,'pixel_scale',200))
        else:self.yaw+=(e.x-x)*.5;self.pitch=float(np.clip(self.pitch+(e.y-y)*.5,-89.5,89.5))
        self.drag=(kind,e.x,e.y);self.render()

    def wheel(self,e):
        if self.modal and self.proportional.get():self.radius.set(int(np.clip(self.radius.get()+(1 if e.delta>0 else -1),1,5)));self.update_transform()
        else:self.zoom=float(np.clip(self.zoom*(1.15 if e.delta>0 else 1/1.15),.2,8));self.render()

    def release(self,event):
        gizmo=self.drag and self.drag[0]=='gizmo';self.drag=None
        if gizmo:self.commit_pending()

    def right_click(self,event):
        if self.modal:self.cancel_transform();return 'break'
        self.drag=('orbit',event.x,event.y)

    def middle_click(self,event):
        self.drag=('pan' if event.state&1 else 'orbit',event.x,event.y)

    def set_inputs(self,values):
        self.updating=True
        for v,x in zip(self.values,values):v.set(f'{x:.6f}')
        self.updating=False;self.draft=True

    def axis_basis(self):
        if self.selected==MODEL:return self.clip.data['object_matrices'][self.frame][:3,:3]
        poses=self.clip.transforms(self.frame,self.draft_values());i=self.clip.names.index(self.selected)
        m=poses[i,:3,:3];return m/np.linalg.norm(m,axis=0)

    def translation_basis(self):
        if self.selected==MODEL:return self.clip.data['object_matrices'][self.frame][:3,:3]
        poses=self.clip.transforms(self.frame,ik=False);i=self.clip.names.index(self.selected);parent=self.clip.parents[i]
        return ((self.clip.data['object_matrices'][self.frame] if parent<0 else poses[parent])@self.clip.rest_local[i])[:3,:3]

    def transformed_values(self,base,axis,amount,mode):
        values=base.copy()
        if mode=='이동':values[:3]+=np.linalg.solve(self.translation_basis(),np.asarray(axis)*amount)
        else:
            angle=math.radians(amount);axis=np.asarray(axis,float);axis/=max(1e-9,np.linalg.norm(axis))
            delta=rotation(np.array([math.cos(angle/2),*(axis*math.sin(angle/2))]))
            if self.modal:world=self.modal['world_rotation']
            elif self.selected==MODEL:world=self.clip.data['object_matrices'][self.frame][:3,:3]@rotation(quaternion(base[3:]))
            else:world=self.clip.transforms(self.frame,self.clip.proportional_offsets(self.selected,self.frame,base[:3]/100,base[3:]))[self.clip.names.index(self.selected),:3,:3]
            world=world/np.linalg.norm(world,axis=0);prefix=world@rotation(quaternion(base[3:])).T
            values[3:]=euler_angles(matrix_quaternion(prefix.T@delta@world))
        return values

    def begin_transform(self,mode):
        if not self.clip or self.app.busy or not self.commit_pending():return
        try:self.inputs()
        except (ValueError,tk.TclError):self.message.set('유효한 위치·회전 숫자를 입력하세요.');return
        self.pause();base=np.array([float(v.get()) for v in self.values]);poses=self.clip.transforms(self.frame,self.draft_values())
        world=self.clip.data['object_matrices'][self.frame][:3,:3]@rotation(quaternion(base[3:])) if self.selected==MODEL else poses[self.clip.names.index(self.selected),:3,:3]
        point=np.asarray(self.mouse if self.mouse else (self.canvas.winfo_width()/2+80,self.canvas.winfo_height()/2))
        self.mode.set(mode);self.modal={'mode':mode,'axis':None,'local':self.orientation.get()=='로컬','plane':False,
            'numeric':'','base':base,'mouse':point,'current':point.copy(),'state':0,'world_rotation':world.copy(),'local_axes':self.axis_basis(),'was_draft':self.draft}
        self.canvas.focus_set();self.message.set(('G 이동 (cm)' if mode=='이동' else 'R 회전 (°)')+' · XYZ 축 / 같은 축 두 번: 로컬 · 숫자 · Enter 확정 / Esc 취소')
        if self.canvas.winfo_viewable():self.canvas.grab_set()

    def motion(self,event):
        self.mouse=(event.x,event.y)
        if self.modal:self.modal['current']=np.array([event.x,event.y]);self.modal['state']=event.state;self.update_transform()

    def update_transform(self):
        if not self.modal:return
        m=self.modal;base=m['base'];delta=m['current']-m['mouse'];view=self.view_matrix();basis=m['local_axes'] if m['local'] else np.eye(3)
        axis=basis[:,m['axis']] if m['axis'] is not None else (np.array([1.,0,0]) if m['numeric'] and m['mode']=='이동' else view[2].copy())
        try:number=float(m['numeric']) if m['numeric'] not in ('','-','.', '-.') else None
        except ValueError:return
        fine=.1 if m['state']&1 else 1.
        if m['mode']=='이동' and number is None:
            move=(view[0]*delta[0]+view[1]*delta[1])/max(1,getattr(self,'pixel_scale',200))*100*fine
            if m['axis'] is not None:move=move-axis*(move@axis) if m['plane'] else axis*(move@axis)
            amount=np.linalg.norm(move);axis=move/max(1e-9,amount)
        elif m['mode']=='이동':amount=number
        else:
            pivot=np.asarray(getattr(self,'pivot',(self.canvas.winfo_width()/2,self.canvas.winfo_height()/2)))
            a=m['mouse']-pivot;b=m['current']-pivot
            angle=math.atan2(b[1],b[0])-math.atan2(a[1],a[0]);angle=(angle+math.pi)%(2*math.pi)-math.pi
            amount=number if number is not None else math.degrees(angle)*fine
        if m['state']&4:amount=round(amount/(1 if m['mode']=='이동' else 5))*(1 if m['mode']=='이동' else 5)
        values=self.transformed_values(base,axis,amount,m['mode']);self.set_inputs(values);self.render()
        axis_text='' if m['axis'] is None else 'XYZ'[m['axis']]+(' 로컬' if m['local'] else ' 전역')
        self.message.set(f'{m["mode"]} {axis_text} {m["numeric"] or round(amount,2)} {"cm" if m["mode"]=="이동" else "°"} · Enter/좌클릭 확정 · Esc/우클릭 취소')

    def confirm_transform(self):
        if not self.modal:return
        if self.canvas.grab_current()==self.canvas:self.canvas.grab_release()
        self.modal=None;self.commit_pending();self.render()

    def cancel_transform(self):
        if not self.modal:return
        if self.canvas.grab_current()==self.canvas:self.canvas.grab_release()
        base=self.modal['base'];was_draft=self.modal['was_draft'];self.modal=None;self.set_inputs(base);self.draft=was_draft;self.render();self.message.set('변형 취소됨')

    def shortcut(self,event):
        if self.app.studio.active_stage!=3 or not self.clip or self.app.busy:return
        key=event.keysym.lower();ctrl=bool(event.state&4);shift=bool(event.state&1);alt=bool(event.state&(8|0x20000))
        if self.modal:
            if key in ('escape','return','kp_enter'):
                self.cancel_transform() if key=='escape' else self.confirm_transform();return 'break'
            if key in ('x','y','z'):
                axis='xyz'.index(key)
                if self.modal['axis']==axis:self.modal['local']=not self.modal['local']
                self.modal['axis']=axis;self.modal['plane']=shift;self.modal['state']=0;self.update_transform();return 'break'
            char=getattr(event,'char','')
            if char and char in '0123456789.-':
                if char=='-':self.modal['numeric']=self.modal['numeric'][1:] if self.modal['numeric'].startswith('-') else '-'+self.modal['numeric']
                elif char!='.' or '.' not in self.modal['numeric']:self.modal['numeric']+=char
                self.update_transform();return 'break'
            if key=='backspace':self.modal['numeric']=self.modal['numeric'][:-1];self.update_transform();return 'break'
        if ctrl and key=='z':self.history(shift)
        elif ctrl and key=='s':
            if self.modal:self.confirm_transform()
            self.save() if shift else self.save_shortcut()
        elif alt and key in ('g','r'):
            if self.modal:self.cancel_transform()
            loc,angles=self.inputs();loc=np.zeros(3) if key=='g' else loc;angles=[0,0,0] if key=='r' else angles
            self.clip.set_key(self.selected,self.frame,loc,angles);self.fields();self.render()
        elif alt and key=='i':self.delete_key()
        elif key in ('g','r'):self.begin_transform('이동' if key=='g' else '회전')
        elif key=='i':self.key()
        elif key=='o':self.proportional.set(not self.proportional.get());self.render()
        elif key=='space':self.toggle()
        elif key in ('left','right'):
            self.pause();self.set_frame((0 if key=='left' else self.clip.count-1) if shift else self.frame+(-1 if key=='left' else 1))
        elif key in ('up','down'):
            keys=sorted(map(int,self.clip.edits.get(self.selected,{})));choices=[v for v in keys if v>self.frame] if key=='up' else [v for v in keys if v<self.frame]
            if choices:self.pause();self.set_frame(min(choices) if key=='up' else max(choices))
        elif key in ('home','kp_decimal','kp_delete'):self.fit()
        elif key in ('kp_1','kp_end','kp_3','kp_next','kp_7','kp_home'):
            if key in ('kp_1','kp_end'):self.yaw=180 if ctrl else 0;self.pitch=0
            elif key in ('kp_3','kp_next'):self.yaw=-90 if ctrl else 90;self.pitch=0
            else:self.yaw=0;self.pitch=-89.5 if ctrl else 89.5
            self.render()
        else:return
        return 'break'
