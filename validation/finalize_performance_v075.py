"""Archive the tested optional candidate-speed change and current work order."""
from pathlib import Path
import json,hashlib,re,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1]
heading='## 2026-10-21 / MVP4 v0.7.5 후보 추론 속도 선택\n\n'
common=('사용자 우선순위: 6속도 → 1접지 → 2루트 이동·높이 → 4잔떨림 → 5비틀림·긴 가림. '
        '3옷·머리카락 오추정/Norma는 후순위. 기존 v0.7.4 춤 결과는 사용자가 양호하다고 확인.\n'
        'v0.7.5: GUI 빠른 후보 추론(시험) 체크를 추가했다. 기본 OFF/full 유지. '
        '체크 시 추가 observed/tight/stable-flip 후보만 body decoder를 사용하며 원본 SAM3D full, '
        '부분 재추정, 추적, M3, M4 보정은 동일하다. 후보 수/프레임 수를 줄이지 않는다. '
        'full/body 결과 캐시를 분리하고 자동후처리 report에 stage_seconds/seconds/프로필을 기록한다. '
        '기존 결과를 열 때도 실행 전 체크 상태를 적용한다. 프로그램 재시작 필요.\n')
measure=('RTX4060 로컬 실측: 춤 초반4프레임×2ROI full 약6.04초 대 body1.74초(3.47배), '
         '전반8프레임×2ROI full 평균13.46초 대 body3.64초(3.70배). '
         '전반 표본의 최대 차이2D28.83px/카메라상대3D0.0871m. 손 전용 추론의 팔·손목 보정이 '
         '사라질 수 있으므로 품질 동등/무손실 최적화가 아니다. 초기 표본만으로 동등하다고 결론내리지 않았다. '
         '전체 처리시간/여러 영상/5분영상의 속도·정확도 검증은 아직 없고 후보 단계 수치를 전체 배수로 해석하지 않는다. '
         'cache유지0.99배, bbox2개 batch1.004배(관절차1.86px), threads1개1.016배, TF32 1.019배는 '
         '유의한 개선 근거 부족으로 제품에 적용하지 않았다.\n')
checks=('검증: 비GUI28 PASS, 격리실제GUI 기본출력·빠른출력·기존결과열기3 PASS(총31), compileall PASS. '
        '실제 CUDA candidate worker body3프레임×3후보9회와 선택/비교영상 저장 통과, 원본/기존raw SHA불변. '
        '자체3차검토: 프로필·캐시·프레임/본 규격 / 기존 full·raw 경로 보존 / 취소·로컬프로세스·원본보존. '
        '검증 실행기 최초 선택저장에 필요한 parent sam3d.json fixture가 없어 FileNotFoundError; '
        '분리된 짧은 fixture와 selection 폴더로 수정해 GPU재실행 없이 재검증 통과. 제품오류 아님.\n')
limits=('6속도는 시험옵션 제공·부분완료이며 기본 품질모드의 큰 속도개선은 미완료. '
        '빠른 모드 전체 시각검증/직전 약33분 전체추출 대비 시간 비교 대기. '
        '다음 1: M4-GROUND-CROUCH-001 웅크림·착지 시 접지/골반높이. 이후 2→4→5. '
        '이번 변경은 기존 접지·잔떨림·비틀림 문제를 해결하지 않는다.\n')
current=heading+'Milestone M4 / 6속도 우선: 시험옵션 구현·한정검증, 전체 품질/시간 검증 대기.\n'
current+='Goal: 후보 추론 비용을 줄이고 품질 차이를 표시한다. Scope: app candidate/automatic/gui, 관련 테스트·검증 실행기.\n'
current+='Acceptance: 기존 full 기본값/원본 유지, body 명시선택, 캐시 분리, 실제 worker와 GUI 연결 검증.\n'+common+measure+checks+limits
(ROOT/'md/CURRENT_TASK.md').write_text(current,encoding='utf-8')
for name in ('PROGRESS.md','PROJECT.md','ISSUES.md'):
    p=ROOT/'md'/name
    issue='M4-PERF-001 PARTIAL: 후보 full에는 손 전용 추가 추론이 포함된다. body는 비용을 줄이지만 전신/팔 관절도 달라질 수 있다.\n' if name=='ISSUES.md' else ''
    p.write_text(heading+issue+common+measure+checks+limits+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
summary=ROOT/'MVP요약/MVP4_후보속도선택_v075.md'
summary.write_text('# MVP4 v0.7.5 후보 추론 속도 선택\n\n'+common+measure+checks+limits,encoding='utf-8')
n=max(int(p.name[4:]) for p in (ROOT/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=ROOT/'진행상황'/f'case{n}';case.mkdir()
for name in ('CURRENT_TASK.md','PROGRESS.md','ISSUES.md','PROJECT.md'):
    p=ROOT/'md'/name;shutil.copyfile(p,case/name)
    assert p.read_bytes()==(case/name).read_bytes()
out=ROOT/'snapshots/v0.7.5 MVP';out.mkdir()
target=out/'m4-candidate-speed-v0.7.5.zip'
extras=[ROOT/'app/automatic_postprocess.py',ROOT/'app/candidate_job.py',ROOT/'app/candidate_worker.py',ROOT/'app/gui.py',ROOT/'tests/test_automatic_postprocess.py',Path(__file__),ROOT/'validation/benchmark_cuda_cache.py',ROOT/'validation/verify_performance_v075.py',summary,*case.glob('*.md')]
extras += list((ROOT/'validation').glob('performance-*/benchmark.json'))
extras += [ROOT/'validation/performance-v075-worker/verification.json']
base=ROOT/'snapshots/v0.7.4 MVP/m4-stronger-smoothing-v0.7.4.zip'
with zipfile.ZipFile(base) as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as archive:
    names=set()
    for info in old.infolist():
        name=info.filename
        if '__pycache__' in name or name.endswith('.pyc'):continue
        p=ROOT/name
        archive.writestr(name,p.read_bytes() if not name.startswith('진행상황/') and p.is_file() else old.read(info));names.add(name)
    for p in extras:
        name=p.relative_to(ROOT).as_posix()
        if name not in names:archive.write(p,name);names.add(name)
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    for p in extras:assert archive.read(p.relative_to(ROOT).as_posix())==p.read_bytes()
with target.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
meta={'version':'0.7.5','sha256':sha,'bytes':target.stat().st_size,'files':len(names),'md_archive':case.name,'tests_passed':31,'full_video_benchmark_pending':True,'quality_equivalence':False,'default_inference':'full','fast_candidate_inference':'body'}
(out/'snapshot.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
print(json.dumps(meta),flush=True)
