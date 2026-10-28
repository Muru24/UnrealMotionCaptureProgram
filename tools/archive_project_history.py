"""Create and verify a history backup. Never delete or move original files."""
import hashlib,json,os,sys,zipfile
from pathlib import Path
from datetime import datetime

HISTORY=('진행상황','MVP요약','계획서 수정','validation','transfer','HOME_TRANSFER.md','md','README.md',
         '.validation/sam3d/cpu_env','.validation/sam3d/source_cpu','.validation/sam3d/source_minimal')
EXISTING=('snapshots','.validation/sam3d/wheels')
KEEP=tuple('validation/sam2/'+n+'.py' for n in ('candidate_geometry','candidate_ranking','knee_anchors','shoe_leg_geometry','leg_flow_guard','boot_evidence','temporal_leg_path'))

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def files(path,root):
    path=Path(path)
    if path.is_symlink():raise ValueError('Linked archive source: '+str(path))
    if not path.exists():return
    if getattr(path.lstat(),'st_file_attributes',0)&0x400:raise ValueError('Linked archive source: '+str(path))
    if not path.resolve().is_relative_to(root):raise ValueError('Archive source escapes project')
    if path.is_file():yield path;return
    if path.is_dir():
        for parent,dirs,names in os.walk(path,followlinks=False):
            for name in dirs+names:
                child=Path(parent)/name
                if child.is_symlink() or getattr(child.lstat(),'st_file_attributes',0)&0x400:raise ValueError('Linked archive entry: '+str(child))
            for name in names:yield Path(parent)/name

def archive(root,destination):
    root=Path(root).resolve();destination=Path(destination).resolve()
    if destination==root or destination.is_relative_to(root):raise ValueError('Archive must be outside project')
    if destination.exists() and any(destination.iterdir()):raise FileExistsError(destination)
    destination.mkdir(parents=True,exist_ok=True)
    items={str(p.relative_to(root)).replace('\\','/'):p for relative in HISTORY for p in files(root/relative,root)}
    manifest={'project':str(root),'created':datetime.now().isoformat(),'compressed_files':{},'existing_archive_inventory':{},
        'required_validation_sources':list(KEEP),'originals_changed':False,'status':'writing'}
    bundle=destination/'history-and-validation.zip'
    with zipfile.ZipFile(bundle,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
        for i,(name,path) in enumerate(sorted(items.items())):
            before=path.stat();h=hashlib.sha256();count=0
            with path.open('rb') as src,z.open(name,'w',force_zip64=True) as dst:
                for block in iter(lambda:src.read(1024*1024),b''):dst.write(block);h.update(block);count+=len(block)
            after=path.stat()
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or count!=before.st_size:raise RuntimeError('Archive input changed: '+name)
            manifest['compressed_files'][name]={'bytes':count,'sha256':h.hexdigest()}
            if i%1000==0:print('ARCHIVE_WRITE',i,len(items),flush=True)
    with zipfile.ZipFile(bundle) as z:
        if set(z.namelist())!=set(items):raise RuntimeError('Archive file list differs')
        for i,(name,row) in enumerate(manifest['compressed_files'].items()):
            h=hashlib.sha256()
            with z.open(name) as src:
                for block in iter(lambda:src.read(1024*1024),b''):h.update(block)
            if h.hexdigest()!=row['sha256'] or z.getinfo(name).file_size!=row['bytes']:raise RuntimeError('Archive verification failed: '+name)
            if i%1000==0:print('ARCHIVE_VERIFIED',i,len(items),flush=True)
    manifest['bundle_sha256']=digest(bundle);manifest['bundle_bytes']=bundle.stat().st_size
    for relative in EXISTING:
        sources=list(files(root/relative,root))
        for i,path in enumerate(sources):
            name=str(path.relative_to(root)).replace('\\','/');manifest['existing_archive_inventory'][name]={'bytes':path.stat().st_size,'sha256':digest(path)}
            if i%20==0:print('EXISTING_ARCHIVE_CHECKSUM',relative,i,len(sources),flush=True)
    manifest['status']='verified_backup';(destination/'archive-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('BACKUP_VERIFIED_ORIGINALS_RETAINED',destination,flush=True);return manifest

if __name__=='__main__':archive(*sys.argv[1:])
