from tkinterdnd2 import TkinterDnD
from tkinter import ttk
from app.gui import PrototypeApp
root=TkinterDnD.Tk();root.withdraw();app=PrototypeApp(root)
try:
    style=ttk.Style(root)
    for name,option,state,expected in (
        ('Treeview','fieldbackground',(),'#1b2637'),
        ('Treeview','foreground',(),'#e6edf6'),
        ('Treeview','background',('selected',),'#3478eb'),
        ('Treeview.Heading','background',(),'#293b52'),
        ('TNotebook.Tab','background',('selected',),'#293b52'),
        ('Vertical.TScrollbar','troughcolor',(),'#101722'),
    ):
        actual=style.lookup(name,option,state)
        assert actual==expected,(name,option,actual)
    assert app.result_panel.window.winfo_exists()
    print('Dark palette runtime smoke PASS (6 states, panel creation)')
finally:app.close()
