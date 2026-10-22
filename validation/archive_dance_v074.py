"""Record this extraction only; the v0.7.4 product snapshot remains unchanged."""
from pathlib import Path
import json,hashlib,re,shutil
from app.animation_job import ROOT

e=ROOT/'validation/dance-v074';state=json.loads((e/'status.json').read_text(encoding='utf-8'))
verified=json.loads((e/'verification.json').read_text(encoding='utf-8'))
assert state['status']=='completed' and verified['input_sha256_unchanged']
for name in ('blender-reopen','blender-fractional'):assert json.loads((e/f'{name}.json').read_text())['passed']
src=Path(state['blend']).parent;dest=e/'example';dest.mkdir(exist_ok=True)
for name in ('animation.blend','animation.json','corrected-motion.json','report.json'):shutil.copyfile(src/name,dest/name)
heading='## 2026-10-21 / v0.7.4 추가 춤 영상 실제 추출\n\n'
summary=(f"사용자 요청 영상 이게 실제로 가능한 춤이였다고_ #부리부리마신소환춤.mp4를 새 결과폴더에 추출했다. "
 f"제품코드는 v0.7.4 그대로. SAM2 대상후보는 전경 실제인물1개(index0), TV애니메이션 인물을 선택하지 않았다. "
 f"SAM2→SAM3D→기존 자동후처리→M3→v0.7.4 접지/잔떨림 보정→Blender 경로. "
 f"실제 {verified['frames']}프레임, tracking 관측{verified['tracking_observations']}, "
 f"자동후처리 상태 {verified['automatic_status']}, motion 입력 {verified['source_kind']}.\n")
evidence=('검증: 원본 SHA불변, source/mask/raw overlay/존재하는 최종재연결 영상 전체디코드와 JSON프레임 정렬, '
 'Blender 실제 재오픈 head/Quaternion·메쉬·접지 및 fractional SLERP/경계검사 통과. '
 '새 단위테스트 재실행 없음(제품무변경), 기존 v0.7.4의78 PASS/1 SKIP와 별개 실제영상 검증. '
 'raw-review.jpg/review.jpg는 프레임 표본 시각검토용이며 정답관절/접지·신원 전체 정확도 검증 아님.\n')
locations=f"결과: {state['output']}\nBlender: {state['blend']}\n확인복사본: validation/dance-v074/example/animation.blend\n"
limits=('M4-GROUND-CROUCH-001 OPEN: 새 영상175~185프레임(약5.8~6.2초) 웅크림에서 보정JSON의 양발이 swing이며 '
 '발목Z약0.26~0.39m로 접지목표0.07m보다 높게 남는다. 원본 표본에서는 발의 바닥 접촉이 유지되는 것으로 보이지만 '
 '정답 접지라벨/실제미터 측정 검증은 아니다. 골반높이 고정으로 정규화한 관절에서 발높이 조건으로 접지를 추정하면 '
 '웅크림을 발들기로 오인하고 골반 하강을 복원하지 못할 수 있다. 이번 요청은 현버전 실제추출이므로 '
 '알고리즘을 즉석 변경하지 않고 결과/이슈를 보존했다. 후속 접지·골반 보정 검토 필요.\n'
 '컨테이너 메타데이터414프레임/30fps/13.8초였으나 현재 OpenCV 원본디코드 및 추적/추출은411프레임으로 일치. '
 '이 차이의 컨테이너/타임스탬프 원인은 이번에 확정하지 않았다. '
 '윈도우 사전 CIM 프로세스정보 조회는 접근불가였으며 권한상승/사용자 프로세스 종료 없이 사용가능한 GPU/프로세스 조회로 대체. '
 '배치추출 중지 상태는 유지하고 요청된 이 한 영상만 수행했다. '
 '접지·월드이동은 추정이며 옷/가림·지속관절 오추정은 해결 보장하지 않는다. 사용자 결과확인 대기.\n')
current=heading+'Milestone M4 / 새 영상 추출·검증 완료, 사용자 시각확인 대기.\n'
current+=('Goal/Scope: 지정한 춤1개를 현재 프로그램과 같은 모델/보정으로 추출. 제품 알고리즘 변경 없음. '
 'Acceptance: 원본보존·새 결과·기존전체후처리 수행상태 명시·모션/영상 정렬·Blender 재생 검사.\n')+summary+locations+evidence+limits
(ROOT/'md/CURRENT_TASK.md').write_text(current,encoding='utf-8')
for name,text in {'PROGRESS.md':summary+locations+evidence+limits,
 'ISSUES.md':'M4-VIDEO-VERIFYING: '+limits+evidence,
 'PROJECT.md':summary+'실행/검증 증거 validation/dance-v074, 제품 v0.7.4/참조22본/모델·스키마 그대로. '+locations+limits}.items():
    p=ROOT/'md'/name;p.write_text(heading+text+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
(e/'README.md').write_text(heading+summary+locations+evidence+limits,encoding='utf-8')
n=max(int(p.name[4:]) for p in (ROOT/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=ROOT/'진행상황'/f'case{n}';case.mkdir()
for name in ('CURRENT_TASK.md','PROGRESS.md','ISSUES.md','PROJECT.md'):
    p=ROOT/'md'/name;shutil.copyfile(p,case/name)
    assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((case/name).read_bytes()).digest()
record={'md_archive':case.name,'version':'0.7.4','product_code_changed':False,
        'existing_mvp_preserved':True,'output':state['output'],'blend':str(dest/'animation.blend')}
(e/'archive.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False),flush=True)
