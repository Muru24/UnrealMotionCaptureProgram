"""Freeze the measured small-jitter correction and archive four current MD files once."""
from pathlib import Path
import json,hashlib,re,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1];e=ROOT/'validation/jitter-v078'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
results=json.loads((e/'results.json').read_text(encoding='utf-8'))
comparison=json.loads((e/'comparison.json').read_text(encoding='utf-8'))
for item in results:
    for kind in ('reopen','fractional'):
        assert json.loads((e/f'{item["label"]}-{kind}.json').read_text(encoding='utf-8'))['passed']
    report=json.loads((Path(item['blend']).parent/'report.json').read_text(encoding='utf-8'))
    assert report['correction_sha256']==sha(ROOT/'core/motion/correction.py')
    assert report['root_solver_sha256']==sha(ROOT/'core/motion/root_motion.py')
for item in comparison:
    assert all(metric['reduction_fraction']>0 for metric in item['metrics'])
    assert item['airborne_after']==item['airborne_before']
    assert abs(item['new_jump_height_m']-item['old_jump_height_m'])<.005
status=json.loads((ROOT/'validation/dance-v074/status.json').read_text(encoding='utf-8'))
assert sha(Path(status['source']))==status['source_sha256']
motion=Path(status['motion']);data=json.loads(motion.read_text(encoding='utf-8'))
assert sha(motion.parent.parent/'sam3d.json')==data['raw_sha256']
assert sha(Path(status['blend']))==sha(ROOT/'validation/dance-v074/example/animation.blend')
heading='## 2026-10-21 / MVP4 v0.7.8 작은 관절·루트 잔떨림 완화\n\n'
common=('우선순위4 잔떨림 추가 완화. 6속도/1접지/2영상·접지 이동 추정 유지. '
        '다음5비틀림·긴 가림, 3옷·머리카락 오추정은 후순위.\n'
        'v0.7.8 correction.revision=7: 기존 SLERP 강도를 전체적으로 올리지 않고, '
        '앞뒤 약1/30초 quaternion midpoint와 현재 회전의 작은 차이만 대칭으로 완화한다. '
        '상체2~8도/다리1~5도 범위에서 가중치를 줄여 큰 빠른 변화는 보존한다. '
        '새 영상 루트 후보의 XY에서도5~25mm 크기의 작은 곡률만 완화하고 루트 후보Z/공중 판정은 별도로 유지한다. '
        '일정 속도 회전/직선 이동은 그대로이며, 누락·장면·camera epoch/유효구간 경계를 넘지 않는다. '
        '접지/IK 뒤에 필터를 추가하지 않아 잠긴 발·본 길이를 재차 움직이지 않는다.\n')
usage=('기존 프로그램 경로에 연결했다. 프로그램 재시작 → 기존 결과 선택 → Blender 애니메이션 저장으로 '
       '새 animation-<id> 생성 및 오른쪽3D 보정본 갱신. GPU 재추출 불필요. '
       '원시/M3/이전 .blend와 빠른 후보 추론·영상 루트/접지 경로를 보존했다.\n')
measure=('v0.7.7 대비 전체 프레임의 부모상대 관절 위치2차차분 평균 지표: '
         'LongSword 손목 좌17.70%/우17.60%, 무릎 좌1.89%/우2.58% 감소, 루트3.81% 감소. '
         '춤 손목 좌4.61%/우6.66%, 무릎 좌4.90%/우9.16%, 루트3.46% 감소. '
         '실제 Blender 키의 팔/종아리 angular-speed-change 지표도 확인한12개 모두 감소했고 '
         '최대1프레임 회전각 증가는1도 미만. 이 지표는 시간적 완화 정도이며 동작 정답률이 아니다. '
         '춤 공중판정147~153프레임 동일, 루트Z최대0.18111→0.17917m(약1.94mm차), '
         '175~185프레임 발목0.07m 접지 유지.\n')
checks=('검증 고유94 PASS/기존 opt-in1 SKIP, compileall PASS. core/app/루트/새필터51+기존회귀40+격리GUI3. '
        '작은 회전/루트 노이즈 감소, 일정속도 운동 보존, 빠른90도 peak 시점/높이 보존, '
        'Quaternion 부호/±180도·30/60fps·짧은span, 큰 루트급변/Z보존 및 기존 접지·공중/착지·누락/컷·'
        '원본해시/취소 회귀 통과. 춤411/LongSword445/합성80 프레임 실제 새 Blender 저장·재오픈 '
        'head/Quaternion·메쉬밑면·접지 및 fractional SLERP/누락경계 검사 통과. '
        '원본영상/원시JSON/M3·이전Blender SHA 보존. GPU추론·의존성·22본/스키마 변경 없음.\n')
review=('M4-JITTER-001 PARTIAL: source 방향과 새 루트 후보의 작은 요동을 완화했다. '
        '상체/다리에2~8도를 동일 적용한 중간실험은 춤 왼무릎 위치지표가0.74% 증가하여 '
        '다리 적용을 기각했다. 다리를1~5도로 보수 적용한 최종본은 위10개 위치 지표 모두 감소했다. '
        '자체3차검토: shortest-arc·peak/일정속도·FPS, IK/접지 전 필터와 root/camera 구간 분리, '
        '소스/코드SHA·취소/분절/기존GUI·원본/기존결과 보존 확인.\n')
limits=('한계: 작은 실제 빠른 손짓도 잔떨림과 비슷하면 일부 완만해질 수 있다. '
        '팔·다리 축 비틀림, 지속적으로 잘못 잡힌 관절·머리카락/옷·긴 가림은 해결하지 않았다. '
        '골격 자세 오류/큰 순간 회전은 잡음으로 단정해 지우지 않으며 다음5에서 별도 검사한다. '
        '거리·깊이·접지는 계속 모델 추정이고 모든 떨림 해결/동작 정확도 개선을 보장하는 수치는 아니다. '
        '사용자 새 보정본 시각확인 대기.\n')
current=heading+'Milestone M4 / 우선순위4 작은 잔떨림 보정 구현·검증, 사용자 확인 대기.\n'
current+='Goal: 작은 관절/루트 요동을 줄이면서 빠른 peak·일정속도·접지/점프·구간경계 보존. Scope: core/motion/correction.py 및 root_motion.py, GUI 버전, 테스트/검증.\n'
current+='Acceptance: 실제2개영상 관절/루트 지표 감소와 본길이·접지·공중판정·Blender 보간/원본SHA 회귀 통과.\n'+common+usage+measure+checks+limits
(ROOT/'md/CURRENT_TASK.md').write_text(current,encoding='utf-8')
for name in ('PROGRESS.md','PROJECT.md','ISSUES.md'):
    p=ROOT/'md'/name;p.write_text(heading+(review if name=='ISSUES.md' else '')+common+usage+measure+checks+limits+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
p=ROOT/'md/MOTION_FORMAT.md'
p.write_text(p.read_text(encoding='utf-8')+'\n\n## v0.7.8 작은 곡률 완화\n\n'
    'M3/animation schema 및22본 그대로, correction.revision=7. 기존 quaternion IIR 후 각 유효span에서 '
    'stride=max(1,round(fps/30))의 앞뒤 shortest SLERP midpoint를 구한다. 현재값과 차이가 '
    '상체2~8도/다리1~5도 사이에서 smoothstep으로 가중치0.5→0, 임계 이상 큰 차이는0이다. '
    '일정각속도는 midpoint와 같아 유지한다. endpoint와 stride보다 짧은span은 그대로. '
    '영상 루트 XY 후보도 같은 시간 간격의 midpoint 거리5~25mm에서0.5→0 가중치, Z는 그대로. '
    '접지/IK 후 위치나 최종 local Quaternion을 다시 평균하지 않는다. 필터 파라미터는 '
    'small_rotation_curvature_degrees, leg_small_rotation_curvature_degrees, small_rotation_smoothing_seconds 및 '
    'root_solver_sha256으로 확인한다. 미세한 실제 움직임과 잡음 구분은 완전하지 않다.\n',encoding='utf-8')
summary=ROOT/'MVP요약/MVP4_잔떨림추가완화_v078.md'
summary.write_text('# MVP4 v0.7.8 작은 잔떨림 추가 완화\n\n'+common+usage+measure+checks+review+limits+'\n확인파일: validation/jitter-v078/dance-example/animation.blend\n',encoding='utf-8')
for name in ('README.md','HOME_TRANSFER.md'):
    p=ROOT/name;p.write_text('# 최신 MVP4 v0.7.8 · 작은 잔떨림 추가 완화\n\n'+usage+limits+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
n=max(int(p.name[4:]) for p in (ROOT/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=ROOT/'진행상황'/f'case{n}';case.mkdir()
for name in ('CURRENT_TASK.md','PROGRESS.md','ISSUES.md','PROJECT.md'):
    p=ROOT/'md'/name;shutil.copyfile(p,case/name);assert sha(p)==sha(case/name)
verification={'version':'0.7.8','tests_passed':94,'skipped':1,'compileall':'PASS','blender_cases':results,
    'md_archive':case.name,'gpu_inference':False,'source_raw_m3_previous_blend_preserved':True,
    'user_visual_review_pending':True,'metrics_are_not_ground_truth_accuracy':True}
(e/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
folder=ROOT/'snapshots/v0.7.8 MVP';folder.mkdir();target=folder/'m4-small-jitter-v0.7.8.zip'
extras=[Path(__file__),summary,ROOT/'tests/test_jitter_filter.py',*case.glob('*.md'),*[p for p in e.rglob('*') if p.is_file()],
    *[ROOT/'validation'/name for name in ('inspect_jitter_v078.py','check_jitter_v078.py','run_jitter_v078.py','compare_jitter_animation_v078.py')]]
with zipfile.ZipFile(ROOT/'snapshots/v0.7.7 MVP/m4-image-root-v0.7.7.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as archive:
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
    for p in extras+[ROOT/'core/motion/correction.py',ROOT/'core/motion/root_motion.py',ROOT/'app/gui.py']:
        assert archive.read(p.relative_to(ROOT).as_posix())==p.read_bytes()
with target.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
meta={'version':'0.7.8','bytes':target.stat().st_size,'files':len(names),'sha256':digest,'md_archive':case.name,
      'tests_passed':94,'skipped':1,'user_visual_review_pending':True}
(folder/'snapshot.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');print(json.dumps(meta),flush=True)
