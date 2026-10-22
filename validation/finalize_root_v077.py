"""Archive the verified image/contact root estimates; do not re-run blindly."""
from pathlib import Path
import json,hashlib,re,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1];e=ROOT/'validation/root-v077-release'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
results=json.loads((e/'results.json').read_text(encoding='utf-8'))
for item in results:
    for kind in ('reopen','fractional'):
        assert json.loads((e/f'{item["label"]}-{kind}.json').read_text(encoding='utf-8'))['passed']
    report=json.loads((Path(item['blend']).parent/'report.json').read_text(encoding='utf-8'))
    for path,key in ((ROOT/'core/motion/correction.py','correction_sha256'),(ROOT/'core/motion/root_motion.py','root_solver_sha256'),(ROOT/'app/root_motion_job.py','root_camera_job_sha256')):
        assert sha(path)==report[key]
status=json.loads((ROOT/'validation/dance-v074/status.json').read_text(encoding='utf-8'))
assert sha(Path(status['source']))==status['source_sha256']
motion=Path(status['motion']);data=json.loads(motion.read_text(encoding='utf-8'))
assert sha(motion.parent.parent/'sam3d.json')==data['raw_sha256']
assert sha(Path(status['blend']))==sha(ROOT/'validation/dance-v074/example/animation.blend')
heading='## 2026-10-21 / MVP4 v0.7.7 영상·접지 결합 이동·높이 추정\n\n'
common=('우선순위2 이동·높이 추정 확장. 6속도 사용자 개선확인, 1웅크림 접지 유지. '
        '다음 4잔떨림 → 5비틀림·긴 가림, 3옷/머리카락 오추정은 후순위.\n'
        'v0.7.7 correction.revision=6: 기존 접지 루트에 영상 골반·발 투영과 원시 SAM pred_cam_t 깊이를 결합했다. '
        '정확한 원본영상/원시JSON SHA가 일치할 때만 CPU로 영상을 읽고, 대상 bbox를 제외한 배경 특징의 '
        '전후 optical flow 및 RANSAC 유사변환으로 pan/roll/zoom을 보정한다. 3D SLAM은 아니다. '
        '보정 투영좌표와 zoom 보정 모델 깊이에서 골반 이동 후보를 만들고, 접지 제약과 속도 제한으로 결합한다. '
        '카메라 epoch/장면/누락 경계의 기준을 재설정해 이어 붙이지 않는다. '
        '배경/원본/발 근거가 없거나 부적합한 구간은 기존 접지 계산을 유지한다.\n')
air=('양발 발목·발끝 투영 높이가 바닥 기준보다0.055m, 골반이0.06m 이상 올라가며 최소0.06초 지속되고 '
     '3D 다리도 유효한 경우만 estimated_airborne으로 판단한다. 이 구간의 잘못된 접지 잠금을 해제하고 '
     '루트Z도 움직인다. 착지 전환은 부드럽게 복귀하며, 이미지/3D 모순으로 발이 바닥 아래로 내려가지 않도록 '
     '공중 최소 여유0.015m를 둔다. 바닥 위 수평 발 이동은 수직 지지만 남기고 XY잠금을 해제한다. '
     '한쪽 발차기·웅크림을 양발 점프로 취급하지 않는다.\n')
usage=('프로그램 경로 연결 완료. 재시작 후 기존 결과 선택 → Blender 애니메이션 저장. '
       '기존 추론을 재사용하며 새 animation-<id>에 저장하고, 오른쪽 3D에도 보정본을 표시한다. '
       '카메라 보조분석에는 원본영상이 필요하지만 GPU 재추출은 필요 없다. 원본이 없으면 접지 보정으로 대체한다. '
       '원시/기존 M3 motion.json·이전 .blend·22본/모델/의존성과 빠른 후보 추론 옵션을 유지했다.\n')
checks=('검증 고유88 PASS/기존 권한 opt-in1 SKIP, compileall PASS. '
        'core/app33+새 루트12+기존회귀40+격리GUI3. 실제 합성MP4로 수평/수직 pan·zoom·느린 pan과 '
        '인물 이동을 분리하고, 점프/착지·한발들기·웅크림 유지·누락/카메라epoch·장면경계·본길이·수평이동·'
        '투영 불일치 시 바닥관통 방지·원본변조/취소를 검증했다. '
        '춤411/LongSword445/합성80 프레임 새 Blender 저장·실제 재오픈 head/Quaternion·proxy밑면 및 '
        'fractional SLERP/누락·컷 경계 검증 통과. 춤175~185프레임 발목0.07m 유지. '
        '춤 배경분석 유효386/411, 루트새근거380프레임, 공중추정147~153프레임, 루트Z범위약0.181m. '
        'LongSword는 유효164/445, 새근거145프레임만 적용하고 나머지 구간은 기존 계산을 유지했다. '
        '이 수치들은 실측 이동거리/접지 정확도/점프 정답률이 아니다. '
        '새 GPU추론 없음; 춤 CPU 분석+보정 표본약3.8초, 전체GPU 처리속도는 재측정하지 않았다. '
        '원본영상/원시JSON/M3·기존Blender SHA 보존 및 새 root/camera 코드 SHA도 export report에 기록·확인.\n')
review=('자체3차검토: 접지/공중/착지·본길이/바닥 여유, root helper의 순환 의존성 제거 및 기존 fallback 보존, '
        '해시/로컬경로/디코더timeout·취소/18,000프레임·최대1920해상도/배경거부 경계 확인. '
        '미세 pan이 무시되어 인물 이동으로 누적되지 않도록 정지 deadband를 축소하고 느린 pan 테스트를 추가했다. '
        '최종 guard와 코드 SHA 반영 후 release3종을 다시 저장·검증했으며 중간 실험 결과는 보존했다.\n')
limits=('한계: 기준 스켈레톤/모델 크기와 기본 FOV를 사용한 추정이며 실제 인물 키·미터 이동거리·지면을 보정한 '
        '측량 결과가 아니다. 깊이는 모델 추정이라 자세·원근·카메라 pitch/3D parallax·움직이는 배경·반사에 '
        '오차가 남는다. 배경 특징 부족/가려진 발/프레임 밖 발은 새 근거가 제한된다. 작은 도약·긴 가림·'
        '모든 카메라 이동과 실제 월드궤적 복원은 미해결. 사용자 시각확인 대기, 다음은4잔떨림 보정.\n')
current=heading+'Milestone M4 / 우선순위2 구현·검증, 사용자 새 Blender 확인 대기.\n'
current+='Goal: 배경 카메라 움직임을 구분하며 루트 수평/깊이 후보와 공중 높이를 접지에 결합. Scope: core/motion root/correction, app root/animation, GUI 버전/스켈레톤 안내, 테스트/검증 실행기.\n'
current+='Acceptance: camera pan/zoom을 인물 이동/점프로 오인하지 않음, 점프/착지·웅크림·누락·본길이·원본보존, 실제 Blender 재열기/보간 검증.\n'+common+air+usage+checks+limits
(ROOT/'md/CURRENT_TASK.md').write_text(current,encoding='utf-8')
for name in ('PROGRESS.md','PROJECT.md','ISSUES.md'):
    p=ROOT/'md'/name;issue='M4-ROOT-001 PARTIAL: 접지-only 루트의 이동 누락·공중 Z부재를 영상/배경/모델 관측으로 확장. 지정영상·합성 회귀 통과, 비보정 카메라/실제미터 정확도는 미완료.\n' if name=='ISSUES.md' else ''
    p.write_text(heading+issue+common+air+usage+checks+review+limits+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
p=ROOT/'md/MOTION_FORMAT.md'
p.write_text(p.read_text(encoding='utf-8')+'\n\n## v0.7.7 영상·접지 루트\n\n'
    'M3 schema는 유지한다. correction.revision=6, 새 파생 root_motion_kind=image_and_contact_estimate '
    '(새 근거가 없으면 contact_constraint_estimate). frames[]의 image_root_drive, image_moving_support[2], '
    'estimated_airborne은 근거 적용/예측 여부이며 정확도 confidence가 아니다. feet에 estimated_airborne 추가. '
    '공중 루트Z는 가상 바닥 루트의 위 이동, pelvis는 전체 위치 보정으로 결정된다. '
    '기존 root_xy_soft_speed_limit_mps=1.8는 접지 조정 prior, 영상 후보X/Y 조정은 각각2.5/1.2m/s, '
    '공중Z는3m/s로 별도 제한하므로 합성 후 전체 동작의 hard speed cap이 아니다. '
    'camera 처리: 최대변480 grayscale, 배경 feature≤240, LK forward/back오차<0.8px, '
    'RANSAC inlier≥16·비율≥0.65·XY분포≥화면0.18, median잔차≤0.65px. '
    '단계 scale0.95~1.05/회전3도/이동0.12화면 이내, 누적scale0.5~2/이동0.75화면 이내. '
    '확실하지 않으면 epoch를 끊고 기존 접지를 사용한다. 기본focal=hypot(width,height)는 로컬 '
    'SAM prepare_batch의 기본 intrinsics와 동일. metric projection·깊이는 모델 단위의 추정이다. '
    'export report root_motion_analysis에 유효/거부/epoch 수, source/raw SHA, 모델·스케일 한계를 저장하고 '
    'root_solver_sha256/root_camera_job_sha256를 생성 후 다시 확인한다.\n',encoding='utf-8')
summary=ROOT/'MVP요약/MVP4_이동높이추정_v077.md'
summary.write_text('# MVP4 v0.7.7 영상·접지 결합 이동·높이 추정\n\n'+common+air+usage+checks+review+limits+'\n확인파일: validation/root-v077-release/dance-example/animation.blend\n',encoding='utf-8')
for name in ('README.md','HOME_TRANSFER.md'):
    p=ROOT/name;p.write_text('# 최신 MVP4 v0.7.7 · 이동·높이 추정\n\n'+usage+limits+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
n=max(int(p.name[4:]) for p in (ROOT/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=ROOT/'진행상황'/f'case{n}';case.mkdir()
for name in ('CURRENT_TASK.md','PROGRESS.md','ISSUES.md','PROJECT.md'):
    p=ROOT/'md'/name;shutil.copyfile(p,case/name);assert sha(p)==sha(case/name)
verification={'version':'0.7.7','tests_passed':88,'skipped':1,'compileall':'PASS','blender_cases':results,
    'md_archive':case.name,'gpu_inference':False,'source_raw_m3_previous_blend_preserved':True,
    'user_visual_review_pending':True,'calibrated_world_trajectory':False}
(e/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
folder=ROOT/'snapshots/v0.7.7 MVP';folder.mkdir();target=folder/'m4-image-root-v0.7.7.zip'
extras=[Path(__file__),summary,ROOT/'app/root_motion_job.py',ROOT/'core/motion/root_motion.py',ROOT/'tests/test_root_motion.py',
    *case.glob('*.md'),*[p for p in e.rglob('*') if p.is_file()],
    *[ROOT/'validation'/name for name in ('inspect_root_v077.py','check_root_v077.py','run_root_v077.py','review_root_v077.py')]]
with zipfile.ZipFile(ROOT/'snapshots/v0.7.6 MVP/m4-crouch-ground-v0.7.6.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as archive:
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
    for p in extras+[ROOT/'core/motion/correction.py',ROOT/'app/animation_job.py',ROOT/'app/skeleton_panel.py']:
        assert archive.read(p.relative_to(ROOT).as_posix())==p.read_bytes()
with target.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
meta={'version':'0.7.7','bytes':target.stat().st_size,'files':len(names),'sha256':digest,'md_archive':case.name,
      'tests_passed':88,'skipped':1,'user_visual_review_pending':True}
(folder/'snapshot.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');print(json.dumps(meta),flush=True)
