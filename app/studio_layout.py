"""Motion Studio desktop shell. Processing and playback stay in PrototypeApp."""
import os
import tkinter as tk
from tkinter import ttk, messagebox

BG = '#080d13'
SIDEBAR = '#0b1119'
PANEL2 = '#141f2b'
MINT = '#64dfc4'
PANEL = '#111a24'
EDGE = '#263545'
TEXT = '#edf4fc'
MUTED = '#8fa4b8'
BLUE = '#7bb7ff'


def theme(root):
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', font=('맑은 고딕', 10), background=BG, foreground=TEXT)
    for name, color in [('TFrame', BG), ('Panel.TFrame', PANEL)]:
        style.configure(name, background=color)
    style.configure('TLabel', background=BG, foreground=TEXT)
    style.configure('Panel.TLabel', background=PANEL)
    style.configure('Muted.TLabel', foreground=MUTED)
    style.configure('TButton', background='#192736', foreground=TEXT, padding=(13, 9),
                    borderwidth=1, bordercolor='#314456', lightcolor='#1d2a37', darkcolor='#1d2a37', focusthickness=0)
    style.map('TButton', background=[('disabled', '#17212c'), ('active', '#2b4057')], foreground=[('disabled', '#66758a')])
    style.configure('Accent.TButton', background=BLUE, foreground='#08131f', bordercolor=BLUE, padding=(17, 11), font=('맑은 고딕', 10, 'bold'))
    style.map('Accent.TButton', background=[('disabled', '#263545'), ('active', '#a6d0ff')],foreground=[('disabled','#6e859b'),('!disabled','#08131f')])
    style.configure('Outline.TButton', background='#172d44', bordercolor='#355b81')
    style.map('Outline.TButton', background=[('active', '#213b57')])
    style.configure('TCombobox', fieldbackground='#1d2935', background='#243242', foreground=TEXT, arrowcolor=MUTED, bordercolor='#405269', lightcolor='#405269', darkcolor='#405269', padding=7)
    style.map('TCombobox', fieldbackground=[('readonly', '#1d2935'), ('disabled', '#17212c')], foreground=[('readonly', TEXT), ('disabled', '#687b90')])
    style.configure('TCheckbutton', background=PANEL, foreground=TEXT, padding=(0, 3))
    style.map('TCheckbutton', background=[('active', PANEL)], foreground=[('disabled', '#687b90')])
    style.configure('TNotebook', background=PANEL, borderwidth=0, bordercolor=EDGE, lightcolor=EDGE, darkcolor=EDGE, tabmargins=(0, 0, 0, 5))
    style.configure('TNotebook.Tab', background='#16222e', foreground=MUTED, padding=(12, 7), borderwidth=0, lightcolor=EDGE, darkcolor=EDGE, bordercolor=EDGE)
    style.map('TNotebook.Tab', background=[('selected', '#123659'), ('active', '#1d3043')], foreground=[('selected', TEXT)])
    style.configure('Treeview', background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=31,
                    borderwidth=0, bordercolor=EDGE, lightcolor=PANEL, darkcolor=PANEL)
    style.map('Treeview', background=[('selected', '#152a43')], foreground=[('selected', '#ffffff')])
    style.configure('Treeview.Heading', background='#182632', foreground=MUTED, relief='flat', borderwidth=0, padding=5)
    style.map('Treeview.Heading', background=[('active', '#24394c')])
    style.configure('Vertical.TScrollbar', background='#34465b', troughcolor=PANEL, arrowcolor=MUTED,
                    bordercolor=PANEL, lightcolor='#34465b', darkcolor='#34465b', width=9)
    style.configure('Horizontal.TScale', background=PANEL, troughcolor='#263748', borderwidth=0, sliderlength=16,lightcolor=EDGE,darkcolor=EDGE,bordercolor=EDGE)
    for control in ('TEntry','TSpinbox'):
        style.configure(control,fieldbackground='#1d2935',foreground=TEXT,background='#243242',arrowcolor=MUTED,insertcolor=TEXT,padding=5)
    style.configure('Horizontal.TProgressbar', background=BLUE, troughcolor='#29384a', borderwidth=0, thickness=8,lightcolor=EDGE,darkcolor=EDGE,bordercolor=EDGE)
    style.configure('TPanedwindow', background=EDGE)
    style.configure('TRadiobutton',background=PANEL,foreground=TEXT)
    style.map('TRadiobutton',background=[('active',PANEL)])
    style.configure('TMenubutton',background='#192736',foreground=TEXT,padding=(10,8))
    rounded_buttons(root,style)
    root.option_add('*TCombobox*Listbox.background', '#1d2935')
    root.option_add('*TCombobox*Listbox.foreground', TEXT)
    root.option_add('*TCombobox*Listbox.selectBackground', '#155b9f')


def rounded_buttons(root,style):
    from PIL import Image,ImageDraw,ImageTk
    root._studio_button_images=[]
    for name,normal,hover,border in [('TButton','#192736','#243b50','#314456'),('Accent.TButton',BLUE,'#a6d0ff',BLUE),('Outline.TButton','#172d44','#213b57','#355b81')]:
        images=[]
        for fill,line in [(normal,border),(hover,border),('#17212c','#263545')]:
            image=Image.new('RGB',(30,30),PANEL);draw=ImageDraw.Draw(image);draw.rounded_rectangle((0,0,29,29),radius=8,fill=fill,outline=line)
            images.append(ImageTk.PhotoImage(image,master=root))
        root._studio_button_images.extend(images);element='Studio'+name.replace('.','')+'.border'
        style.element_create(element,'image',images[0],('disabled',images[2]),('active',images[1]),border=7,sticky='nswe')
        style.layout(name,[(element,{'sticky':'nswe','children':[('Button.padding',{'sticky':'nswe','children':[('Button.label',{'sticky':'nswe'})]})]})])
        style.configure(name,padding=(14,5) if name=='Accent.TButton' else (12,3))


def label(parent, text=None, muted=False, size=10, bold=False, **kw):
    foreground=kw.pop('fg',MUTED if muted else TEXT)
    return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=foreground,
                    font=('맑은 고딕', size, 'bold' if bold else 'normal'), anchor='w', **kw)


def card(parent, title=None):
    frame = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=EDGE, padx=15, pady=13)
    # Mask the square native-frame corners; keep the content as real widgets.
    for anchor, rx, ry, box in [('nw',0,0,(0,0,20,20)), ('ne',1,0,(-10,0,10,20)),
                               ('sw',0,1,(0,-10,20,10)), ('se',1,1,(-10,-10,10,10))]:
        corner=tk.Canvas(frame,width=10,height=10,bg=BG,highlightthickness=0)
        corner.create_oval(*box,fill=PANEL,outline=EDGE)
        corner.place(relx=rx,rely=ry,anchor=anchor)
    if title:
        label(frame, title, size=11, bold=True).pack(anchor='w', pady=(0, 10))
    return frame


def icon(canvas, kind, x=30, y=45, color=TEXT):
    """Small line icons, drawn at native display resolution."""
    if kind == 0:
        canvas.create_rectangle(x-20, y-22, x+20, y+22, outline=color, width=2)
        canvas.create_polygon(x-5, y-11, x+9, y, x-5, y+11, fill='', outline=color, width=2)
    elif kind == 1:
        for a,b,c,d in [(x,y-18,x,y),(x,y,x-16,y+23),(x,y,x+16,y+23)]:
            canvas.create_line(a,b,c,d,fill=color,width=2)
        for a,b in [(x,y-23),(x,y),(x-17,y+27),(x+17,y+27)]:
            canvas.create_oval(a-4,b-4,a+4,b+4,outline=color,width=2,fill=PANEL)
    else:
        canvas.create_polygon(x,y-24,x+20,y-13,x+20,y+12,x,y+25,x-20,y+12,x-20,y-13,fill='',outline=color,width=2)
        canvas.create_line(x-20,y-13,x,y-1,x+20,y-13,fill=color,width=2)
        canvas.create_line(x,y-1,x,y+25,fill=color,width=2)


class NavigationItem(tk.Canvas):
    def __init__(self,parent,index,title,subtitle,command):
        super().__init__(parent,height=66,bg=SIDEBAR,highlightthickness=0,cursor='hand2',takefocus=True)
        self.index,self.title,self.subtitle,self.command=index,title,subtitle,command;self.selected=False;self.hover=False
        self.bind('<Configure>',lambda e:self.draw());self.bind('<Button-1>',lambda e:self.command())
        self.bind('<Return>',lambda e:self.command());self.bind('<space>',lambda e:self.command())
        self.bind('<Enter>',lambda e:self.rollover(True));self.bind('<Leave>',lambda e:self.rollover(False))
        self.bind('<FocusIn>',lambda e:self.draw());self.bind('<FocusOut>',lambda e:self.draw())

    def rollover(self,value):self.hover=value;self.draw()

    def draw(self):
        self.delete('all');w=max(200,self.winfo_width());fill='#152a43' if self.selected else '#141f2b' if self.hover else SIDEBAR
        self.create_polygon(10,1,w-10,1,w-2,9,w-2,56,w-10,64,10,64,2,56,2,9,smooth=True,fill=fill,outline='#295883' if self.selected else fill)
        if self.selected:self.create_line(2,18,2,47,fill=BLUE,width=3)
        self.create_polygon(17,17,40,17,45,22,45,44,40,49,17,49,12,44,12,22,smooth=True,fill='#23517e' if self.selected else '#101822',outline='#498cd5' if self.selected else '#354454')
        self.create_text(29,33,text=f'{self.index+1:02d}',fill='#c5e3ff' if self.selected else '#8da0b4',font=('Consolas',10,'bold'))
        self.create_text(58,23,text=self.title,anchor='w',fill=TEXT if self.selected else '#a8b9cb',font=('맑은 고딕',10,'bold'))
        self.create_text(58,44,text=self.subtitle,anchor='w',fill='#8eafca' if self.selected else '#74889f',font=('Segoe UI',8))
        if self.focus_get()==self:self.create_rectangle(5,5,w-6,60,outline=BLUE,dash=(2,3))


class StudioLayout:
    TITLES = ['영상 트래킹', '스켈레톤 검수', '모델 적용', '애니메이션 편집', '최종 결과 / 내보내기']
    DESCRIPTIONS = ['영상을 가져와 대상의 움직임을 분석하고 모션을 트래킹합니다.',
                    '트래킹한 데이터로 표준 스켈레톤을 생성하고 관절을 확인합니다.',
                    '애니메이션을 저장하고 캐릭터에 적용된 결과를 확인합니다.',
                    '모델과 본의 위치·회전을 조절하고 키프레임으로 편집 결과를 저장합니다.',
                    '완료된 최종 모델 애니메이션을 확인하고 필요한 형식으로 내보냅니다.']

    def __init__(self, app):
        self.app = app
        self.root = app.root
        theme(self.root)
        self.root.title('Motion Studio · 모션 캡처 / 애니메이션 리타게팅 도구')
        self.root.geometry('1600x940')
        self.root.minsize(1320, 900)
        self.root.configure(bg=BG)
        self.build_header()
        shell = tk.Frame(self.root, bg=BG)
        shell.pack(fill='both', expand=True)
        sidebar = tk.Frame(shell, bg=SIDEBAR, width=244, highlightthickness=1, highlightbackground=EDGE)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        label(sidebar,'ACTIVE PROJECT',muted=True,size=8,bold=True).pack(anchor='w',padx=25,pady=(23,10))
        project=tk.Frame(sidebar,bg='#142132',highlightbackground='#304258',highlightthickness=1,padx=13,pady=12);project.pack(fill='x',padx=13,pady=(0,18))
        label(project,'◇  현재 작업',size=10,bold=True).pack(anchor='w')
        self.project_text=tk.StringVar(value=app.file_text.get())
        label(project,textvariable=self.project_text,muted=True,size=8,wraplength=180).pack(anchor='w',pady=(6,0))
        label(sidebar,'WORKFLOW',muted=True,size=8,bold=True).pack(anchor='w',padx=25,pady=(0,8))
        self.nav=[]
        subtitles=['Video → Motion','3D Skeleton Review','Retarget & Preview','Timeline & Keyframe','Final Review & Export']
        for i,title in enumerate(self.TITLES):
            item=NavigationItem(sidebar,i,'최종 결과' if i==4 else title,subtitles[i],lambda n=i:self.show_stage(n));item.pack(fill='x',padx=12,pady=3);self.nav.append(item)
        tk.Frame(sidebar,bg=EDGE,height=1).pack(fill='x',padx=24,pady=(15,13))
        label(sidebar,'WORKSPACE STATUS',muted=True,size=8,bold=True).pack(anchor='w',padx=25)
        self.side_status=tk.StringVar(value='영상 입력 대기')
        label(sidebar,textvariable=self.side_status,muted=True,size=9,wraplength=185).pack(anchor='w',padx=25,pady=(10,0))
        lower=tk.Frame(sidebar,bg=SIDEBAR);lower.pack(side='bottom',fill='x',padx=22,pady=22)
        local=tk.Frame(lower,bg='#111d27',highlightbackground='#253848',highlightthickness=1,padx=12,pady=12);local.pack(fill='x')
        label(local,'●  LOCAL WORKSPACE',size=8,bold=True,fg=MINT).pack(anchor='w')
        label(local,'영상과 결과는 이 PC에 저장됩니다.',muted=True,size=8,wraplength=165).pack(anchor='w',pady=(6,0))
        label(lower,'MOTION STUDIO / DESKTOP',muted=True,size=7).pack(anchor='w',pady=(15,0))
        self.workspace = tk.Frame(shell, bg=BG)
        self.workspace.pack(side='left', fill='both', expand=True, padx=28, pady=(18, 14))
        self.workspace.columnconfigure(0, weight=1)
        self.workspace.rowconfigure(0, weight=1)
        self.pages, self.viewer_hosts, self.result_hosts = [], [], []
        self.stage_labels=[]
        for i in range(len(self.TITLES)):
            page = tk.Frame(self.workspace, bg=BG)
            page.grid(row=0, column=0, sticky='nsew')
            page.columnconfigure(0, weight=1)
            heading=tk.Frame(page,bg=BG);heading.grid(row=0,column=0,sticky='ew',pady=(0,8))
            label(heading,f'●  {i+1:02d} / '+['MOTION TRACKING','SKELETON REVIEW','MODEL RETARGET','ANIMATION EDITOR','FINAL REVIEW / EXPORT'][i],size=8,bold=True,fg=BLUE).pack(anchor='w')
            label(heading,self.TITLES[i],size=23,bold=True).pack(anchor='w',pady=(4,0))
            sub=tk.Frame(page,bg=BG);sub.grid(row=1,column=0,sticky='ew',pady=(0,10));sub.columnconfigure(0,weight=1)
            label(sub,self.DESCRIPTIONS[i],muted=True,size=10).grid(row=0,column=0,sticky='w',pady=(0,8))
            pipeline=tk.Frame(sub,bg=BG);pipeline.grid(row=1,column=0,sticky='ew');steps=[]
            for n,title in enumerate(self.TITLES):
                pipeline.columnconfigure(n,weight=1,uniform='step')
                tile=tk.Label(pipeline,text=f'{n+1:02d}   '+['영상 입력','본 검수','모델 적용','키 편집','최종 내보내기'][n],bg='#101822',fg='#6f849a',font=('맑은 고딕',9),highlightthickness=1,highlightbackground=EDGE,padx=8,pady=5)
                tile.grid(row=0,column=n,sticky='ew',padx=(0,6 if n<len(self.TITLES)-1 else 0));steps.append(tile)
            self.stage_labels.append(steps)
            self.pages.append(page)
        self.build_upload()
        self.build_bones()
        self.build_model()
        self.build_viewer()
        from app.animation_editor import AnimationEditor
        self.pages[3].rowconfigure(2,weight=1)
        self.editor=AnimationEditor(self.pages[3],app)
        self.editor.grid(row=2,column=0,sticky='nsew')
        from app.final_panel import FinalResultsPanel
        self.pages[4].rowconfigure(2,weight=1)
        self.final_panel=FinalResultsPanel(self.pages[4],app);self.final_panel.grid(row=2,column=0,sticky='nsew')
        from app.result_browser import ResultBrowser
        app.result_panel = ResultBrowser(self.workspace, app_root()/'outputs', app.preview_saved_result, app.before_result_delete, lambda:app.busy,compact=True)
        app.result_panel.window.configure(padding=0)
        self.build_status()
        self.active_stage = None
        self.show_stage(0)
        app.status_text.trace_add('write',lambda *args:self.update_summary())
        app.file_text.trace_add('write',lambda *args:self.update_summary())
        self.root.after(250,self.dark_titlebar)

    def build_header(self):
        bar=tk.Frame(self.root,bg='#0d141d',height=64,highlightbackground=EDGE,highlightthickness=1);bar.pack(fill='x');bar.pack_propagate(False)
        mark=tk.Canvas(bar,width=34,height=34,bg='#0d141d',highlightthickness=0);mark.pack(side='left',padx=(23,12),pady=14)
        mark.create_polygon(9,0,25,0,34,9,34,25,25,34,9,34,0,25,0,9,smooth=True,fill=BLUE,outline='')
        for x,h in [(9,7),(14,17),(20,24),(25,12)]:mark.create_line(x,17-h/2,x,17+h/2,fill='#08131f',width=2)
        brand=tk.Frame(bar,bg='#0d141d');brand.pack(side='left')
        label(brand,'Motion Studio',size=12,bold=True).pack(anchor='w');label(brand,'CAPTURE / RETARGET / EDIT',muted=True,size=6).pack(anchor='w',pady=(1,0))
        self.breadcrumb=tk.StringVar(value='WORKSPACE   ›   LOCAL PROJECT   ›   영상 트래킹')
        label(bar,textvariable=self.breadcrumb,muted=True,size=9).pack(side='left',padx=30)
        ttk.Button(bar,text='사용 안내  ?',command=self.help).pack(side='right',padx=22,pady=14)
        label(bar,'●  LOCAL · OFFLINE',size=8,fg=MINT).pack(side='right',padx=14)

    def columns(self, page, row):
        area = tk.Frame(page, bg=BG)
        area.grid(row=row, column=0, sticky='nsew')
        page.rowconfigure(row, weight=1)
        area.columnconfigure(0, weight=1)
        area.columnconfigure(1, minsize=316)
        area.rowconfigure(0, weight=1)
        viewer = tk.Frame(area, bg=BG)
        viewer.grid(row=0, column=0, sticky='nsew', padx=(0, 13))
        viewer.columnconfigure(0, weight=1)
        viewer.rowconfigure(0, weight=1)
        right = tk.Frame(area, bg=BG, width=316)
        right.grid(row=0, column=1, sticky='nsew')
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        results = card(right)
        results.grid(row=1, column=0, sticky='nsew', pady=(12, 0))
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)
        self.viewer_hosts.append(viewer)
        self.result_hosts.append(results)
        return viewer, right

    def build_upload(self):
        a=self.app;_,right=self.columns(self.pages[0],2)
        settings=card(right,'트래킹 설정');settings.grid(row=0,column=0,sticky='ew')
        a.drop_area=tk.Frame(settings,bg='#111f2c',highlightbackground='#456382',highlightthickness=1,padx=10,pady=10)
        a.drop_area.pack(fill='x')
        a.file_label=label(a.drop_area,textvariable=a.file_text,bold=True,size=9,wraplength=260);a.file_label.pack(anchor='w')
        label(a.drop_area,textvariable=a.info_text,muted=True,size=8,wraplength=260).pack(anchor='w',pady=(5,8))
        a.choose_button=ttk.Button(a.drop_area,text='＋  영상 선택',command=a.choose,style='Outline.TButton');a.choose_button.pack(fill='x')
        label(settings,'자동 추출 · SAM 3D + SAM 2',bold=True,size=9).pack(anchor='w',pady=(12,0))
        label(settings,'추적 → 본·손 보정 → 선택 모델 → 파일 저장',muted=True,size=8,wraplength=275).pack(anchor='w',pady=(5,12))
        target=tk.Frame(settings,bg=PANEL);target.pack(fill='x')
        a.candidate_button=ttk.Button(target,text='대상 선택',command=a.find_candidates,state='disabled');a.candidate_button.pack(side='right',padx=(5,0))
        a.target_box=ttk.Combobox(target,textvariable=a.target,values=('자동 선택',),state='readonly',width=12);a.target_box.pack(side='left',fill='x',expand=True)
        label(settings,'여러 인물 중 직접 고를 때만 대상 선택을 사용하세요.',muted=True,size=8,wraplength=270).pack(anchor='w',pady=(8,0))

    def build_bones(self):
        a = self.app
        viewer, right = self.columns(self.pages[1], 2)
        # Video and skeleton are siblings under the same page, not extra pages.
        self.bone_video_host = tk.Frame(viewer, bg=BG)
        self.bone_video_host.grid(row=0,column=0,sticky='nsew',padx=(0,10))
        self.bone_video_host.columnconfigure(0,weight=1)
        self.bone_video_host.rowconfigure(0,weight=1)
        viewer.columnconfigure(1,weight=1)
        self.skeleton_host = card(viewer)
        self.skeleton_host.grid(row=0,column=1,sticky='nsew')
        self.skeleton_host.columnconfigure(0,weight=1)
        self.skeleton_host.rowconfigure(0,weight=1)
        self.bone_stacked=False
        viewer.columnconfigure(0,uniform='bone-view')
        viewer.columnconfigure(1,uniform='bone-view')
        from app.skeleton_panel import SkeletonPanel
        a.skeleton_panel = SkeletonPanel(self.workspace, None)
        a.skeleton_panel.canvas.configure(bg='#0a1119')
        info = card(right, '스켈레톤 생성')
        info.grid(row=0,column=0,sticky='ew')
        label(info, '표준 Humanoid · 22본', size=12,bold=True).pack(anchor='w')
        label(info, '골반 · 척추 · 머리 · 팔 · 다리', muted=True).pack(anchor='w',pady=(6,12))
        label(info,'추출 시 자동 생성됩니다.\n오른쪽 결과를 선택하면 영상과 함께 표시됩니다.',muted=True,size=10,wraplength=300).pack(anchor='w')

    def build_model(self):
        a = self.app
        _, right = self.columns(self.pages[2], 2)
        controls = card(right, '모델 / 애니메이션')
        controls.grid(row=0,column=0,sticky='ew')
        from app.user_models import selected
        self.model_keys={};self.model_choice=tk.StringVar(value=selected())
        self.model_box=ttk.Combobox(controls,textvariable=self.model_choice,state='readonly',width=24)
        self.model_box.pack(fill='x',pady=(0,8));self.model_box.bind('<<ComboboxSelected>>',self.choose_model)
        self.add_model_button=ttk.Button(controls,text='+  모델 추가',command=a.add_user_model)
        self.add_model_button.pack(fill='x',pady=(0,10))
        self.builtin_status=tk.StringVar()
        label(controls,textvariable=self.builtin_status,muted=True,size=9,wraplength=300).pack(anchor='w',pady=(0,8))
        label(controls,'본이 있으면 기존 본을 유지하고, 없으면 기본 본·웨이트를 생성합니다.\n선택한 모델은 전체 추출에 자동 적용됩니다.\n추정한 본은 3·4번에서 확인해 주세요.',muted=True,size=9,wraplength=300).pack(anchor='w')
        self.builtin_apply_button=ttk.Button(controls,text='선택 모델 적용',command=a.apply_builtin_model)
        self.builtin_install_button=ttk.Button(controls,text='기본 모델 파일 연결',command=a.install_builtin_model)
        self.refresh_builtin_status()

    def build_viewer(self):
        a = self.app
        self.viewer = card(self.workspace)
        self.viewer.columnconfigure(0,weight=1)
        self.viewer.rowconfigure(1,weight=1)
        bar = tk.Frame(self.viewer,bg=PANEL)
        bar.grid(row=0,column=0,sticky='ew',pady=(0,11))
        self.viewer_title = label(bar,'비디오 미리보기',size=12,bold=True)
        self.viewer_title.pack(side='left')
        a.kind_box = ttk.Combobox(bar,textvariable=a.result_kind,values=('원본 영상',),state='disabled',width=18)
        a.kind_box.pack(side='right')
        a.kind_box.bind('<<ComboboxSelected>>',a.change_view)
        self.preview_images=tk.Frame(self.viewer,bg=PANEL)
        self.preview_images.grid(row=1,column=0,sticky='nsew')
        self.preview_images.columnconfigure(0,weight=1,uniform='video')
        self.preview_images.rowconfigure(1,weight=1)
        self.original_title=label(self.preview_images,'원본 영상',muted=True,size=10)
        self.original_title.grid(row=0,column=0,sticky='w',pady=(0,8))
        self.tracking_title=label(self.preview_images,'트래킹 결과 · 원시 뼈대',muted=True,size=10)
        self.tracking_title.grid(row=0,column=1,sticky='w',padx=(10,0),pady=(0,8))
        a.canvas = tk.Canvas(self.preview_images,bg='#0a141f',highlightbackground=EDGE,highlightthickness=1)
        a.canvas.grid(row=1,column=0,sticky='nsew')
        a.canvas.bind('<Configure>',lambda e:a.render_frame())
        a.tracking_canvas=tk.Canvas(self.preview_images,bg='#0a141f',highlightbackground=EDGE,highlightthickness=1)
        a.tracking_canvas.grid(row=1,column=1,sticky='nsew',padx=(10,0))
        a.tracking_canvas.bind('<Configure>',lambda e:a.render_frame())
        self.reconnect_button=ttk.Button(bar,text='원본 다시 연결',command=a.reconnect_original)
        controls = tk.Frame(self.viewer,bg=PANEL)
        controls.grid(row=2,column=0,sticky='ew',pady=(10,0))
        controls.columnconfigure(1,weight=1)
        a.play_button = ttk.Button(controls,text='재생',command=a.toggle_play,state='disabled',width=7)
        a.play_button.grid(row=0,column=0,padx=(0,9))
        a.seek = ttk.Scale(controls,from_=0,to=1,variable=a.seek_var,state='disabled')
        a.seek.grid(row=0,column=1,sticky='ew')
        a.seek.bind('<ButtonPress-1>',a.seek_begin)
        a.seek.bind('<ButtonRelease-1>',a.seek_end)
        a.seek.bind('<KeyRelease>',a.seek_end)
        tk.Label(controls,textvariable=a.time_text,width=16,anchor='e',bg=PANEL,fg=MUTED).grid(row=0,column=2,padx=(7,0))

    def build_status(self):
        a = self.app
        status = card(self.workspace)
        self.status=status
        status.grid(row=1,column=0,sticky='ew',pady=(13,0))
        status.columnconfigure(0,weight=1)
        a.status_label = label(status,textvariable=a.status_text,bold=True)
        a.status_label.grid(row=0,column=0,sticky='w')
        actions = tk.Frame(status,bg=PANEL)
        actions.grid(row=0,column=1,rowspan=2,sticky='e',padx=(20,0))
        a.start_button = ttk.Button(actions,text='▶  전체 추출',style='Accent.TButton',command=a.start,state='disabled')
        a.start_button.pack(side='left',padx=(0,10))
        a.folder_button = ttk.Button(actions,text='결과 폴더 열기',command=a.open_folder,state='disabled')
        a.folder_button.pack(side='left',padx=(0,8))
        a.cancel_button = ttk.Button(actions,text='취소',command=a.cancel,state='disabled')
        a.cancel_button.pack(side='left')
        a.progress = ttk.Progressbar(status,mode='determinate',maximum=100)
        a.progress.grid(row=1,column=0,sticky='ew',pady=(9,6))
        a.detail_label = label(status,textvariable=a.detail_text,muted=True,size=9,wraplength=950)
        a.detail_label.grid(row=2,column=0,columnspan=2,sticky='w')
        status.bind('<Configure>',lambda e:a.detail_label.configure(wraplength=max(300,e.width-35)))

    def show_stage(self, index):
        if index not in range(len(self.TITLES)):raise ValueError('Unknown stage')
        if not self.editor.finish_edit():return
        previous=self.active_stage
        self.status.grid() if index!=4 or self.app.busy else self.status.grid_remove()
        self.breadcrumb.set('WORKSPACE   ›   LOCAL PROJECT   ›   '+self.TITLES[index])
        for row in self.stage_labels:
            for n,tile in enumerate(row):tile.configure(bg='#162941' if n==index else '#101822',fg='#d5ebff' if n==index else '#6f849a',highlightbackground='#4679ad' if n==index else EDGE)
        self.editor.pause();self.final_panel.pause()
        self.viewer.grid_forget()
        self.app.skeleton_panel.grid_forget()
        self.app.result_panel.window.grid_forget()
        for i,page in enumerate(self.pages):
            if i==index:page.grid()
            else:page.grid_remove()
            self.nav[i].selected=i==index
            self.nav[i].draw()
        if index==4:
            self.app.pause();self.app.start_button.pack_forget();self.app.folder_button.pack_forget();self.active_stage=index
            self.final_panel.refresh();return
        if not self.app.folder_button.winfo_manager():self.app.folder_button.pack(side='left',before=self.app.cancel_button,padx=(0,8))
        if index==3:
            self.app.pause();self.app.start_button.pack_forget();self.active_stage=index
            if previous==2 and self.editor.clip and self.app.requested_preview_path in (self.editor.preview,self.editor.last_output):
                self.editor.set_frame(round(self.app.position/self.app.video_fps*self.editor.clip.fps))
            self.editor.refresh();self.root.after_idle(self.editor.render);return
        self.app.result_panel.refresh(selected=self.app.result_dir)
        host=self.bone_video_host if index==1 else self.viewer_hosts[index]
        self.viewer.grid(in_=host,row=0,column=0,sticky='nsew')
        if index==1:self.app.skeleton_panel.grid(in_=self.skeleton_host,row=0,column=0,sticky='nsew')
        self.app.result_panel.window.grid(in_=self.result_hosts[index],row=0,column=0,sticky='nsew')
        self.viewer_title.configure(text=['원본 / 트래킹 비교','원본 영상','모델 적용 미리보기'][index])
        self.reconnect_button.pack_forget()
        self.app.kind_box.pack_forget()
        self.reconnect_button.pack(side='right')
        if index in (0,2):
            self.preview_images.columnconfigure(1,weight=1,uniform='video')
            self.tracking_title.configure(text='모델 애니메이션' if index==2 else '트래킹 결과 · 원시 뼈대')
            self.original_title.grid();self.tracking_title.grid();self.app.tracking_canvas.grid()
        else:
            self.preview_images.columnconfigure(1,weight=0,uniform='')
            self.original_title.grid_remove();self.tracking_title.grid_remove();self.app.tracking_canvas.grid_remove()
        if index==0:self.app.start_button.pack(side='left',before=self.app.folder_button,padx=(0,10))
        else:self.app.start_button.pack_forget()
        self.active_stage=index
        if previous is not None and previous!=index:self.app.stage_preview_changed()
        if index==2 and previous==3 and self.editor.clip and self.app.requested_preview_path in (self.editor.preview,self.editor.last_output) and self.app.capture is not None:
            self.app.seek_var.set(round(self.editor.frame/self.editor.clip.fps*self.app.video_fps));self.app.seek_end()
        if index==2:self.refresh_models()
        self.root.after_idle(self.app.render_frame)

    def update_summary(self):
        if self.active_stage==4 and self.final_panel.current:
            name=self.final_panel.current.label;self.project_text.set(self.app.display_name(name));self.side_status.set('최종 결과 준비됨\n'+self.app.display_name(name));return
        self.project_text.set(self.app.file_text.get())
        if self.app.busy:self.side_status.set(self.app.leg_phase or '추출 처리 중')
        elif self.app.result_dir:self.side_status.set('결과 준비됨\n'+self.app.display_name(self.app.result_dir.name))
        elif self.app.source:self.side_status.set('영상 준비됨\n'+self.app.display_name(self.app.source.name))
        else:self.side_status.set('영상 입력 대기')

    def refresh_models(self):
        self.refresh_builtin_status()

    def selected_builtin(self):
        return self.model_keys.get(self.model_choice.get(),'unreal_manny')

    def choose_model(self,event=None):
        from app.user_models import select
        if self.app.busy:return
        select(self.selected_builtin());self.refresh_builtin_status()

    def refresh_builtin_status(self):
        from app.builtin_models import installed
        from app.model_preview import model_asset,metadata
        from app.user_models import registered,selected
        rows=registered();key=selected()
        self.model_keys={'Unreal · Manny':'unreal_manny'}
        for k,r in rows.items():
            name=r['name']+f" · {r['bones']}본"
            if name in self.model_keys:name+=' · '+k[-4:]
            self.model_keys[name]=k
        self.model_box.configure(values=list(self.model_keys),state='disabled' if self.app.busy else 'readonly')
        self.model_choice.set(next((name for name,value in self.model_keys.items() if value==key),'Unreal · Manny'))
        self.add_model_button.configure(state='disabled' if self.app.busy else 'normal')
        ready=installed('unreal_manny') if key=='unreal_manny' else key in rows;result=self.app.result_dir
        result_ready=bool(result and (result/'sam3d.json').is_file())
        item=model_asset(result,None) if result_ready else None
        missing=result_ready and (item is None or (metadata(item.path) or {}).get('model_id','unreal_manny')!=key)
        text='추적·본·손 보정·모델 적용·파일 저장이 추출에 통합되어 있습니다.'
        if key in rows:
            row=rows[key];text=f"{row['bones']}개 본 · 손가락 {row['fingers']}개 본 · "+('본 자동 생성' if row['auto_rigged'] else '기존 본 유지')
            if row.get('deform_helpers'):text+=f"\n메시 체형에 맞춘 변형 보조 본 {row['deform_helpers']}개"
            if row.get('estimated'):text+='\nT/A 포즈 기반 추정 · 관절 위치 검수 필요'
        self.builtin_status.set(text if ready else 'Manny 모델 파일을 연결해야 추출을 완료할 수 있습니다.')
        self.builtin_apply_button.pack_forget();self.builtin_install_button.pack_forget()
        if missing and not self.app.busy:self.builtin_apply_button.pack(fill='x',pady=(8,0))
        if not ready and key=='unreal_manny':self.builtin_install_button.pack(fill='x',pady=(8,0))
        self.builtin_apply_button.configure(state='disabled' if self.app.busy else 'normal')
        self.builtin_install_button.configure(state='disabled' if self.app.busy else 'normal')

    def help(self):
        messagebox.showinfo('Motion Studio 사용 방법',
            '1. 영상 업로드 / 트래킹\nMP4를 선택하고 전체 추출을 누르면 본·손 보정·선택 모델·파일 저장까지 자동 처리합니다.\n\n'
            '2. 본 생성\n추출 시 자동 생성된 본과 3D 스켈레톤을 확인합니다.\n\n'
            '3. 모델 적용\n선택한 모델의 애니메이션 결과를 재생합니다. Blender / FBX 파일도 함께 저장됩니다.\n\n'
            '4. 애니메이션 편집\n모델을 불러와 본을 선택하고 위치(cm)·회전(°) 오프셋을 키로 저장합니다. 편집 결과 출력으로 새 애니메이션과 미리보기를 만듭니다.\n\n'
            '5. 최종 결과 / 내보내기\n최종 완료본만 확인하고 FBX·Blender·MP4 형식으로 선택한 폴더에 내보냅니다.\n\n'
            '출력 결과는 미리보기 옆 목록에서 열고 삭제·복원할 수 있습니다.\n'
            '3번 모델 추가: FBX·GLB·OBJ·BLEND를 로컬로 불러옵니다. 본 없는 사람형 T/A 포즈는 기본 본을 추정합니다. 얼굴 표정 본은 포함하지 않습니다.',parent=self.root)

    def dark_titlebar(self):
        if os.name!='nt':return
        import ctypes
        try:
            user32=ctypes.windll.user32
            user32.GetParent.argtypes=[ctypes.c_void_p]
            user32.GetParent.restype=ctypes.c_void_p
            hwnd=user32.GetParent(self.root.winfo_id())
            value=ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(hwnd),20,ctypes.byref(value),ctypes.sizeof(value))
            for attribute,color in [(35,0x0020170e),(36,0x00fbf3ed)]:
                value=ctypes.c_int(color)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(hwnd),attribute,ctypes.byref(value),ctypes.sizeof(value))
        except (AttributeError,OSError):pass


def app_root():
    from app.gui_jobs import ROOT
    return ROOT
