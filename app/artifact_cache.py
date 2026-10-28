"""Reuse only completed, content-verified exports inside the owning result folder."""
import hashlib,json,uuid
from pathlib import Path
from app.knee_job import digest

def identity(executable):
    path=Path(executable)
    return [str(path.resolve()),path.stat().st_size,path.stat().st_mtime_ns] if path.is_file() else str(executable)

def index_path(root,kind,signature):
    key=hashlib.sha256(json.dumps(signature,sort_keys=True,ensure_ascii=True).encode()).hexdigest()
    return Path(root)/'.export-cache'/f'{kind}-{key}.json'

def lookup(root,kind,signature,cancelled=lambda:False):
    root=Path(root).resolve();index=index_path(root,kind,signature)
    try:
        if index.is_symlink() or index.parent.is_symlink() or index.stat().st_size>32768:return None
        entry=json.loads(index.read_text(encoding='utf-8'))
        if entry.get('signature')!=signature or not entry.get('files') or entry.get('result') not in entry['files']:return None
        for name,value in entry['files'].items():
            if cancelled():raise KeyboardInterrupt
            path=root/name
            if path.is_symlink() or path.parent.is_symlink() or not path.resolve().is_relative_to(root):return None
            if digest(path)!=value:return None
        result=root/entry['result']
        return result if result.resolve().is_relative_to(root) and result.is_file() else None
    except (OSError,ValueError,KeyError,TypeError):return None

def publish(root,kind,signature,result,names):
    root=Path(root).resolve();result=Path(result).resolve()
    if not result.is_relative_to(root):raise ValueError('Export cache escapes result folder')
    files={str((result.parent/name).relative_to(root)):digest(result.parent/name) for name in names}
    index=index_path(root,kind,signature);index.parent.mkdir(exist_ok=True)
    temporary=index.with_name('.'+uuid.uuid4().hex)
    temporary.write_text(json.dumps({'signature':signature,'result':str(result.relative_to(root)),'files':files},sort_keys=True),encoding='utf-8')
    temporary.replace(index)
