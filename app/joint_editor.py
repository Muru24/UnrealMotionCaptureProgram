"""Source-frame pixel anchor editor. No model or Tk calls in worker threads."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import cv2
from PIL import Image, ImageTk

from core.pose3d.guidance import NAMES, validate_anchors

LABELS = ('골반 중심', '어깨 중심', '왼손목', '오른손목', '왼발목', '오른발목',
          '왼팔꿈치', '오른팔꿈치', '왼무릎', '오른무릎')


def swap_sides(points):
    """Explicit user operation; never infer anatomical left from screen X."""
    return {('right_'+n[5:] if n.startswith('left_') else
             'left_'+n[6:] if n.startswith('right_') else n):list(xy)
            for n,xy in points.items()}


class JointEditor:
    def __init__(self, parent, source, anchors, on_save, *, legs_only=False):
        self.legs_only=legs_only
        labels=tuple(LABELS[NAMES.index(n)] for n in ('left_knee','right_knee','left_ankle','right_ankle')) if legs_only else LABELS
        self.window = tk.Toplevel(parent)
        self.window.title('관절 지정 · 좌우는 인물 기준')
        self.window.geometry('720x850')
        self.window.transient(parent)
        self.window.grab_set()
        self.anchors = deepcopy(anchors)
        digest=hashlib.sha256()
        with Path(source).open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
        self.source_sha256 = digest.hexdigest()
        self.on_save = on_save
        self.capture = cv2.VideoCapture(str(source))
        if not self.capture.isOpened():
            self.capture.release(); self.window.destroy()
            raise ValueError('원본 영상을 열 수 없습니다.')
        self.count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.capture.get(cv2.CAP_PROP_FPS)
        self.index = 0
        self.frame = self.photo = None
        self.transform = None
        self.position = tk.IntVar(value=0)
        self.selected = tk.StringVar(value=labels[0])
        self.info = tk.StringVar()
        ttk.Label(self.window,text=('무릎·발목 지정 → 적용 후 닫기를 누르면 별도 보정 계산.\n발목 미지정 시 모델 발목을 기준으로 사용합니다. 신발 자동 추적은 아닙니다.\n좌우는 캐릭터 기준입니다. 가려진 점은 찍지 마세요.' if legs_only else '골반 → 어깨 중심 → 손목·발목 클릭. 중간 프레임도 지정 가능.\n정면 인물의 왼쪽 = 화면 오른쪽 / 뒷모습에서는 반대입니다.\n회전해도 인물의 좌우 이름은 유지합니다. 가려진 점은 찍지 마세요.')).pack(pady=8)
        bar = ttk.Frame(self.window); bar.pack(fill='x')
        ttk.Combobox(bar,textvariable=self.selected,values=labels,state='readonly',width=15).pack(side='left')
        ttk.Button(bar,text='선택 점 삭제',command=self.delete_point).pack(side='left')
        ttk.Button(bar,text='이 프레임 전체 삭제',command=self.delete_frame).pack(side='left')
        ttk.Button(bar,text='파일로 저장',command=self.export).pack(side='left')
        ttk.Button(bar,text='불러오기',command=self.import_file).pack(side='left')
        ttk.Button(self.window,text='현재 프레임의 좌우 지정 교환',command=self.swap_frame).pack(anchor='w')
        self.canvas = tk.Canvas(self.window,bg='#101722',highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.render())
        self.canvas.bind('<Button-1>',self.click)
        slider = ttk.Scale(self.window,from_=0,to=max(0,self.count-1),variable=self.position)
        slider.pack(fill='x',padx=12)
        slider.bind('<ButtonRelease-1>',self.seek)
        slider.bind('<KeyRelease>',self.seek)
        ttk.Label(self.window,textvariable=self.info).pack()
        nav = ttk.Frame(self.window);nav.pack(pady=8)
        ttk.Button(nav,text='이전 프레임',command=lambda:self.step(-1)).pack(side='left')
        ttk.Button(nav,text='다음 프레임',command=lambda:self.step(1)).pack(side='left')
        ttk.Button(nav,text='적용하고 계산' if legs_only else '적용 후 닫기',command=self.save).pack(side='left')
        ttk.Button(nav,text='취소',command=self.close).pack(side='left')
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.seek()

    def step(self, delta):
        self.position.set(max(0,min(self.count-1,self.index+delta)));self.seek()

    def seek(self,event=None):
        index = int(float(self.position.get()))
        self.capture.set(cv2.CAP_PROP_POS_FRAMES,index)
        ok, frame = self.capture.read()
        if ok:
            self.index,self.frame = index,frame
            self.render()
        else:
            self.info.set('이 프레임은 디코딩할 수 없습니다. 이전 프레임을 선택하세요.')

    def render(self):
        if self.frame is None:return
        h,w=self.frame.shape[:2]
        cw,ch=max(1,self.canvas.winfo_width()),max(1,self.canvas.winfo_height())
        scale=min(cw/w,ch/h)
        iw,ih=max(1,round(w*scale)),max(1,round(h*scale))
        ox,oy=(cw-iw)/2,(ch-ih)/2
        self.transform=(ox,oy,iw/w,ih/h)
        self.photo=ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(self.frame,cv2.COLOR_BGR2RGB)).resize((iw,ih)),master=self.window)
        self.canvas.delete('all');self.canvas.create_image(ox,oy,image=self.photo,anchor='nw')
        for name, (x,y) in self.anchors.get(self.index,{}).items():
            x,y=ox+x*iw/w,oy+y*ih/h
            self.canvas.create_oval(x-5,y-5,x+5,y+5,outline='#ff75db',width=2)
            self.canvas.create_text(x+8,y,text=LABELS[NAMES.index(name)],fill='#ff75db',anchor='w')
        self.info.set(f'프레임 {self.index} · {self.index/max(self.fps,1):.3f}초 · 지정 프레임 {len(self.anchors)}개')

    def click(self,event):
        if self.frame is None or self.transform is None:return
        ox,oy,sx,sy=self.transform
        x,y=(event.x-ox)/sx,(event.y-oy)/sy
        h,w=self.frame.shape[:2]
        if not (0<=x<w and 0<=y<h):return
        at=LABELS.index(self.selected.get())
        self.anchors.setdefault(self.index,{})[NAMES[at]]=[round(x,3),round(y,3)]
        if not self.legs_only:self.selected.set(LABELS[min(at+1,len(LABELS)-1)])
        self.render()

    def delete_point(self):
        points=self.anchors.get(self.index,{})
        points.pop(NAMES[LABELS.index(self.selected.get())],None)
        if not points:self.anchors.pop(self.index,None)
        self.render()

    def delete_frame(self):
        self.anchors.pop(self.index,None);self.render()

    def swap_frame(self):
        if self.index in self.anchors:
            self.anchors[self.index]=swap_sides(self.anchors[self.index])
            self.render()

    def save(self):
        h,w=self.frame.shape[:2]
        try:clean=validate_anchors(self.anchors,w,h,self.count)
        except ValueError as exc:
            messagebox.showerror('관절 지정 확인',str(exc),parent=self.window);return
        self.on_save(clean);self.close()

    def export(self):
        h,w=self.frame.shape[:2]
        try:clean=validate_anchors(self.anchors,w,h,self.count)
        except ValueError as exc:
            messagebox.showerror('관절 지정 확인',str(exc),parent=self.window);return
        path=filedialog.asksaveasfilename(parent=self.window,defaultextension='.json',
                                         filetypes=[('관절 지정 JSON','*.json')])
        if not path:return
        try:
            target=self.local_path(path)
            data={'version':1,'source_sha256':self.source_sha256,'anchors':clean}
            target.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        except (OSError,ValueError) as exc:
            messagebox.showerror('저장 실패',str(exc),parent=self.window)

    @staticmethod
    def local_path(path):
        p=Path(path)
        if str(p).startswith(('\\\\','//')) or '://' in str(p) or \
                p.is_symlink() or any(x.is_symlink() for x in p.parents):
            raise ValueError('로컬 일반 파일을 선택하세요.')
        return p

    def import_file(self):
        path=filedialog.askopenfilename(parent=self.window,filetypes=[('관절 지정 JSON','*.json')])
        if not path:return
        try:
            p=self.local_path(path)
            if p.stat().st_size>2*1024*1024:raise ValueError('지정 파일은 2MiB 이하여야 합니다.')
            data=json.loads(p.read_text(encoding='utf-8'))
            if not isinstance(data,dict) or data.get('version')!=1 or data.get('source_sha256')!=self.source_sha256:
                raise ValueError('이 영상에서 저장한 관절 지정 파일이 아닙니다.')
            h,w=self.frame.shape[:2]
            imported=validate_anchors(data.get('anchors'),w,h,self.count)
            if self.legs_only and any(n not in ('left_knee','right_knee','left_ankle','right_ankle') for points in imported.values() for n in points):
                raise ValueError('무릎·발목 앵커만 불러오세요.')
            self.anchors=imported
            self.render()
        except (OSError,ValueError,TypeError) as exc:
            messagebox.showerror('불러오기 실패',str(exc),parent=self.window)

    def close(self):
        self.capture.release();self.window.destroy()
