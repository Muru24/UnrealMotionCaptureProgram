"""Freeze the bounded axial prior and explicit missing-span policy once."""
from pathlib import Path
import hashlib,json,re,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1];e=ROOT/'validation/twist-v079'
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
results=json.loads((e/'results.json').read_text(encoding='utf-8'))
metrics=json.loads((e/'twist-comparison.json').read_text(encoding='utf-8'))
assert json.loads((e/'properties.json').read_text())=={'passed':True,'tests':8}
for item in results:
    for kind in ('reopen','fractional'):assert json.loads((e/f'{item["label"]}-{kind}.json').read_text(encoding='utf-8'))['passed']
    report=json.loads((Path(item['blend']).parent/'report.json').read_text(encoding='utf-8'))
    assert report['solver_sha256']==sha(ROOT/'tools/animate_reference_rig.py')
    assert report['correction_sha256']==sha(ROOT/'core/motion/correction.py')
    assert report['root_solver_sha256']==sha(ROOT/'core/motion/root_motion.py')
    assert report['motion_sha256']==item['motion_sha256']
status=json.loads((ROOT/'validation/dance-v074/status.json').read_text(encoding='utf-8'))
assert sha(Path(status['source']))==status['source_sha256']
motion=Path(status['motion']);data=json.loads(motion.read_text(encoding='utf-8'))
assert sha(motion.parent.parent/'sam3d.json')==data['raw_sha256']
assert sha(Path(status['blend']))==sha(ROOT/'validation/dance-v074/example/animation.blend')
for label in ('dance','LongSword','synthetic'):
    assert (e/f'{label}-example/corrected-motion.json').read_bytes()==(ROOT/f'validation/jitter-v078/{label}-example/corrected-motion.json').read_bytes()
heading='## 2026-10-21 / MVP4 v0.7.9 축 비틀림 사전값·가림 뒤 연결\n\n'
common=('우선순위5의 첫 보정 적용. 기존 단순 평행이동 회전 전달은 몸통 회전과 무관한 축 방향을 오래 유지할 수 있었다. '
        '상완·전완·허벅지·종아리8본에서 부모의 현재 회전과 rest 상대방향으로 축 사전값을 만들고, '
        '관측된 본 방향으로 swing을 맞춘 뒤 기존 전달 방향에서 축 roll만 보정한다. '
        'Quaternion 사용, 시간상수0.18초·최대120도/초이며 관측된 빠른 swing 자체를 속도 제한하지 않는다. '
        '접지 발의 바닥 기준 roll, 위치·본길이·루트·접지·점프 및 v0.7.8 잔떨림 보정은 그대로다.\n'
        '동일 추적/장면 안의 부분 누락은 최대0.25초까지만 이전 roll을 기억한다. '
        '긴 부분 누락 뒤에는 부모 사전값으로 재시작하고, 전신 분실/장면·추적 경계에서는 기억을 버린다. '
        '누락 위치/Quaternion은 계속 null이며 보간하지 않는다. animation.json의 orientation_policy에 '
        '본별 short_missing/long_missing 구간, 재연결 수, 적용 최대roll, filled=false를 기록한다. '
        '이는 가려진 동작을 생성하는 모델이 아니라 보수적인 방향 재연결 정책이다.\n')
usage=('프로그램 연결: 재시작 → 기존 결과 선택 → Blender 애니메이션 저장. 새 animation-<id>로 출력하며 GPU 재추출 불필요. '
       '축 roll은 Blender 메쉬/본 방향에서 확인한다. 관절점 위치가 같으므로 오른쪽 선 스켈레톤의 외형은 동일할 수 있다. '
       '원시/M3/이전 .blend를 보존했다. root_motion_kind도 실제 보정본의 값을 animation.json에 전달하도록 맞췄다.\n')
measurement='정량 확인(실제 비틀림 정답률이 아님): '
for item in metrics:
    a,b=item['metrics'];measurement+=f"{item['label']} 평균 부모축 사전값 차이 {a['mean_absolute_parent_twist_prior_error_degrees']:.2f}→{b['mean_absolute_parent_twist_prior_error_degrees']:.2f}도; "
measurement+='정답 라벨 없이 설정한 사전값을 따르는 정도만 측정했다. 일부 순간 큰 차이는 남는다.\n'
checks=('검증102 PASS/기존 opt-in1 SKIP: 기존 비GUI91+격리GUI3+Blender 수학속성8, compileall PASS. '
        '축 rate·정규직교·0/180도 swing·±179도 shortest path·30/60fps·수렴·누락/컷 구간 보고 검증. '
        '춤411/LongSword445/기존합성80/새 가림합성150 프레임 실제 Blender 저장·독립 재오픈·fractional SLERP 검사 통과. '
        '새 합성은3프레임 부분 누락,21프레임 부분 누락,11프레임 전신 분실,장면 변경을 포함한다. '
        '가림 중 null 유지·짧은 roll 연결·긴 부분 누락 재시작 확인. '
        '실제2개영상+기존합성의 corrected-motion.json은 v0.7.8과 바이트 단위 동일하므로 접지/점프/루트/관절위치를 보존했다. '
        '원본영상/원시/M3·이전Blender SHA 보존, 의존성·GPU모델·22본/schema 변경 없음.\n')
limits=('한계: 관절 위치만으로 팔뚝 회내/회외·피부 축 비틀림을 직접 관측할 수 없어 부모 기준의 보수적 prior다. '
        '실제 독립적인 팔다리 비틀림을 일부 완화할 수 있으며 사용자 시각확인이 필요하다. '
        '긴 가림 동작 복원은 미해결이고 재등장 자세 차이도 남을 수 있다. '
        '부분 누락의 Blender proxy는 기존 부모/rest fallback을 표시하므로 관측/복원 결과로 해석하면 안 된다. '
        '전신 누락은 숨김 유지. 옷·머리카락에 붙은 유효값 오추정은 이번 정책의 누락으로 간주하지 않으며 후순위3으로 남긴다. '
        '손가락·얼굴/애니메이션FBX·게임엔진 리타깃도 아직 미구현이다.\n')
review=('M4-TWIST-001 PARTIAL: 단순 transport의 축 누적 편차를 부모 prior로 완화. '
        'M4-OCCLUSION-001 PARTIAL: 누락 길이 구분/짧은 방향 기억/긴 누락 재시작·보고 추가, 긴 동작 복원 미구현. '
        '자체3차검토: ①swing 불변·shortest 축·rate/FPS/antiparallel, '
        '②부모/자식 valid·부분/전신 누락/장면 경계와 발 접지 경로, '
        '③원본/코드 SHA·격리GUI·Blender 재오픈·서브프레임·이전 결과 보존 확인.\n')
current=heading+'Milestone M4 / 우선순위5 축 비틀림·가림 처리 첫 구현 검증, 사용자 확인 대기.\n'
current+='Goal: swing/접지 보존하며 축 roll prior 개선 및 누락 길이별 재연결. Scope: tools/animate_reference_rig.py, GUI 버전, 검증/기록.\n'
current+='Acceptance: twist-only 속성, 짧은/긴 누락 경계, 실제 Blender 재열기, 원본·v078 corrected 위치 보존.\n'+common+usage+measurement+checks+limits
(ROOT/'md/CURRENT_TASK.md').write_text(current,encoding='utf-8')
for name in ('PROGRESS.md','PROJECT.md','ISSUES.md'):
    p=ROOT/'md'/name;p.write_text(heading+(review if name=='ISSUES.md' else '')+common+usage+measurement+checks+limits+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
p=ROOT/'md/MOTION_FORMAT.md';p.write_text(p.read_text(encoding='utf-8')+'\n\n## v0.7.9 축 방향·누락 정책\n\n'+common+
    'M3 및 standard_bone_animation_v1은 유지하며 animation.json에 orientation_policy 진단 metadata를 추가한다. '
    'revision=2, twist_prior, twist_bones, twist_time_constant_seconds, max_twist_correction_degrees_per_second, '
    'max_applied_twist_step_degrees, short_gap_roll_memory_seconds, short_roll_reconnections, long_roll_restarts, '
    'missing_spans, missing_positions_filled를 포함한다. 구간 start_frame/end_frame은0시작 양끝 포함, '
    'seconds=프레임수/fps, 같은 추적/장면별로 분리한다. long_roll_restarts는 긴 부분 누락 뒤 해당8본 재시작 횟수이며 '
    '전신 분실/컷은 캐시 자체를 버리므로 이 수에 포함하지 않는다. correction.revision=7은 그대로.\n',encoding='utf-8')
summary=ROOT/'MVP요약/MVP4_비틀림과가림_v079.md';summary.write_text('# MVP4 v0.7.9 축 비틀림·가림 처리\n\n'+common+usage+measurement+checks+review+limits,encoding='utf-8')
for name in ('README.md','HOME_TRANSFER.md'):
    p=ROOT/name;p.write_text('# 최신 MVP4 v0.7.9 · 축 비틀림·가림 처리\n\n'+usage+limits+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
n=max(int(p.name[4:]) for p in (ROOT/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=ROOT/'진행상황'/f'case{n}';case.mkdir()
for name in ('CURRENT_TASK.md','PROGRESS.md','ISSUES.md','PROJECT.md'):
    p=ROOT/'md'/name;shutil.copyfile(p,case/name);assert sha(p)==sha(case/name)
verification={'version':'0.7.9','tests_passed':102,'skipped':1,'compileall':'PASS','blender_cases':results,'md_archive':case.name,
              'gpu_inference':False,'source_raw_m3_previous_blend_preserved':True,'v078_corrected_positions_unchanged':True,
              'user_visual_review_pending':True,'long_occlusion_motion_reconstruction':False,'metrics_are_not_ground_truth_accuracy':True}
(e/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
folder=ROOT/'snapshots/v0.7.9 MVP';folder.mkdir();target=folder/'m4-twist-gaps-v0.7.9.zip'
extras=[Path(__file__),summary,*case.glob('*.md'),*[p for p in e.rglob('*') if p.is_file() and '__pycache__' not in p.parts],
        *[ROOT/'validation'/name for name in ('test_twist_v079_blender.py','run_twist_v079.py','check_twist_v079.py','compare_twist_v079_blender.py')]]
with zipfile.ZipFile(ROOT/'snapshots/v0.7.8 MVP/m4-small-jitter-v0.7.8.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as archive:
    names=set()
    for info in old.infolist():
        name=info.filename
        if '__pycache__' in name or name.endswith('.pyc'):continue
        p=ROOT/name;archive.writestr(name,p.read_bytes() if not name.startswith('진행상황/') and p.is_file() else old.read(info));names.add(name)
    for p in extras:
        name=p.relative_to(ROOT).as_posix()
        if name not in names:archive.write(p,name);names.add(name)
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    for p in extras+[ROOT/'tools/animate_reference_rig.py',ROOT/'app/gui.py']:
        assert archive.read(p.relative_to(ROOT).as_posix())==p.read_bytes()
meta={'version':'0.7.9','bytes':target.stat().st_size,'files':len(names),'sha256':sha(target),'md_archive':case.name,
      'tests_passed':102,'skipped':1,'user_visual_review_pending':True}
(folder/'snapshot.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');print(json.dumps(meta),flush=True)
