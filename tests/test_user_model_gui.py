import time
from tests.test_user_models import publish


def test_add_model_button_imports_selects_and_obeys_busy_guard(tmp_path,monkeypatch):
    from tkinterdnd2 import TkinterDnD
    import app.user_models as users
    import app.gui as gui
    monkeypatch.setattr(users,'ROOT',tmp_path)
    chosen=tmp_path/'Hero.fbx';chosen.write_bytes(b'model')
    calls=[]
    monkeypatch.setattr(gui.filedialog,'askopenfilename',lambda **kw:str(chosen))
    def imported(source,cancelled,progress):
        assert not cancelled();calls.append(source)
        publish(tmp_path,'user_hero','Hero');users.select('user_hero')
        progress(3,3);return 'user_hero'
    monkeypatch.setattr(users,'import_model',imported)
    root=TkinterDnD.Tk();app=gui.PrototypeApp(root);app.studio.editor.auto_load=False
    try:
        app.studio.show_stage(2);root.update()
        assert app.studio.add_model_button.winfo_ismapped()
        app.studio.add_model_button.invoke()
        assert app.busy
        app.add_user_model();assert len(calls)<=1
        deadline=time.monotonic()+8
        while app.busy and time.monotonic()<deadline:root.update();time.sleep(.01)
        assert not app.busy and calls==[str(chosen)]
        assert app.studio.selected_builtin()=='user_hero'
        assert '52' in app.studio.builtin_status.get() and '30' in app.studio.builtin_status.get()
        assert app.studio.add_model_button.winfo_ismapped()
        assert str(app.studio.model_box.cget('state'))=='readonly'
    finally:
        app.studio.final_panel.clear();app.stop_video();root.destroy()
