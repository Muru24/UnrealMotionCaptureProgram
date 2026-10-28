"""One finalized model per extraction and atomic, non-destructive delivery export."""
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import hashlib,json,math,re,shutil,uuid
from app.model_preview import describe,metadata
from app.animation_edit_job import edit_source


@dataclass(frozen=True)
class FinalResult:
    root:Path
    preview:Path
    blend:Path
    fbx:Path|None
    label:str
    edited:bool
    frames:int
    fps:float


def read(path):
    if path.is_symlink() or path.stat().st_size>2*1024*1024:raise ValueError('Invalid result report')
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,dict):raise ValueError('Invalid result report')
    return data


def list_final_results(root):
    from app.result_library import list_results,linked
    found=[]
    def scan(folder,owner,depth=2):
        for path in folder.iterdir():
            if path.name.startswith('model-preview') and path.suffix=='.mp4':
                item=describe(path)
                if item:found.append((owner,item))
            elif depth and path.name.startswith(('model-','edit-')) and path.is_dir() and not linked(path):scan(path,owner,depth-1)
    for record in list_results(root):
        try:scan(record['path'],record['path'])
        except OSError:continue
    rows={}
    for folder,item in found:
        if item.legacy:continue
        try:
            info=metadata(item.path);blend=edit_source(item.path)
            edited=(item.path.parent/'edit-report.json').is_file()
            marker=item.path.parent/'edit-report.json' if edited else item.path.parent/'delivery.json'
            if not marker.is_file():marker=blend.parent/'hand-stability.json'
            report=read(marker)
            if report.get('status')!='completed':continue
            frames=int(info['frames']);fps=float(info['fps'])
            if frames<1 or not math.isfinite(fps) or fps<=0 or report.get('frames',frames)!=frames:continue
            fbx=item.path.parent/('Edited_Manny.fbx' if edited else 'Manny_Animation.fbx')
            if (item.path.parent/'Model_Animation.fbx').is_file():fbx=item.path.parent/'Model_Animation.fbx'
            source=item.source.stem if item.source else folder.name
            row=FinalResult(folder,item.path,blend,fbx if fbx.is_file() else None,source,edited,frames,fps)
            key=(edited,item.path.stat().st_mtime_ns)
            if folder not in rows or key>rows[folder][0]:rows[folder]=(key,row)
        except (OSError,ValueError,KeyError,TypeError):continue
    return sorted((row for _,row in rows.values()),key=lambda row:row.preview.stat().st_mtime_ns,reverse=True)


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(2*1024*1024),b''):h.update(block)
    return h.hexdigest()


def export_final(row,destination,formats,cancelled=lambda:False,progress=lambda *args:None):
    formats=set(formats)
    if not formats or formats-{'blend','fbx','mp4'}:raise ValueError('내보낼 형식을 선택하세요.')
    if cancelled():raise KeyboardInterrupt
    destination=Path(destination).resolve()
    if not destination.is_dir():raise ValueError('저장할 폴더를 선택하세요.')
    sources={'blend':row.blend,'mp4':row.preview,'fbx':row.fbx}
    if 'fbx' in formats and row.fbx is None:
        from app.builtin_models import blender_job
        cache=row.root/'.final-export-cache'/uuid.uuid4().hex;cache.mkdir(parents=True)
        blender_job('export_model_animation.py',[row.blend,cache],cache/'export.log',cancelled)
        sources['fbx']=cache/'Manny_Animation.fbx'
    for kind in formats:
        source=sources[kind]
        if source is None or not source.is_file() or source.is_symlink():raise ValueError('최종 파일이 없거나 유효하지 않습니다: '+kind)
    label=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',row.label)[:60].strip(' .') or 'Motion'
    out=destination/(label+'_Final_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    pending=destination/('.motion-export-'+uuid.uuid4().hex);pending.mkdir()
    stem='Model_Animation' if (metadata(row.preview) or {}).get('model_id','unreal_manny')!='unreal_manny' else 'Manny_Animation'
    names={'blend':stem+'.blend','fbx':stem+'.fbx','mp4':'model-preview.mp4'};files={}
    try:
        for i,kind in enumerate(sorted(formats)):
            if cancelled():raise KeyboardInterrupt
            progress(i,len(formats));source=sources[kind];before=digest(source);target=pending/names[kind]
            with source.open('rb') as reader,target.open('xb') as writer:
                while True:
                    if cancelled():raise KeyboardInterrupt
                    chunk=reader.read(2*1024*1024)
                    if not chunk:break
                    writer.write(chunk)
            if digest(target)!=before or digest(source)!=before:raise ValueError('내보내는 동안 원본이 변경되었습니다.')
            files[names[kind]]=before
        if cancelled():raise KeyboardInterrupt
        (pending/'export-info.json').write_text(json.dumps({'schema':'motion_final_export_v1','status':'completed',
            'name':row.label,'frames':row.frames,'fps':row.fps,'edited':row.edited,'files_sha256':files},ensure_ascii=False,indent=2),encoding='utf-8')
        pending.rename(out);progress(len(formats),len(formats));return out
    except BaseException:
        # This directory was exclusively created above; never delete a source or an existing export.
        if pending.exists() and pending.parent.resolve()==destination and pending.name.startswith('.motion-export-'):
            shutil.rmtree(pending)
        raise
