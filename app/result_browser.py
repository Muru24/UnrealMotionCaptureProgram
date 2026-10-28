"""Read-only previews and explicit reversible deletion of output folders."""
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk,messagebox
from app.result_library import list_results,list_previews,trash_result,list_trash,restore_result

class ResultBrowser:
    def __init__(self,parent,root,on_preview,before_delete,is_busy=lambda:False,compact=False):
        self.compact=compact;self.refreshing=False
        self.root=Path(root);self.on_preview=on_preview;self.before_delete=before_delete;self.is_busy=is_busy
        self.window=ttk.Frame(parent,width=340,padding=(10,0,0,0))
        if compact:self.window.configure(style='Panel.TFrame')
        heading=ttk.Frame(self.window,style='Panel.TFrame' if compact else 'TFrame');heading.pack(fill='x',pady=(0,8))
        ttk.Label(heading,text='출력 결과',font=('맑은 고딕',11,'bold'),style='Panel.TLabel' if compact else 'TLabel').pack(side='left')
        self.tabs=ttk.Notebook(self.window);self.tabs.pack(fill='both',expand=True)
        active=ttk.Frame(self.tabs);deleted=ttk.Frame(self.tabs);self.tabs.add(active,text='결과');self.tabs.add(deleted,text='프로그램 휴지통')
        self.tree=self.make_tree(active,('name',),('결과 폴더',))
        self.trash_tree=self.make_tree(deleted,('name',),('원래 결과 이름',))
        if compact:
            style=ttk.Style(parent);style.layout('Result.TNotebook.Tab',[]);self.tabs.configure(style='Result.TNotebook')
            choices=ttk.Menubutton(heading,text='⋯',width=2);choices.pack(side='right')
            menu=tk.Menu(choices,tearoff=False,bg='#111a24',fg='#edf4fc');choices.configure(menu=menu)
            menu.add_command(label='출력 결과',command=lambda:self.tabs.select(0));menu.add_command(label='프로그램 휴지통',command=lambda:self.tabs.select(1))
        self.tree.bind('<<TreeviewSelect>>',lambda e:None if self.refreshing else self.select());self.tree.bind('<Double-1>',lambda e:self.preview())
        self.info=tk.StringVar(value='결과를 선택하세요.')
        if not compact:ttk.Label(active,textvariable=self.info,wraplength=300).pack(fill='x',pady=5)
        self.preview_name=tk.StringVar()
        self.combo=ttk.Combobox(active,textvariable=self.preview_name,state='readonly',width=28);self.combo.pack(fill='x',pady=5)
        self.combo.bind('<<ComboboxSelected>>',lambda e:self.preview())
        row=ttk.Frame(active);row.pack(fill='x',pady=5)
        self.preview_button=None
        if not compact:
            self.preview_button=ttk.Button(row,text='미리보기',command=self.preview);self.preview_button.pack(side='left')
        self.delete_button=ttk.Button(row,text='삭제' if compact else '결과 삭제',command=self.delete);self.delete_button.pack(side='left' if compact else 'right',padx=(5,0) if compact else 0)
        self.restore_button=ttk.Button(deleted,text='선택 결과 복원',command=self.restore);self.restore_button.pack(pady=8)
        if not compact:ttk.Label(self.window,text='삭제한 결과는 프로그램 휴지통에서 복원할 수 있습니다.',wraplength=300).pack(fill='x',pady=5)
        self.refresh_button=None
        if not compact:
            self.refresh_button=ttk.Button(self.window,text='새로고침',command=self.refresh);self.refresh_button.pack(anchor='e',pady=5)
        if compact:
            # Reserve actions first so reducing the window only shrinks the list.
            listing=active.winfo_children()[0]
            for child in (listing,self.combo,row):child.pack_forget()
            row.pack(side='bottom',fill='x',pady=(3,0))
            self.combo.pack(side='bottom',fill='x',pady=(4,2))
            listing.pack(fill='both',expand=True)
            for frame in (active,deleted,row,listing):frame.configure(style='Panel.TFrame')
        self.refresh()

    def make_tree(self,parent,columns,headings):
        frame=ttk.Frame(parent);frame.pack(fill='both',expand=True)
        tree=ttk.Treeview(frame,columns=columns,show='headings',selectmode='browse',height=3 if self.compact else 10)
        for column,title in zip(columns,headings):tree.heading(column,text=title);tree.column(column,width=280,minwidth=100,stretch=True)
        scroll=ttk.Scrollbar(frame,orient='vertical',command=tree.yview);tree.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');tree.pack(side='left',fill='both',expand=True);return tree

    def refresh(self,selected=None):
        if self.is_busy():return
        old=self.selected() if hasattr(self,'rows') else None
        selected=Path(selected) if selected else old['path'] if old else None
        prior=self.previews[self.combo.current()] if hasattr(self,'previews') and 0<=self.combo.current()<len(self.previews) else None
        self.refreshing=self.compact
        self.rows={};self.deleted={};self.previews=[];self.combo.configure(values=());self.preview_name.set('');self.info.set('결과를 선택하세요.')
        self.tree.delete(*self.tree.get_children());self.trash_tree.delete(*self.trash_tree.get_children())
        try:
            for i,row in enumerate(list_results(self.root)):
                key=str(i);self.rows[key]=row;self.tree.insert('', 'end',iid=key,values=(row['name'],))
            if self.root.exists():
                for i,row in enumerate(list_trash(self.root)):
                    key=str(i);self.deleted[key]=row;self.trash_tree.insert('','end',iid=key,values=(row['original_name'],))
        except (OSError,ValueError) as error:messagebox.showerror('결과 목록',str(error),parent=self.window)
        for key,row in self.rows.items():
            if row['path']==selected:
                self.tree.selection_set(key);self.select(load=False)
                if prior in self.previews:self.combo.current(self.previews.index(prior))
                break
        self.window.after_idle(lambda:setattr(self,'refreshing',False))

    def selected(self):
        keys=self.tree.selection();return self.rows.get(keys[0]) if keys else None

    def select(self,load=True):
        if self.is_busy():return
        row=self.selected()
        self.info.set(f"{row['name']}\n{row['status']} · {row['frames']} 프레임\n{datetime.fromtimestamp(row['modified']).strftime('%Y-%m-%d %H:%M')}" if row else '결과를 선택하세요.')
        try:self.previews=[] if row is None else list_previews(self.root,row['path'])
        except (OSError,ValueError) as error:self.previews=[];messagebox.showerror('미리보기',str(error),parent=self.window)
        if self.compact:self.previews=[p for p in self.previews if p.name in ('overlay.mp4','preview3d.mp4','model-comparison.mp4') or p.name.startswith('model-preview')]
        names=[str(p.relative_to(row['path'])) for p in self.previews] if row else []
        self.combo.configure(values=names);self.preview_name.set(names[0] if names else '')
        if self.compact and load and self.previews:self.preview()

    def preview(self):
        if self.is_busy():return
        row=self.selected();index=self.combo.current()
        if row and 0<=index<len(self.previews):self.on_preview(row['path'],self.previews[index])

    def set_busy(self,busy):
        for widget in (self.preview_button,self.delete_button,self.restore_button,self.refresh_button):
            if widget is not None:widget.configure(state='disabled' if busy else 'normal')
        self.combo.configure(state='disabled' if busy else 'readonly')

    def delete(self):
        if self.is_busy():return
        row=self.selected()
        if not row:return
        if not messagebox.askyesno('결과 삭제',f'{row["name"]}\n\n이 결과 폴더와 모든 하위 파일을 프로그램 휴지통으로 옮길까요?',parent=self.window):return
        try:self.before_delete(row['path']);trash_result(self.root,row['path']);self.refresh()
        except (OSError,ValueError) as error:messagebox.showerror('삭제 실패',str(error),parent=self.window)

    def restore(self):
        if self.is_busy():return
        keys=self.trash_tree.selection()
        if not keys:return
        try:restore_result(self.root,self.deleted[keys[0]]['path']);self.refresh()
        except (OSError,ValueError) as error:messagebox.showerror('복원 실패',str(error),parent=self.window)
