"""Synchronized orthographic 3D skeleton panel; drag to orbit, wheel to zoom."""
import json
import tkinter as tk
from tkinter import ttk
import numpy as np


class SkeletonPanel(ttk.Frame):
    def __init__(self,parent,convert_command):
        super().__init__(parent);self.points=None;self.parents=[];self.names=[];self.position=0
        self.fps=None;self.empty_message='본 데이터 없음 · 1번에서 전체 추출하면 자동 생성됩니다'
        self.yaw=-25.;self.pitch=12.;self.zoom=1.;self.drag=None;self.loaded_path=None
        self.columnconfigure(0,weight=1);self.rowconfigure(1,weight=1)
        bar=ttk.Frame(self);bar.grid(row=0,column=0,sticky='ew')
        bar.columnconfigure(0,weight=1)
        ttk.Label(bar,text='본 애니메이션 · 3D',font=('맑은 고딕',10,'bold')).grid(row=0,column=0,sticky='w',pady=(0,7))
        controls=ttk.Frame(bar);controls.grid(row=1,column=0,sticky='ew')
        for i,(text,yaw) in enumerate((('정면',0),('측면',90))):
            controls.columnconfigure(i,weight=1)
            ttk.Button(controls,text=text,width=5,command=lambda a=yaw:self.view(a)).grid(row=0,column=i,sticky='ew',padx=(0,5))
        controls.columnconfigure(2,weight=1)
        self.convert_button=None
        if convert_command is not None:
            self.convert_button=ttk.Button(controls,text='변환',width=5,command=convert_command)
            self.convert_button.grid(row=0,column=2,sticky='ew')
        self.canvas=tk.Canvas(self,bg='#080d14',highlightthickness=0)
        self.canvas.grid(row=1,column=0,sticky='nsew',pady=(8,0))
        self.label=ttk.Label(self,text='드래그: 회전 · 휠: 확대 · M3 위치 미리보기',foreground='#9bb0c9',wraplength=330)
        self.label.grid(row=2,column=0,sticky='ew')
        self.canvas.bind('<Configure>',lambda e:self.render())
        self.canvas.bind('<ButtonPress-1>',lambda e:setattr(self,'drag',(e.x,e.y)))
        self.canvas.bind('<B1-Motion>',self.orbit)
        self.canvas.bind('<MouseWheel>',self.wheel)

    def clear(self,text='추출 결과를 열면 표시됩니다'):
        self.points=None;self.loaded_path=None;self.fps=None;self.empty_message=text;self.label.configure(text=text);self.render()

    def load(self,path):
        key=(str(path),path.stat().st_mtime_ns,path.stat().st_size)
        if self.loaded_path==key:return
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema')!='standard_motion_positions_v1':raise ValueError('Unknown standard motion schema.')
        try:fps=float(data['video']['fps'])
        except (KeyError,TypeError,ValueError) as exc:raise ValueError('Invalid skeleton frame rate.') from exc
        if not np.isfinite(fps) or fps<=0:raise ValueError('Invalid skeleton frame rate.')
        bones=data['skeleton']['bones'];self.names=[b['name'] for b in bones]
        self.parents=[None if b['parent'] is None else self.names.index(b['parent']) for b in bones]
        points=np.asarray([[[np.nan]*3 if p is None else p for p in row['positions']] for row in data['frames']],dtype=np.float32)
        if points.shape!=(len(data['frames']),len(bones),3):raise ValueError('Invalid skeleton preview positions.')
        self.points=points;self.loaded_path=key;self.fps=fps
        self.label.configure(text=f"입력: {data['source_kind']} · 고정 체형/제자리 · 드래그 회전/휠 확대")
        if data.get('correction'):
            text='영상·접지 결합 이동 추정 · 깊이는 모델 추정' if data.get('root_motion_kind')=='image_and_contact_estimate' else '접지 추정·SLERP 보정 · 루트 이동은 접지 제약 기반 추정'
            self.label.configure(text=text)
        self.render()

    def set_frame(self,index):self.position=index;self.render()

    def set_time(self,seconds):
        self.set_frame(round(seconds*self.fps) if self.fps else 0)

    def view(self,yaw):self.yaw=yaw;self.pitch=0.;self.render()

    def orbit(self,event):
        if self.drag:
            self.yaw+=(event.x-self.drag[0])*.6
            self.pitch=float(np.clip(self.pitch+(event.y-self.drag[1])*.4,-65,65))
        self.drag=(event.x,event.y);self.render()

    def wheel(self,event):self.zoom=float(np.clip(self.zoom*(1.1 if event.delta>0 else 1/1.1),.4,2.5));self.render()

    def render(self):
        self.canvas.delete('all');w=max(1,self.canvas.winfo_width());h=max(1,self.canvas.winfo_height())
        if self.points is None:
            self.canvas.create_text(w/2,h/2,text=self.empty_message,fill='#7690ab',width=max(1,w-32),justify='center');return
        if not 0<=self.position<len(self.points):
            self.canvas.create_text(w/2,h/2,text='이 영상과 스켈레톤의 프레임 범위가 다릅니다',fill='#e8b365');return
        q=self.points[self.position];valid=np.isfinite(q).all(axis=1)
        if not valid.any():
            self.canvas.create_text(w/2,h/2,text=f'{self.position}프레임 · 대상/관절 없음',fill='#e8b365');return
        yaw,pitch=np.radians([self.yaw,self.pitch]);c,s=np.cos(yaw),np.sin(yaw)
        def project(p):
            x,y,z=p;horizontal=x*c-y*s;depth=x*s+y*c
            return (w*.5+horizontal*min(w*.47,h*.44)*self.zoom,
                    h*.89-(z*np.cos(pitch)-depth*np.sin(pitch))*min(w*.47,h*.44)*self.zoom)
        for x in (-1,-.5,0,.5,1):
            self.canvas.create_line(*project((x,-1,0)),*project((x,1,0)),fill='#243044')
            self.canvas.create_line(*project((-1,x,0)),*project((1,x,0)),fill='#243044')
        for i,parent in enumerate(self.parents):
            if parent is None or parent==0 or not valid[i] or not valid[parent]:continue
            color='#77bfff' if self.names[i].endswith('_l') else '#eeaf6d' if self.names[i].endswith('_r') else '#70dda0'
            self.canvas.create_line(*project(q[parent]),*project(q[i]),fill=color,width=4)
        for i,p in enumerate(q):
            if valid[i]:
                x,y=project(p);self.canvas.create_oval(x-3,y-3,x+3,y+3,fill='#dceaf4',outline='')
        self.canvas.create_text(10,14,text=f'Frame {self.position} · {valid.sum()}/{len(q)} · Z up',anchor='w',fill='#b4c7db')
