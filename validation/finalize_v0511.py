from pathlib import Path
import json,hashlib,shutil,zipfile,re
root=Path(__file__).resolve().parents[1]
cases=root/'진행상황';number=max(int(p.name[4:]) for p in cases.iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=cases/f'case{number}';case.mkdir()
note=f'''## 2026-10-19 / v0.5.11 결과 패널 다크 색상 통일

증상: 새 결과 패널의 목록·탭·스크롤 영역에 기본 clam 밝은 색상이 남아 글자가 잘 보이지 않았다. 원인: 기존 공통 스타일만 설정했고 Treeview의 fieldbackground 및 Notebook/Scrollbar 전용 상태 색상을 지정하지 않았다.
조치: 목록 배경 #1b2637/글자 #e6edf6, 헤더·선택 탭 #293b52, 선택 행 #3478eb/흰 글자, 스크롤 홈과 패널 경계는 기존 화면의 #101722 계열로 통일했다. hover/선택 상태와 스크롤 손잡이·화살표 색상도 지정했다. 기능/파일 처리 동작은 변경하지 않았다.
검증: validation/check_v0511.py 실제 Tk 생성 및 스타일 lookup 6개 상태 PASS. 시각 변경이라 새 단위 테스트 및 GPU 추론은 실행하지 않았다. 사용자 출력 삭제 없음. 4MD 원본과 case{number} 해시 일치 복사, v0.5.11 MVP 저장. M2 품질 상태는 진행 중 유지.

'''
for name in ('CURRENT_TASK.md','PROGRESS.md','ISSUES.md','PROJECT.md'):
    p=root/'md'/name;p.write_text(note+'---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8');shutil.copyfile(p,case/name)
    assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((case/name).read_bytes()).digest()
p=root/'README.md';p.write_text(p.read_text(encoding='utf-8').replace('현재 작업 버전은 v0.5.10','현재 작업 버전은 v0.5.11'),encoding='utf-8')
p=root/'HOME_TRANSFER.md';p.write_text('# 최신 버전 v0.5.11\n\n결과 패널 목록·탭·스크롤·선택 색상을 기존 다크 테마로 통일. StartPrototype.cmd 재시작. 최신 MD 및 v0.5.11 MVP 참고.\n\n---\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
folder=root/'snapshots/v0.5.11 MVP';folder.mkdir();target=folder/'m2-dark-panel-v0.5.11.zip'
extra=[Path(__file__),root/'validation/check_v0511.py',*case.glob('*.md')]
with zipfile.ZipFile(root/'snapshots/v0.5.10 MVP/m2-result-panel-v0.5.10.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as out:
    names=set()
    for info in old.infolist():
        name=info.filename
        if '__pycache__' in name or name.endswith('.pyc'):continue
        p=root/name;out.writestr(name,p.read_bytes() if p.is_file() else old.read(info));names.add(name)
    for p in extra:
        name=p.relative_to(root).as_posix()
        if name not in names:out.write(p,name)
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    assert z.read('app/gui.py')==(root/'app/gui.py').read_bytes()
    count=len(z.infolist())
data={'version':'0.5.11','files':count,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'runtime_style_smoke':'PASS','md_archive':case.name,'m2_pass':False}
(folder/'snapshot.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(data))
