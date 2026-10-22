"""Freeze reviewed M4 implementation and CPU evidence, preserving earlier archives."""
from pathlib import Path
import json,hashlib,re,zipfile,shutil
ROOT=Path(__file__).resolve().parents[1];e=ROOT/'validation/m4'
results=json.loads((e/'results.json').read_text(encoding='utf-8'))
assert all(r['passed'] and r['skin_mesh_moves'] for r in results)
for label,item in zip(('synthetic','LongSword'),results):
    source=Path(item['file']).parent;target=e/(label+'-example');target.mkdir(exist_ok=True)
    for name in ('animation.blend','animation.json','report.json'):shutil.copyfile(source/name,target/name)
    shutil.copyfile(source.parent/'motion.json',target/'motion.json')
header='## 2026-10-21 / MVP4 v0.7.0 Blender 본 애니메이션\n\n'
common=('사용자가 MVP3 영상1개 출력·스켈레톤 정상 확인. 떨림은 본 연결 뒤 보정하기로 하고 MVP4 진행 승인. '
 '22본 정의·MVP2 원시/후처리·MVP3 motion.json과 T-pose/정지FBX를 보존한다. '
 '새 모델/패키지/네트워크/GPU추론 없음. 기존 일괄추출 취소 유지.\n')
usage=('사용: StartPrototype.cmd 재시작 → 결과목록에서 완료된 SAM3D 결과 선택 → '
 '3D 패널 아래 Blender 애니메이션 저장. 필요하면 먼저 같은 M3 CPU 변환을 수행한다. '
 'motion/animation-<고유값>/animation.blend 및 animation.json/report.json 생성. '
 'Blender로 .blend를 열어 Space 재생. 새 영상 출력 때 애니메이션 저장은 버튼으로 명시적으로 실행한다.\n')
limits=('한계: 제자리 root/참조 골반높이 유지, 실제 전역이동·골반높이·접지/Foot Lock 없음. '
 '손가락/표정 본과 추적 연결, 애니메이션 FBX와 엔진 직접 임포트는 미구현/미검증. '
 '관절점만으로 축 비틀림을 관측할 수 없어 몸 좌우 방향·팔다리 최소회전 운반 기준을 사용한다. '
 '끝 본은 부모 회전을 상속한다. 개별 관절 누락은 JSON null/missing이며 .blend에서는 부모/기준 자세 fallback이라 복원된 동작이 아니다. '
 '대상 전체 누락은 전신 숨김, 구간 경계/누락은 회전 이력 초기화. CONSTANT 샘플 키프레임으로 긴 누락/컷을 보간하지 않는다. '
 '떨림/SLERP 필터는 기본 미적용. 5분18000프레임 Blender 속도·메모리는 미측정, 처리 제한30분. '
 'Norma 의상 오추정/M2 후보 첫26프레임 제약/QA-002 잔여는 해결 선언하지 않는다.\n')
verification=('검증: 고유66 PASS/기존 권한 opt-in1 SKIP, compileall PASS. '
 '신규6: 취소 선차단/외부 파일명 거부/실패시 원본·기존 결과 보존/인자 배열·SHA/자기 프로세스만 취소/실제 GUI 버튼→worker→완료 연동. '
 '기존 M3 코어10+GUI2, 기존 GUI10, SAM3D·자동후처리·후등장·긴영상 비GUI38 회귀. '
 'Blender5.1.1 실제 background 합성8프레임(미검출·누락·179→181도·장면경계·29.883fps·Tpose identity) '
 '및 LongSword445프레임 생성/파일 재오픈/모든 유효 본 회전·head·스킨 메쉬 움직임 검사. '
 '재오픈 최대 head 오차1.605e-6m 미만, 방향 오차1e-4 미만. '
 '이는 입력 스켈레톤 재현 오차이며 영상 동작의 정답 정확도가 아니다. 렌더 frame101 시각검토. '
 '실제 사용자 Blender 재생 확인은 대기.\n')
current=(header+'Milestone M4 Bone Solver / 1차 구현·자동검증 완료, 사용자 시각확인 대기.\n'
 'Goal: 기존22본에 로컬 Quaternion·키프레임 연결. Scope: tools/animate_reference_rig.py, '
 'app/animation_job.py/gui.py, tests/test_animation_job.py, validation/m4, 규격·인계 MD. '
 'Acceptance: Tpose 기준 로컬회전/부모계층/참조길이 재현, 회전부호 연속성·누락/컷 경계, '
 'Blender 실제 재생 가능한 Action·스킨메쉬, fps/전체프레임 유지, 원본보존·CPU 처리·취소·검증.\n'
 +common+usage+verification+limits+
 '다음: 사용자가 실제 Blender 동작 확인 후 Quaternion/SLERP 시간 필터와 비틀림·관절 제약, 접지는 후속 범위로 분리. '
 '현재 오른쪽 3D 패널은 M3 위치 미리보기 그대로이며 .blend 회전 평가 뷰어로 바꾼 것은 아니다.\n')
(ROOT/'md/CURRENT_TASK.md').write_text(current,encoding='utf-8')
updates={
 'PROGRESS.md':common+('구현: 실제 Blender rest matrix와 parent matrix로 pose.matrix_basis 로컬 quaternion(wxyz)·location 계산. '
  '연결 본은 참조 길이로 재현, 분리된 쇄골/골반-허벅지 attachment는 M3 head 위치 보존을 위해 로컬 위치키 포함. '
  'Euler 사용 없음, q/-q 연속부호 및 limb roll 최소회전 운반. root rest 회전 고정. '
  '별도 Action/키프레임·유효 첫프레임·nominal fps, 골반고정·기존 메쉬 ARMATURE 변형. '
  'GUI 선택 결과의 M3 변환 재사용 후 선택형 CPU Blender worker, 고유 출력·로그·입력SHA·timeout·자기 자식 취소. '
  '저장 실패/취소는 완료 report를 만들지 않으며 이전 사용자 결과는 덮어쓰지 않는다.\n')+usage+verification+limits,
 'ISSUES.md':('M4-001 FIXED: 합성 미검출 뒤 재등장 프레임에서 hide_viewport 상태로 depsgraph를 평가해 직전 pose가 남고 '
  'head 재구성 최대2.73m 실패. 가시성을 평가 전에 갱신하고 root는 rest matrix를 유지하도록 수정. '
  '최종 합성 재오픈 오차2.984e-7m/실제 LongSword1.605e-6m미만. 초기 실패 로그·중간 파일은 보존, 완료 결과와 구분한다.\n'
  'M4-002 KNOWN_LIMIT: 축 비틀림은 점 위치만으로 관측 불가. 횡축 평행 시 roll 반전 방지를 위해 팔다리는 '
  '이전 world 방향의 최소회전 운반을 사용하며 단절/컷에서 초기화. 정확한 twist 정답으로 보지 않는다.\n'
  'M4-003 DEFERRED: 사용자와 떨림 보정은 본 연동 뒤 진행하기로 합의. 현재는 원본 샘플을 보존, SLERP 필터 미적용.\n'
  'M4-004 UNBENCHMARKED: 최대5분 Blender 전체 저장 자원부하 미검증. 이번 실제검증은445프레임.\n')+limits+verification,
 'PROJECT.md':common+('M4 승인 범위: 기존 standard_motion_positions_v1를 바꾸지 않고 별도 '
  'standard_bone_animation_v1 파일과 .blend Action으로 확장. 본22개·계층·기존 JSON 유지. '
  'Blender backend는 tools 스크립트, 응용 process orchestration은 app/animation_job.py, UI는 해당 job 호출만 담당. '
  '명시적 저장 버튼을 사용하며 GPU 재추론·추출시 자동 Blender 실행 없음. '
  'M4 첫 MVP는 위치를 로컬 quaternion과 키프레임으로 재현하는 범위이며 '
  '관절 해부학적 제한·떨림 필터·world root·접지·임의 리타게팅·Unity/UE 직접재생은 완료 아님.\n')+usage+limits}
for name,text in updates.items():
    p=ROOT/'md'/name;p.write_text(header+text+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
p=ROOT/'md/MOTION_FORMAT.md'
p.write_text(p.read_text(encoding='utf-8')+'\n\n## MVP4 추가 경계 (v0.7.0)\n\n'
 '위 MVP3 위치 스키마는 그대로 유지하며 bone_rotations=null도 변경하지 않는다. '
 '별도 motion/animation-<id>/animation.json의 schema는 standard_bone_animation_v1. '
 'skeleton은 변경 없는22본 정의, bone_names는 같은 순서, fps는 원본 nominal fps, Blender 프레임은 frame_index+1. '
 '각 프레임은 timestamp/segment/scene과 local_quaternions_wxyz, local_locations_m, bone_status를 포함한다. '
 '회전은 Blender PoseBone.matrix_basis 기준 부모/rest 상대 단위 Quaternion(wxyz), 위치는 같은 basis의 미터 단위 위치. '
 'M3의 분리된 attachment 위치 보존을 위해 로컬 위치 채널이 포함되므로 회전만 재생하면 완전히 같은 head가 되지 않을 수 있다. '
 'JSON의 누락 quaternion/location은 null, .blend는 부모/rest fallback을 쓰므로 그 부분의 정확한 복원으로 보지 않는다. '
 '전체 미검출은 mesh/armature 숨김 키로 구분. 유효구간 q/-q 부호연속·경계 초기화, CONSTANT 샘플 키프레임, '
 'SLERP 시간 필터 미적용. source/raw provenance는 기존 motion 파일 및 새 report의 motion/solver/rig SHA로 연결. '
 'report.status=completed와 해당 .blend/.json이 있어야 성공. 실패 로그/부분 파일은 완료 결과가 아니다. '
 '해당 Blender22본 rest 규격용 로컬 회전이며 엔진별 회전/FBX 리타게팅 규격으로 동일시하지 않는다.\n',encoding='utf-8')
(ROOT/'MVP요약/MVP4_본애니메이션_구현요약.md').write_text(header+common+usage+verification+limits,encoding='utf-8')
for filename in ('README.md','HOME_TRANSFER.md'):
    p=ROOT/filename;p.write_text('# 최신 MVP4 v0.7.0\n\n'+usage+limits+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
n=max(int(p.name[4:]) for p in (ROOT/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=ROOT/'진행상황'/f'case{n}';case.mkdir()
for name in ('CURRENT_TASK.md','PROGRESS.md','ISSUES.md','PROJECT.md'):
    src=ROOT/'md'/name;shutil.copyfile(src,case/name)
    assert hashlib.sha256(src.read_bytes()).digest()==hashlib.sha256((case/name).read_bytes()).digest()
evidence={'version':'0.7.0','tests_passed':66,'skipped':1,'compileall':'PASS','blender_reopen':results,
 'review':['correctness: rest/local matrices, full head/direction reconstruction and missing reappearance',
           'architecture: optional Blender backend/app worker, unchanged M2/M3 schemas and 22-bone rig',
           'security/regression: argument array, owned child termination, timeout, provenance, unique output, isolated GUI checks'],
 'md_archive':case.name,'gpu_inference':False,'user_visual_review_pending':True,
 'smoothing':False,'engine_import_verified':False}
(e/'verification.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
outdir=ROOT/'snapshots/v0.7.0 MVP';outdir.mkdir();target=outdir/'m4-blender-animation-v0.7.0.zip'
extras=[ROOT/'app/animation_job.py',ROOT/'tools/animate_reference_rig.py',ROOT/'tests/test_animation_job.py',
 Path(__file__),ROOT/'validation/verify_m4_blender.py',ROOT/'validation/run_m4_validation.py',ROOT/'validation/render_m4_preview.py',
 ROOT/'MVP요약/MVP4_본애니메이션_구현요약.md',*case.glob('*.md'),*[p for p in e.iterdir() if p.is_file()],
 *[p for d in ('synthetic-example','LongSword-example','preview') for p in (e/d).glob('*') if p.is_file()]]
with zipfile.ZipFile(ROOT/'snapshots/v0.6.0 MVP/m3-standard-motion-skeleton-v0.6.0.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
    seen=set()
    for info in old.infolist():
        name=info.filename
        if '__pycache__' in name or name.endswith('.pyc'):continue
        p=ROOT/name
        z.writestr(name,p.read_bytes() if not name.startswith('진행상황/') and p.is_file() else old.read(info));seen.add(name)
    for p in extras:
        name=p.relative_to(ROOT).as_posix()
        if name not in seen:z.write(p,name);seen.add(name)
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    for p in [ROOT/'app/gui.py',*extras]:assert z.read(p.relative_to(ROOT).as_posix())==p.read_bytes()
    count=len(z.infolist())
with target.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
meta={'version':'0.7.0','files':count,'bytes':target.stat().st_size,'sha256':sha,'md_archive':case.name,
 'm4_local_quaternions':True,'blender_animation':True,'smoothing':False,'user_visual_review_pending':True,
 'unity_import_verified':False,'unreal_import_verified':False}
(outdir/'snapshot.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
print(json.dumps(meta),flush=True)
