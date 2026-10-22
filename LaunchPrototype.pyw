"""Windowed entry point; StartPrototype.cmd selects the project venv."""
from pathlib import Path
import logging
import sys
import traceback

root=Path(__file__).resolve().parent
log=root/'outputs'/'prototype.log'
log.parent.mkdir(parents=True,exist_ok=True)
with log.open('a',encoding='utf-8') as stream:
    original_stdout,original_stderr=sys.stdout,sys.stderr
    sys.stdout=sys.stderr=stream
    logging.basicConfig(stream=stream,level=logging.WARNING)
    try:
        from app.gui import main
        main()
    except Exception:
        traceback.print_exc(file=stream)
        stream.flush()
        import tkinter as tk
        from tkinter import messagebox
        window=tk.Tk();window.withdraw()
        messagebox.showerror('실행 오류',f'프로그램을 시작하지 못했습니다.\n프로젝트 가상환경과 requirements.lock을 확인하세요.\n\n로그: {log}')
        window.destroy()
    finally:
        sys.stdout,sys.stderr=original_stdout,original_stderr
