from pathlib import Path
import json,hashlib,shutil,zipfile,re
ROOT=Path(__file__).resolve().parents[1]
cases=ROOT/'진행상황';n=max(int(p.name[4:]) for p in cases.iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=cases/f'case{n}';case.mkdir()
note=f'''## 2026-10-19 / v0.5.10 미리보기 옆 결과 패널

사용자 요청으로 결과 목록 버튼과 별도 모달 창을 제거하고 미리보기 오른쪽에 상시 결과 패널을 배치했다. Panedwindow 경계를 드래그해 미리보기와 목록 폭을 조절한다. 결과/프로그램 휴지통 탭, 결과 상세 상태, 하위 영상 선택, 미리보기, 삭제/복원/새로고침을 패널 안에서 제공한다. 결과를 선택한 뒤 미리보기 또는 더블클릭으로 열며 하위 영상 선택 변경도 바로 재생 화면에 반영한다. 추론을 재실행하지 않는다. 창 기본 1400x850/최소1200x700. 작업 종료 시 자동 목록 갱신, 작업 중 재생 전환/삭제/복원/갱신 차단. 파일 이동 검증 및 프로그램 휴지통 규칙은 v0.5.9 그대로다.
검증: 관련 8 PASS(파일 관리 3, 패널 통합 GUI 1, 기존 GUI 회귀 4). Tk GUI는 각 별도 프로세스로 검증했다. 실제 사용자 출력 삭제 없음, 새 GPU 추론 없음. 테스트는 패널의 메인 Panedwindow 소속/버튼 제거, 재생 후 패널 유지, 작업 중 삭제 비활성화, 재생 핸들 해제 후 삭제/복원과 기존 자동 처리·취소·입력 동작을 확인한다. 전체 비GUI 회귀는 직전 v0.5.9의 365 PASS/1 SKIP이며 이번에는 관련 검사만 실행했다.
원본4MD 및 case{n} SHA 동일 복사, snapshots/v0.5.10 MVP 저장. 이전 MVP 및 HOME ZIP 유지. M2 진행 중이며 망토·회전 관절 오추정은 이번 UI 변경에서 수정하지 않았다.

'''
for name in ('CURRENT_TASK.md','PROGRESS.md','ISSUES.md','PROJECT.md'):
    p=ROOT/'md'/name;p.write_text(note+'---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8');shutil.copyfile(p,case/name)
    assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((case/name).read_bytes()).digest()
p=ROOT/'README.md';s=p.read_text(encoding='utf-8').replace('현재 작업 버전은 v0.5.9','현재 작업 버전은 v0.5.10').replace('하단 ‘결과 목록’에서','미리보기 오른쪽 결과 패널에서');p.write_text(s,encoding='utf-8')
p=ROOT/'HOME_TRANSFER.md';p.write_text('# 최신 버전 v0.5.10\n\n미리보기 오른쪽 상시 결과 패널 추가. 기존 결과 목록 버튼/별도 창 제거. 패널에서 조회·미리보기·삭제·복원. StartPrototype.cmd 재시작. 최신4MD와 case'+str(n)+' 및 v0.5.10 MVP 참고.\n\n---\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
folder=ROOT/'snapshots/v0.5.10 MVP';folder.mkdir();target=folder/'m2-result-panel-v0.5.10.zip'
old=ROOT/'snapshots/v0.5.9 MVP/m2-result-library-v0.5.9.zip'
extra=[Path(__file__),*case.glob('*.md')]
with zipfile.ZipFile(old) as source,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as out:
    names=set()
    for info in source.infolist():
        name=info.filename
        if '__pycache__' in name or name.endswith('.pyc'):continue
        p=ROOT/name;out.writestr(name,p.read_bytes() if p.is_file() else source.read(info));names.add(name)
    for p in extra:
        name=p.relative_to(ROOT).as_posix()
        if name not in names:out.write(p,name)
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    for name in ('app/gui.py','app/result_browser.py','tests/test_result_library.py'):assert z.read(name)==(ROOT/name).read_bytes()
    count=len(z.infolist())
data={'version':'0.5.10','files':count,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'related_tests_passed':8,'gui_separate_processes':5,'md_archive':case.name,'m2_pass':False}
(folder/'snapshot.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(data))
