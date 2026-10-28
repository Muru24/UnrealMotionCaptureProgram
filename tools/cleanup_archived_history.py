"""Apply an explicitly approved cleanup, only against verified archive manifest entries."""
import argparse,json,shutil
from pathlib import Path
from tools.archive_project_history import digest,files,KEEP,EXISTING

REMOVE=('진행상황','MVP요약','계획서 수정','validation','transfer','HOME_TRANSFER.md',
        '.validation/sam3d/cpu_env','.validation/sam3d/source_cpu','.validation/sam3d/source_minimal')

def cleanup(root,archive,apply=False):
    root,archive=Path(root).resolve(),Path(archive).resolve()
    if archive.is_relative_to(root):raise ValueError('Archive must be outside project')
    manifest=json.loads((archive/'archive-manifest.json').read_text(encoding='utf-8'))
    if Path(manifest['project']).resolve()!=root or manifest['status']!='verified_backup':raise ValueError('Wrong/unverified archive')
    if not apply:return {'remove_after_backup':REMOVE,'move_existing_archives':EXISTING}
    if digest(archive/'history-and-validation.zip')!=manifest['bundle_sha256']:raise ValueError('Backup archive changed')
    for extra in manifest.get('supplemental_archives',[]):
        path=archive/extra['file']
        if path.parent!=archive or digest(path)!=extra['sha256']:raise ValueError('Supplemental backup changed')
    targets=[];retained={};removed_bytes=0;moved_bytes=0
    for relative in REMOVE:
        target=root/relative
        if not target.exists():continue
        if not target.resolve().is_relative_to(root) or str(target.relative_to(root)).replace('\\','/')!=relative:raise ValueError('Invalid cleanup path')
        entries=list(files(target,root));actual={str(p.relative_to(root)).replace('\\','/') for p in entries}
        expected={n for n in manifest['compressed_files'] if n==relative or n.startswith(relative+'/')}
        if actual!=expected:raise ValueError('Original file list changed: '+relative)
        for path in entries:
            name=str(path.relative_to(root)).replace('\\','/');row=manifest['compressed_files'][name]
            if path.stat().st_size!=row['bytes'] or digest(path)!=row['sha256']:raise ValueError('Original changed: '+name)
            if name in KEEP:retained[name]=path.read_bytes()
            removed_bytes+=row['bytes']
        targets.append(target)
        print('CLEANUP_VERIFIED',relative,len(entries),flush=True)
    # All delete targets are absolute, bounded, manifest-matched and backed up.
    for target in targets:
        if not target.resolve().is_relative_to(root):raise ValueError('Cleanup escaped project')
        if target.is_dir():shutil.rmtree(target)
        else:target.unlink()
    for name,data in retained.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    for relative in EXISTING:
        source=root/relative
        if not source.exists():continue
        if not source.resolve().is_relative_to(root) or source.stat().st_dev!=archive.stat().st_dev:raise ValueError('Move must stay on verified project volume')
        items=list(files(source,root));names={str(p.relative_to(root)).replace('\\','/') for p in items}
        expected={n for n in manifest['existing_archive_inventory'] if n==relative or n.startswith(relative+'/')}
        if names!=expected:raise ValueError('Existing archive inventory changed')
        identities={}
        for i,path in enumerate(items):
            name=str(path.relative_to(root)).replace('\\','/');row=manifest['existing_archive_inventory'][name];stat=path.stat()
            if stat.st_size!=row['bytes'] or digest(path)!=row['sha256']:raise ValueError('Existing archive changed: '+name)
            identities[name]=(stat.st_ino,stat.st_size);moved_bytes+=stat.st_size
            if i%20==0:print('MOVE_VERIFIED',relative,i,len(items),flush=True)
        target=archive/'existing-archives'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():raise FileExistsError(target)
        source.rename(target)
        for name,identity in identities.items():
            stat=(archive/'existing-archives'/name).stat()
            if (stat.st_ino,stat.st_size)!=identity:raise RuntimeError('Archive move changed file identity')
    result={'status':'completed','archived_original_bytes_removed':removed_bytes,'existing_archive_bytes_moved':moved_bytes,
        'runtime_preserved':['.venv','.validation/sam3d/env','models','assets','outputs'],'retained_validation_sources':list(retained)}
    (archive/'cleanup-complete.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CLEANUP_COMPLETE',json.dumps(result,ensure_ascii=True),flush=True);return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('archive');parser.add_argument('--apply',action='store_true');args=parser.parse_args();print(cleanup(args.root,args.archive,args.apply))
