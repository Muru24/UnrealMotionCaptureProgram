"""Freeze the first inferred-contact/SLERP correction increment."""
from pathlib import Path
import json,hashlib,re,zipfile,shutil
ROOT=Path(__file__).resolve().parents[1];e=ROOT/'validation/m4-correction'
comparison=json.loads((e/'comparison.json').read_text(encoding='utf-8'))
actual=json.loads((e/'reopen.json').read_text(encoding='utf-8'));synthetic=json.loads((e/'synthetic-reopen.json').read_text(encoding='utf-8'))
assert actual['passed'] and synthetic['passed'] and comparison['original_motion_unchanged']
for label,record in (('LongSword-example',actual),('synthetic-example',synthetic)):
    src=Path(record['file']).parent;dest=e/label;dest.mkdir(exist_ok=True)
    for name in ('animation.blend','animation.json','corrected-motion.json','report.json'):shutil.copyfile(src/name,dest/name)
    report=json.loads((src/'report.json').read_text(encoding='utf-8'))
    for name,path in (('solver_sha256',ROOT/'tools/animate_reference_rig.py'),('correction_sha256',ROOT/'core/motion/correction.py')):
        assert report[name]==hashlib.sha256(path.read_bytes()).hexdigest()
heading='## 2026-10-21 / MVP4 v0.7.1 접지·회전 떨림 1차 보정\n\n'
common=('사용자 Blender 본 연동 확인 후 발 지면접촉·이동과 심한 관절 떨림 보정 요청. '
 'MVP4 범위에서 요청한 접지/회전 보정 부분을 우선 구현했다. 기존22본·원시SAM3D/후처리·M3 motion.json·'
 'v0.7.0 애니메이션·T-pose 자산은 보존, 모델/패키지/GPU추론 추가 없음.\n')
implementation=('구현: core/motion/correction.py에서 본 head 간 방향을 swing Quaternion으로 표현하고 '
 '최단경로 양방향 SLERP(3~18Hz, 약0.08초 이웃 각속도로 적응)를 적용한 뒤 같은 참조 길이로 계층 재구성. '
 '단일프레임 흔들림을 빠른 동작으로 오인하지 않도록 이웃 구간 속도를 사용한다. '
 'joint 누락/추적 segment/scene 경계를 넘지 않으며 관절을 새로 채우지 않는다. '
 '발 높이·수직 속도·최소지속시간으로 접지를 추정하고 지지 발목XY를 고정한다. '
 '발목Z0.07m/발끝Z0.03m는 이 참조 본 프록시 메쉬의 밑면이 바닥Z0에 오도록 한 값이다. '
 '루트XY는 접지 앵커 제약에서 추정, 골반 높이는 접지·도달거리 조건에 맞춰 조정, '
 '무릎 2-link IK로 허벅지/종아리 길이·굴곡 방향 유지. 도달 불가 접지는 해제하고 별도 상태를 남긴다. '
 '미접지 발도 관통 시 XY를 고정하지 않는 지면 충돌 IK를 적용한다. '
 '접지/충돌 발의 회전축은 수평 지면 기준으로 안정화, .blend에 Ground 평면 추가.\n')
usage=('사용: 프로그램 재시작→완료된 SAM3D 결과 선택→Blender 애니메이션 저장. '
 '자동 보정 후 새 motion/animation-<id>/animation.blend, animation.json, corrected-motion.json, report.json 생성. '
 '완료 시 오른쪽3D 패널도 보정 위치를 표시하고, 이후 결과 재선택 시 완료report·원본motion SHA·보정JSON SHA가 '
 '일치하는 최신 보정만 자동 표시한다. 기존 원시 영상의 선은 다시 렌더하지 않았으므로 오른쪽 보정 패널과 구분한다. '
 'Blender 파일을 열어 Space로 지면과 함께 재생. 이전 .blend에는 소급 반영되지 않으며 새로 저장해야 한다.\n')
verification=('검증: 고유75 PASS/권한opt-in1 SKIP, compileall PASS. 비GUI24(보정8/animation job6/M3코어10), '
 '기존SAM3D/후처리/후등장/긴영상38, 기존GUI10, 분리실행 실제GUI3. '
 '179↔-179°와q/-q, 정지떨림/빠른회전 보존, 지지발 고정·길이·루트이동, 발차기 비고정, '
 '개별관절/전체누락·컷 초기화, 과도각도 튐, 도달불가, 취소, 원본보존, 최신미리보기SHA 거부 확인. '
 'Blender5.1.1 실제 LongSword445프레임과 합성80프레임(발들기·빈프레임·컷·29.883fps)을 저장/재오픈해 '
 '모든 유효본 head/Quaternion·메쉬 변형·접지밑면 확인. 실제 최대head오차8.941e-7m, '
 '접지 발목 프레임간 최대이동6.254e-7m, 접지 프록시 밑면 최소Z약0.002m. '
 '좌/우 접지추정393/364프레임, 같은 접지구간 평균 발목 프레임이동3.469/3.216cm→수치상0. '
 '좌/우 어깨상대손목 위치2차차분 평균0.057703/0.065285→0.032644/0.040305m(약43.4/38.3%감소). '
 '이는 흔들림 대용 지표이며 실제 동작의 정확도/전체 떨림 해결을 뜻하지 않는다. '
 '445프레임 비교MP4 전체 디코드 및 Blender/frame100 비교 이미지 시각검토. 원본 motion SHA 불변.\n')
limits=('한계: 평평한 지면과 참조 신체 비율 가정이며 실제 신발 모양·바닥 검출·정답 접지 라벨은 없다. '
 '추정접지가 틀리면 발 끌기/피벗/점프/웅크림을 과도하게 제한할 수 있고 발목 고정 중 발끝 yaw는 변할 수 있다. '
 '루트XY는 접지 제약으로 만든 경로이며 영상과 동일한 전역 이동·카메라 움직임을 복원한 것이 아니다. '
 '공중 이동·실제 골반높이 복원, 전 관절 해부학적 제한, 지속 오추정/Norma 망토 문제는 미해결. '
 'SLERP는 떨림을 줄이지만 일부 동작을 감쇠시킬 수 있다. 5분 Blender 속도/메모리 미측정, '
 'UE/Unity 임포트·애니메이션FBX·손가락/표정은 미구현/미검증. 사용자 실제 영상 시각확인 대기.\n')
current=heading+'Milestone M4 보정 1차 구현/자동검증 완료, 사용자 확인 대기.\n'
current+=('Goal: 지지 발 지면접촉과 관절 떨림 감소. Scope: core/motion/correction.py, app/animation_job.py/gui.py/skeleton_panel.py, '
 'tools/animate_reference_rig.py, tests/test_motion_correction.py/test_animation_job.py, validation/m4-correction, 관련문서. '
 'Acceptance: Quaternion 최단보간/고정길이/누락경계 유지, 지지발 고정·미접지 발들기, 도달불가 해제·원본 보존, '
 'Blender 실제 바닥 메쉬/위치 재오픈 검사와 GUI 보정 연결.\n')+common+usage+verification+limits
current+='다음: 사용자가 새 .blend와 보정 패널 확인→오접지/발피벗·웅크림·점프 구간별 보정강도 조정. M5 자동진입 없음.\n'
(ROOT/'md/CURRENT_TASK.md').write_text(current,encoding='utf-8')
changes={
 'PROGRESS.md':common+implementation+usage+verification+limits,
 'ISSUES.md':('M4-GROUND-001 PARTIAL: 기존 골반고정/접지없음으로 발 부유·미끄러짐. '
  '추정접지 앵커·루트/골반·다리IK 적용, LongSword 접지 구간 재오픈 미끄러짐/밑면 확인. 실제 정답 접지 판정은 미검증.\n'
  'M4-GROUND-002 HANDLED_FOR_TEST: 접지만 고정한 초기 결과에서 미접지 발끝Z최저약-0.175m 관통을 확인. '
  'XY고정 없는 미접지 지면충돌IK와 지면 기준 foot roll 추가, 최종 발목Z>=0.07/발끝Z>=0.03, '
  'LongSword 미해결충돌0. 다른 영상/형상의 무관통 보장 아님.\n'
  'M4-JITTER-001 PARTIAL: v0.7.0은 부호연속만 처리하고 위치/회전 시간필터 없음. '
  'Quaternion방향 SLERP·길이 재구성 추가. 초기 순간속도 적응은 흔들림도 빠른동작으로 해석해 '
  '지표 감소가13%정도여서 이웃 구간 속도로 보완, 최종 어깨상대손목 지표38~43%감소. '
  '전체 관절 흔들림 해결/정답 동작 검증으로 표현하지 않는다.\n'
  '검증 fixture 변경: 추가된 프로세스 시작전 취소검사로 취소테스트가 자식생성전 종료되어 기대호출 불일치. '
  '취소 신호 시점을 자식생성 뒤로 수정 후 자신이 만든 자식만 종료함을 재검증. 제품 취소실패 아님.\n')+verification+limits,
 'PROJECT.md':common+implementation+usage+('원래 standard_motion_positions_v1 경계와22본 규격을 보존. '
  '보정JSON은 같은 스키마의 별도 파생파일이며 correction 객체에 파라미터·프레임별 접지상태/루트오프셋을 추가한다. '
  '파생파일의 root_motion=true와 root_motion_kind=contact_constraint_estimate는 추정이동임을 명시한다. '
  '원본M3 root_motion=false 및 bone_rotations=null은 변경하지 않는다. '
  'standard_bone_animation_v1 root_motion의 bool 타입도 유지하며 kind 필드를 추가했다. '
  'Python독립core에서 보정, Blender는 재현/bake, UI는 응용job 호출과 준비결과 표시만 담당.\n')+limits}
for name,text in changes.items():
    p=ROOT/'md'/name;p.write_text(heading+text+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
p=ROOT/'md/MOTION_FORMAT.md';p.write_text(p.read_text(encoding='utf-8')+'\n\n## v0.7.1 파생 보정 Motion\n\n'
 '원본파일은 수정하지 않는다. 새 animation-<id>/corrected-motion.json은 기존 positions 스키마와22본 정의를 사용하며 '
 'root_motion=true, root_motion_kind=contact_constraint_estimate와 correction 메타데이터를 추가한다. '
 'correction.frames[i].feet는 좌/우 순서로 inferred_contact/swing/ground_collision/미해결·누락 상태, '
 'root_offset_m은 골반까지 적용한 추정오프셋(그 Z는 골반 높이 보정; 가상root 자체Z는0)을 기록한다. '
 '원본 회전은 참조head방향 swing Quaternion→적응형 최단SLERP→고정길이 재구성→접지/충돌IK→Blender local Quaternion 순서다. '
 '원본 JSON의 기존 필드 및 MHR회전은 덮어쓰지 않는다. 재생 JSON의 smoothing=true, root_motion은 bool 유지, '
 'root_motion_kind로 측정된월드이동과 구분. 보고서에 correction 코드SHA 및 corrected_motion_sha256 추가. '
 'CONSTANT 프레임 키는 유지하고 누락/컷을 메우지 않는다. 시간필터와 접지의 추정 한계는 MVP4 보정 요약 참조.\n',encoding='utf-8')
(ROOT/'MVP요약/MVP4_접지와떨림보정_1차.md').write_text(heading+common+implementation+usage+verification+limits,encoding='utf-8')
for filename in ('README.md','HOME_TRANSFER.md'):
    p=ROOT/filename;p.write_text('# 최신 MVP4 v0.7.1 · 접지/SLERP 보정\n\n'+usage+limits+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
n=max(int(p.name[4:]) for p in (ROOT/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=ROOT/'진행상황'/f'case{n}';case.mkdir()
for name in ('CURRENT_TASK.md','PROGRESS.md','ISSUES.md','PROJECT.md'):
    src=ROOT/'md'/name;shutil.copyfile(src,case/name)
    assert hashlib.sha256(src.read_bytes()).digest()==hashlib.sha256((case/name).read_bytes()).digest()
verified={'version':'0.7.1','tests_passed':75,'skipped':1,'compileall':'PASS','comparison':comparison,
 'actual_blender':actual,'synthetic_blender':synthetic,'md_archive':case.name,'gpu_inference':False,
 'review':['Quaternion shortest path, rates, fixed lengths, stance/swing, unreachable and missing boundaries',
          'independent core, Blender playback adapter, unchanged raw/skeleton contracts and opt-in job',
          'provenance/hash checks, own process cancellation, unique output, SHA preview validation and isolated GUI regression'],
 'ground_truth_contact_tested':False,'world_motion_measured':False,'user_visual_review_pending':True}
(e/'verification.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2),encoding='utf-8')
outdir=ROOT/'snapshots/v0.7.1 MVP';outdir.mkdir();target=outdir/'m4-ground-slerp-v0.7.1.zip'
extras=[ROOT/'core/motion/correction.py',ROOT/'tests/test_motion_correction.py',Path(__file__),
 ROOT/'validation/run_m4_correction.py',ROOT/'validation/check_m4_contact_synthetic.py',
 ROOT/'MVP요약/MVP4_접지와떨림보정_1차.md',*case.glob('*.md'),*[p for p in e.iterdir() if p.is_file()],
 *[p for d in ('LongSword-example','synthetic-example','preview') for p in (e/d).glob('*') if p.is_file()]]
with zipfile.ZipFile(ROOT/'snapshots/v0.7.0 MVP/m4-blender-animation-v0.7.0.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
    seen=set()
    for info in old.infolist():
        name=info.filename
        if '__pycache__' in name or name.endswith('.pyc'):continue
        p=ROOT/name;z.writestr(name,p.read_bytes() if not name.startswith('진행상황/') and p.is_file() else old.read(info));seen.add(name)
    for p in extras:
        name=p.relative_to(ROOT).as_posix()
        if name not in seen:z.write(p,name);seen.add(name)
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    for p in [ROOT/'app/gui.py',ROOT/'app/animation_job.py',ROOT/'tools/animate_reference_rig.py',*extras]:
        assert z.read(p.relative_to(ROOT).as_posix())==p.read_bytes()
    count=len(z.infolist())
with target.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
metadata={'version':'0.7.1','files':count,'bytes':target.stat().st_size,'sha256':sha,'md_archive':case.name,
    'inferred_ground_contact':True,'quaternion_slerp':True,'measured_world_motion':False,'user_visual_review_pending':True}
(outdir/'snapshot.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
print(json.dumps(metadata),flush=True)
