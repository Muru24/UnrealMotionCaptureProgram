"""Freeze stronger smoothing while retaining the reviewed v0.7.3 files."""
from pathlib import Path
import json,hashlib,re,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1];e=ROOT/'validation/m4-smooth'
results=json.loads((e/'results.json').read_text(encoding='utf-8'));comparison=json.loads((e/'comparison.json').read_text());reports={}
for item in results:
    src=Path(item['blend']).parent;dest=e/(item['label']+'-example');dest.mkdir(exist_ok=True)
    provenance=json.loads((src/'report.json').read_text(encoding='utf-8'))
    assert provenance['correction_sha256']==hashlib.sha256((ROOT/'core/motion/correction.py').read_bytes()).hexdigest()
    for name in ('animation.blend','animation.json','corrected-motion.json','report.json'):shutil.copyfile(src/name,dest/name)
    for kind in ('reopen','fractional'):
        report=json.loads((e/f"{item['label']}-{kind}.json").read_text(encoding='utf-8'));assert report['passed'];reports[item['label']+'-'+kind]=report
heading='## 2026-10-21 / MVP4 v0.7.4 보간·잔떨림 추가 완화\n\n'
common=('사용자가 v0.7.3에서 더 부드럽게 보간하도록 요청. 기존 Quaternion 보정 파라미터만 강화했다. '
 '저속 cutoff1.5→0.9Hz, 속도에 따른 cutoff 상승계수3→2, 상한18Hz 유지. '
 'IK 무릎 굴곡면 안정화0.07→0.10초, 큰 방향변화0.025초는 유지. '
 '고립 impulse/방향일관성·접지/전환/길이·누락/컷 보호 및 quarter-frame 재생방식 유지. '
 '보간 키 개수를 늘린 것이 아니라 유효구간의 시간필터를 더 강하게 적용한 버전이다.\n')
usage=('사용: 프로그램 재시작→완료된 SAM3D 결과 선택→Blender 애니메이션 저장 다시 실행. '
 '기존 파일은 자동변경하지 않고 새 motion/animation-<id>/에 고유 저장한다. '
 '새 오른쪽3D 보정 미리보기도 갱신. 확인파일 validation/m4-smooth/LongSword-example/animation.blend. '
 '원시/M3 motion·22본·모델·이전 .blend/MVP 보존, GPU추론·의존성 추가 없음.\n')
checks=('검증 고유78 PASS/권한opt-in1 SKIP, compileall PASS. '
 '비GUI27+기존회귀38+격리실제GUI3+기존GUI10. 빠른180도회전·느린20도/3초·30/60fps·발차기/착지·본길이·'
 '누락/컷·취소·원본보존 회귀 통과. LongSword445/합성80프레임 Blender 새저장·재오픈·접지밑면·'
 '정수head/Quaternion 및 fractional SLERP 검사 통과. '
 'v0.7.3 대비 상완시작점상대 손목 위치2차차분 평균 좌21.5%/우23.6%, '
 '허벅지시작점상대 무릎 좌27.1%/우23.2% 추가감소. '
 '발목 최대 프레임이동<0.3m 회귀와 원본motion SHA불변 확인. '
 '지표감소는 시간적 완화 정도이며 실제 영상의 동작 정확도/모든 떨림해결을 뜻하지 않는다.\n')
limits=('한계: 더 강한 저속필터는 작은 동작·급변을 더 완만하게 만들 수 있다. '
 '단일프레임 실제 빠른 peak도 고립잡음과 혼동할 수 있다. 정답접지/실제월드이동/지속관절오추정·Norma·긴누락은 미해결. '
 '사용자 전체영상·5분 bake 자원부하·엔진임포트 미검증. 새파일 사용자 시각확인 대기, M5 자동진입 없음.\n')
current=heading+'Milestone M4 보정 파라미터 강화 / 구현·이번 검증 완료, 사용자 확인 대기.\n'
current+=('Goal/Acceptance: 직전버전보다 저속잔떨림 완화, 빠른/느린 의도동작·접지·연속재생·원본/누락경계 보존. '
 'Scope: core/motion/correction.py, app/gui.py 버전, validation/run_m4_smooth.py와 관련문서.\n')+common+usage+checks+limits
(ROOT/'md/CURRENT_TASK.md').write_text(current,encoding='utf-8')
for name,text in {
 'PROGRESS.md':common+usage+checks+limits,
 'ISSUES.md':('M4-JITTER-001 PARTIAL: 사용자 추가 완화 요청으로 cutoff/속도적응/IK평면 파라미터 조정. '
  '기존 정답오추정과 구분하며 직전대비 지표감소 확인. '
  '검증 실행기 준비 중 PowerShell 인라인 문자열 quoting으로 SyntaxError가 발생해 모델작업 시작 전 종료. '
  '별도 validation/run_m4_smooth.py로 작성 후 실제 전체검증 성공, 제품 출력 실패 아님.\n')+common+checks+limits,
 'PROJECT.md':common+('correction.revision=4, cutoff_hz=[0.9,18], ik_pole_smoothing_seconds=0.10. '
  '기존 positions/animation schema·22본·Quaternion 순서·quarter-frame 샘플은 동일. '
  '원본은 유지하고 새 파생 보정결과로 저장한다.\n')+usage+limits
}.items():
    p=ROOT/'md'/name;p.write_text(heading+text+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
p=ROOT/'md/MOTION_FORMAT.md';p.write_text(p.read_text(encoding='utf-8')+'\n\n## v0.7.4 강한 저속 완화\n\n'
 'correction.revision=4, cutoff_hz=[0.9,18], 속도 상승계수2, IK pole0.10초(큰방향변화0.025초). '
 '새 스키마·본·보간키 추가가 아니라 같은 시간필터의 강도조정이다. 원본/누락/컷 및 접지전환·quarter-frame 재생 정책 유지.\n',encoding='utf-8')
(ROOT/'MVP요약/MVP4_보간강화_v074.md').write_text(heading+common+usage+checks+limits,encoding='utf-8')
for name in ('README.md','HOME_TRANSFER.md'):
    p=ROOT/name;p.write_text('# 최신 MVP4 v0.7.4 · 저속 보정 강화\n\n'+usage+limits+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
n=max(int(p.name[4:]) for p in (ROOT/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=ROOT/'진행상황'/f'case{n}';case.mkdir()
for name in ('CURRENT_TASK.md','PROGRESS.md','ISSUES.md','PROJECT.md'):
    p=ROOT/'md'/name;shutil.copyfile(p,case/name)
    assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((case/name).read_bytes()).digest()
verified={'version':'0.7.4','tests_passed':78,'skipped':1,'compileall':'PASS','blender':reports,'comparison':comparison,
 'md_archive':case.name,'gpu_inference':False,'user_visual_review_pending':True,
 'review':['fast/slow/rate/noise/length and stance regression at new parameters',
          'unchanged core/app/Blender/skeleton boundaries',
          'source hashes, unique output/cancellation and isolated GUI regression']}
(e/'verification.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2),encoding='utf-8')
folder=ROOT/'snapshots/v0.7.4 MVP';folder.mkdir();target=folder/'m4-stronger-smoothing-v0.7.4.zip'
extras=[Path(__file__),ROOT/'validation/run_m4_smooth.py',ROOT/'MVP요약/MVP4_보간강화_v074.md',*case.glob('*.md'),
 *[p for p in e.iterdir() if p.is_file()],*[p for d in ('LongSword-example','synthetic-example') for p in (e/d).glob('*') if p.is_file()]]
with zipfile.ZipFile(ROOT/'snapshots/v0.7.3 MVP/m4-jitter-refinement-v0.7.3.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
    names=set()
    for info in old.infolist():
        name=info.filename
        if '__pycache__' in name or name.endswith('.pyc'):continue
        p=ROOT/name;z.writestr(name,p.read_bytes() if not name.startswith('진행상황/') and p.is_file() else old.read(info));names.add(name)
    for p in extras:
        name=p.relative_to(ROOT).as_posix()
        if name not in names:z.write(p,name);names.add(name)
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    for p in [ROOT/'app/gui.py',ROOT/'core/motion/correction.py',*extras]:assert z.read(p.relative_to(ROOT).as_posix())==p.read_bytes()
    count=len(z.infolist())
with target.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
meta={'version':'0.7.4','files':count,'bytes':target.stat().st_size,'sha256':sha,'md_archive':case.name,'user_visual_review_pending':True}
(folder/'snapshot.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');print(json.dumps(meta),flush=True)
