"""Bounded output discovery and reversible moves to a program-owned trash."""
from pathlib import Path
from uuid import uuid4
from datetime import datetime,timezone
import json,os,stat

def linked(path):
    p=Path(path)
    return p.is_symlink() or (os.name=='nt' and bool(p.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT))

def root_path(root):
    p=Path(root).absolute()
    if not p.is_dir() or linked(p):raise ValueError('일반 출력 폴더를 선택하세요.')
    return p.resolve(strict=True)

def checked_result(root,path):
    root=root_path(root);p=Path(path).absolute()
    if p.parent!=root or p.name.startswith('.') or not p.is_dir() or linked(p) or p.resolve(strict=True).parent!=root:
        raise ValueError('출력 폴더 바로 아래의 일반 결과 폴더만 처리할 수 있습니다.')
    return p

def read_small(path):
    if linked(path) or path.stat().st_size>2*1024*1024:raise ValueError('리포트를 읽을 수 없습니다.')
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,dict):raise ValueError('리포트 형식이 올바르지 않습니다.')
    return data

def list_results(root):
    if not Path(root).exists():return []
    root=root_path(root);results=[]
    for p in root.iterdir():
        if p.name.startswith('.') or not p.is_dir() or linked(p):continue
        info={};status='리포트 없음'
        try:info=read_small(p/'report.json');status=info.get('status','알 수 없음')
        except (OSError,ValueError,TypeError):pass
        results.append({'path':p,'name':p.name,'status':status,'modified':p.stat().st_mtime,'frames':info.get('frames_processed',info.get('frames_written',''))})
    return sorted(results,key=lambda r:r['modified'],reverse=True)

def list_previews(root,path):
    path=checked_result(root,path);found=[]
    # Search only three directory levels; never traverse symlinks/junctions.
    def scan(folder,depth):
        for p in folder.iterdir():
            if linked(p):continue
            if p.is_file() and p.suffix.lower()=='.mp4':found.append(p)
            elif depth and p.is_dir():scan(p,depth-1)
    scan(path,2)
    priority={'reconnection-overlay.mp4':-1,'part-overlay.mp4':0,'leg-overlay.mp4':1,'candidate-overlay.mp4':2,'overlay.mp4':3,'preview3d.mp4':4}
    return sorted(found,key=lambda p:(priority.get(p.name,9),-p.stat().st_mtime,str(p)))

def assert_no_links(folder):
    for parent,dirs,files in os.walk(folder,followlinks=False):
        for name in dirs+files:
            if linked(Path(parent)/name):raise ValueError('연결 파일이나 junction이 포함된 결과는 이동하지 않습니다.')

def trash_result(root,path):
    root=root_path(root);source=checked_result(root,path);assert_no_links(source)
    trash=root/'.trash'
    if trash.exists() and linked(trash):raise ValueError('프로그램 휴지통 경로가 올바르지 않습니다.')
    trash.mkdir(exist_ok=True)
    entry=trash/uuid4().hex;entry.mkdir();destination=entry/'result'
    # Verify both resolved absolute parents before a directory move on Windows.
    if source.resolve(strict=True).parent!=root or destination.parent.resolve(strict=True).parent!=trash.resolve(strict=True):raise ValueError('허용 범위를 벗어난 이동입니다.')
    metadata={'schema':'output_trash_v1','original_name':source.name,'deleted_utc':datetime.now(timezone.utc).isoformat()}
    (entry/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    source.rename(destination)
    return entry

def list_trash(root):
    root=root_path(root);trash=root/'.trash'
    if not trash.is_dir() or linked(trash):return []
    rows=[]
    for entry in trash.iterdir():
        try:
            if not entry.is_dir() or linked(entry):continue
            data=read_small(entry/'metadata.json');payload=entry/'result'
            if data.get('schema')=='output_trash_v1' and isinstance(data.get('original_name'),str) and isinstance(data.get('deleted_utc'),str) and payload.is_dir() and not linked(payload):rows.append({**data,'path':entry})
        except (OSError,ValueError,TypeError):pass
    return sorted(rows,key=lambda r:r['deleted_utc'],reverse=True)

def restore_result(root,entry):
    root=root_path(root);trash=root/'.trash';entry=Path(entry).absolute()
    if not trash.is_dir() or linked(trash) or entry.parent!=trash or linked(entry) or not entry.is_dir() or entry.resolve(strict=True).parent!=trash.resolve(strict=True):raise ValueError('유효한 프로그램 휴지통 항목이 아닙니다.')
    data=read_small(entry/'metadata.json');name=data.get('original_name','')
    if data.get('schema')!='output_trash_v1':raise ValueError('휴지통 형식이 올바르지 않습니다.')
    if not isinstance(name,str) or not name or name.startswith('.') or Path(name).name!=name or '/' in name or '\\' in name:raise ValueError('복원 이름이 올바르지 않습니다.')
    target=root/name;source=entry/'result'
    if target.exists() or target.is_symlink():raise ValueError('동일한 이름의 결과가 있어 복원하지 않았습니다.')
    if not source.is_dir() or linked(source):raise ValueError('복원할 결과가 없습니다.')
    assert_no_links(source)
    if target.parent.resolve(strict=True)!=root or source.resolve(strict=True).parent!=entry.resolve(strict=True):raise ValueError('복원 범위를 벗어났습니다.')
    source.rename(target)
    return target
