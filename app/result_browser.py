"""Read-only previews and explicit reversible deletion of output folders."""
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk,messagebox
from app.result_library import list_results,list_previews,trash_result,list_trash,restore_result

class ResultBrowser:
    def __init__(self,parent,root,on_preview,before_delete,is_busy=lambda:False):
        self.root=Path(root);self.on_preview=on_preview;self.before_delete=before_delete;self.is_busy=is_busy
        self.window=ttk.Frame(parent,width=340,padding=(10,0,0,0))
        ttk.Label(self.window,text='출력 결과',font=('맑은 고딕',11,'bold')).pack(anchor='w',pady=(0,8))
        self.tabs=ttk.Notebook(self.window);self.tabs.pack(fill='both',expand=True)
        active=ttk.Frame(self.tabs);deleted=ttk.Frame(self.tabs);self.tabs.add(active,text='결과');self.tabs.add(deleted,text='프로그램 휴지통')
        self.tree=self.make_tree(active,('name',),('결과 폴더',))
        self.trash_tree=self.make_tree(deleted,('name',),('원래 결과 이름',))
        self.tree.bind('<<TreeviewSelect>>',lambda e:self.select());self.tree.bind('<Double-1>',lambda e:self.preview())
        self.info=tk.StringVar(value='결과를 선택하세요.')
        ttk.Label(active,textvariable=self.info,wraplength=300).pack(fill='x',pady=5)
        self.preview_name=tk.StringVar()
        self.combo=ttk.Combobox(active,textvariable=self.preview_name,state='readonly',width=28);self.combo.pack(fill='x',pady=5)
        self.combo.bind('<<ComboboxSelected>>',lambda e:self.preview())
        row=ttk.Frame(active);row.pack(fill='x',pady=5)
        self.preview_button=ttk.Button(row,text='미리보기',command=self.preview);self.preview_button.pack(side='left')
        self.delete_button=ttk.Button(row,text='결과 삭제',command=self.delete);self.delete_button.pack(side='right')
        self.restore_button=ttk.Button(deleted,text='선택 결과 복원',command=self.restore);self.restore_button.pack(pady=8)
        ttk.Label(self.window,text='삭제한 결과는 프로그램 휴지통에서 복원할 수 있습니다.',wraplength=300).pack(fill='x',pady=5)
        self.refresh_button=ttk.Button(self.window,text='새로고침',command=self.refresh);self.refresh_button.pack(anchor='e',pady=5)
        self.refresh()

    def make_tree(self,parent,columns,headings):
        frame=ttk.Frame(parent);frame.pack(fill='both',expand=True)
        tree=ttk.Treeview(frame,columns=columns,show='headings',selectmode='browse')
        for column,title in zip(columns,headings):tree.heading(column,text=title);tree.column(column,width=280,minwidth=100,stretch=True)
        scroll=ttk.Scrollbar(frame,orient='vertical',command=tree.yview);tree.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');tree.pack(side='left',fill='both',expand=True);return tree

    def refresh(self):
        if self.is_busy():return
        self.rows={};self.deleted={};self.previews=[];self.combo.configure(values=());self.preview_name.set('');self.info.set('결과를 선택하세요.')
        self.tree.delete(*self.tree.get_children());self.trash_tree.delete(*self.trash_tree.get_children())
        try:
            for i,row in enumerate(list_results(self.root)):
                key=str(i);self.rows[key]=row;self.tree.insert('', 'end',iid=key,values=(row['name'],))
            if self.root.exists():
                for i,row in enumerate(list_trash(self.root)):
                    key=str(i);self.deleted[key]=row;self.trash_tree.insert('','end',iid=key,values=(row['original_name'],))
        except (OSError,ValueError) as error:messagebox.showerror('결과 목록',str(error),parent=self.window)

    def selected(self):
        keys=self.tree.selection();return self.rows.get(keys[0]) if keys else None

    def select(self):
        if self.is_busy():return
        row=self.selected()
        self.info.set(f"{row['name']}\n{row['status']} · {row['frames']} 프레임\n{datetime.fromtimestamp(row['modified']).strftime('%Y-%m-%d %H:%M')}" if row else '결과를 선택하세요.')
        try:self.previews=[] if row is None else list_previews(self.root,row['path'])
        except (OSError,ValueError) as error:self.previews=[];messagebox.showerror('미리보기',str(error),parent=self.window)
        names=[str(p.relative_to(row['path'])) for p in self.previews] if row else []
        self.combo.configure(values=names);self.preview_name.set(names[0] if names else '')

    def preview(self):
        if self.is_busy():return
        row=self.selected();index=self.combo.current()
        if row and 0<=index<len(self.previews):self.on_preview(row['path'],self.previews[index])

    def set_busy(self,busy):
        for widget in (self.preview_button,self.delete_button,self.restore_button,self.refresh_button):widget.configure(state='disabled' if busy else 'normal')
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
