"""Freeze verified crouch support and archive the current four MD files once."""
from pathlib import Path
import json,hashlib,re,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1];e=ROOT/'validation/ground-v076'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
results=json.loads((e/'results.json').read_text(encoding='utf-8'))
for item in results:
    for kind in ('reopen','fractional'):
        assert json.loads((e/f'{item["label"]}-{kind}.json').read_text(encoding='utf-8')).get('passed',False)
status=json.loads((ROOT/'validation/dance-v074/status.json').read_text(encoding='utf-8'))
assert sha(Path(status['source']))==status['source_sha256']
motion=Path(status['motion']);data=json.loads(motion.read_text(encoding='utf-8'))
assert sha(motion.parent.parent/'sam3d.json')==data['raw_sha256']
assert sha(Path(status['blend']))==sha(ROOT/'validation/dance-v074/example/animation.blend')
comparison=json.loads((e/'comparison.json').read_text(encoding='utf-8'))
assert comparison['maximum_ankle_step_m']<=comparison['baseline_maximum_ankle_step_m']+1e-7
assert all(abs(z-.07)<1e-5 for row in comparison['crouch_new_ankle_z_m'] for z in row)
heading='## 2026-10-21 / MVP4 v0.7.6 웅크림 접지·골반 높이\n\n'
common=('사용자 v0.7.5 빠른 후보 추론 속도개선 확인 후 우선순위1 접지 작업. '
        '다음 순서는 2루트 이동·높이 → 4잔떨림 → 5비틀림·긴 가림, 3옷/머리카락은 후순위 유지.\n'
        'v0.7.6 correction.revision=5: 기존 3D 발높이 기반 접지가 놓치는 양다리 웅크림에 '
        '동일 추출 packet의 2D 발목·발끝·골반 투영좌표를 보조 근거로 사용한다. '
        '양 무릎 굽힘≥30도, 접지 seed의 영상 바닥 근처, 발 대비 골반 하강, 최소0.1초 조건에서 '
        '골반을 낮추고 고정 본 길이 IK로 발목0.07m/발끝0.03m를 맞춘다. '
        '새 inferred_ground_support는 수직 지지만 적용하고 XY를 고정하지 않아 회전·바닥 이동을 허용한다. '
        '이륙/조건해제 후 추가 골반 오프셋을 해제하며 누락·컷·추적구간·화면밖 발에는 확장하지 않는다. '
        '새 지지 상태도 Blender 발 roll의 바닥 기준 처리에 포함했다.\n')
usage=('기존 프로그램 경로 연결 완료. 프로그램 재시작 → 결과목록에서 영상 선택 → Blender 애니메이션 저장. '
       '기존 추출을 재사용하고 새 animation-<id>에 저장하므로 GPU 재추출 불필요. '
       'M3 motion.json/원시 결과/기존 .blend를 덮어쓰지 않는다. '
       'app.animation_job은 motion의 input_sha256과 정확히 일치하는 원본/후처리 packet만 읽고 '
       '프레임·좌표를 검증한다. 근거가 없으면 기존 3D 접지만 사용하며, 사용한 근거의 SHA와 생성후 무결성을 검사한다. '
       'M3 규격/22본·모델·의존성·GPU 경로는 그대로다.\n')
checks=('검증 고유76 PASS/권한 opt-in1 SKIP, compileall PASS. '
        '비GUI core33+기존 SAM/자동후처리/5분입력/늦은등장40+격리실제GUI3. '
        '웅크림 수직지지·XY비고정·본길이·발차기/공중굽힘·웅크린뒤 이륙·화면밖 발·누락/컷·근거SHA/프레임검사 통과. '
        '춤411/LongSword445/합성80 프레임 실제 Blender 새저장·재오픈과 fractional SLERP·분절경계 검증 통과. '
        '춤175~185프레임 발목Z기존0.26~0.39m에서0.07m, 골반도 함께 하강. '
        '춤 최대 발목1프레임 이동0.39127m는 기존과 동일(빠른 발차기), LongSword0.23434m. '
        '춤 새 지지123프레임, 모든접지 정답검증을 뜻하지 않음. 원본영상/원시JSON/M3와 기존Blender 보존 확인. '
        '자체3차검토 완료: 조건/접지해제/본길이, core와 파일근거 경계, provenance·취소·기존경로/누락 회귀.\n')
issues=('M4-GROUND-CROUCH-001 PARTIAL / 지정 춤 구간 수정·검증. '
        '확인 원인: 고정골반에서 정규화한3D 발높이가 웅크림을 발들기로 오인해 지지가 풀림. '
        '최초 Blender 재오픈 검사에서 새 inferred_ground_support를 planted 발 roll 조건에 빠뜨려 '
        '골격점이 맞아도 proxy밑면이 기준을 벗어남을 발견; 동일 바닥roll 분기에 포함 후 재검증 통과. '
        '검증 실행기 합성누락 None 좌표를 바로 np.array로 변환해 실패한 부분은 NaN triplet으로 명시변환 후 '
        '기존 검증파일을 SHA확인해 재사용하여 재검증했다. '
        '혼합 GUI 테스트 한 실행에서 tkdnd 로딩 실패(QA-002 재현)는 별도 Python 프로세스로 분리해 3개 모두 통과. '
        '제품 실패/검증 실행기 실패를 구분하며 실패 로그도 유지한다.\n')
limits=('한계: 2D 근거도 모델 투영값이며 실제 바닥/접지 라벨·카메라 보정값이 아니다. '
        '평면에서 크게 벗어나는 이동·카메라 이동/줌·작은 도약·가림/오추정에는 한계가 있다. '
        '전 구간 양발을 바닥에 강제 고정하지 않으며 실제 점프높이/월드궤적 복원은 아직 미완료. '
        '사용자 새 .blend 시각확인 대기. 다음 작업2에서 실제 이동·높이 추정의 제한을 다룬다.\n')
current=heading+'Milestone M4 / 우선순위1 웅크림 접지 구현·검증, 사용자 새 결과 확인 대기.\n'
current+='Goal: 발을 바닥에 둔 웅크림의 골반하강을 복원하고 발차기/공중자세·기존 결과를 보존. Scope: core/motion/correction.py, app/animation_job.py, Blender planted 상태/GUI 버전, 관련 테스트.\n'
current+='Acceptance: 175~185프레임 양발0.07m·골반하강, XY비고정·이륙/누락/본길이·Blender밑면/보간·입력SHA보존 검증.\n'+common+usage+checks+limits
(ROOT/'md/CURRENT_TASK.md').write_text(current,encoding='utf-8')
for name in ('PROGRESS.md','PROJECT.md','ISSUES.md'):
    p=ROOT/'md'/name;p.write_text(heading+(issues if name=='ISSUES.md' else '')+common+usage+checks+limits+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
p=ROOT/'md/MOTION_FORMAT.md'
p.write_text(p.read_text(encoding='utf-8')+'\n\n## v0.7.6 영상근거 웅크림 지지\n\n'
    'M3 standard_motion_positions_v1은 그대로 유지한다. export 시 동일 input SHA의 native MHR70 image_joints에서 '
    '발목13/14, 발끝15·16/18·19 평균, 골반9·10 평균을 보조 입력으로 읽는다. '
    'correction.revision=5, frames[].image_ground_support=[bool,bool], feet의 새 상태 inferred_ground_support는 '
    '수직 접지만 추정하고 XY잠금을 뜻하지 않는다. 원래 inferred_contact는 XY잠금을 유지한다. '
    '부드러운 진입 중에는 기존 collision_transition 표기를 사용한다. '
    'metadata image_ground_evidence_used와 crouch_support, 내보내기 report ground_evidence_sha256을 포함한다. '
    '유효연속구간 안의 양발접지 seed≥0.1초(최소3프레임), 영상5프레임 median, '
    '발목/발끝 각각 seed median Y의 -0.03~+0.12×영상높이, 양무릎내각<150도, '
    '발대비골반하강>0.035×영상높이, 연속0.1초(최소3프레임)에서만 새 지지. '
    '화면밖/누락/컷 경계를 넘지 않는다. 접지높이0.07/0.03m, 본길이/SLERP 파라미터는 동일. '
    '실측바닥·월드이동·신발형상·전체정답정확도 보장이 아니다.\n',encoding='utf-8')
summary=ROOT/'MVP요약/MVP4_웅크림접지_v076.md'
summary.write_text('# MVP4 v0.7.6 웅크림 접지·골반 높이\n\n'+common+usage+checks+issues+limits+'\n확인파일: validation/ground-v076/dance-example/animation.blend\n',encoding='utf-8')
for name in ('README.md','HOME_TRANSFER.md'):
    p=ROOT/name;p.write_text('# 최신 MVP4 v0.7.6 · 웅크림 접지\n\n'+usage+limits+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
n=max(int(p.name[4:]) for p in (ROOT/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=ROOT/'진행상황'/f'case{n}';case.mkdir()
for name in ('CURRENT_TASK.md','PROGRESS.md','ISSUES.md','PROJECT.md'):
    p=ROOT/'md'/name;shutil.copyfile(p,case/name);assert sha(p)==sha(case/name)
verification={'version':'0.7.6','tests_passed':76,'skipped':1,'compileall':'PASS','blender_cases':results,
              'md_archive':case.name,'source_raw_m3_and_previous_blend_preserved':True,'gpu_inference':False,
              'user_visual_review_pending':True,'ground_truth_contact_accuracy':False}
(e/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
snapshot=ROOT/'snapshots/v0.7.6 MVP';snapshot.mkdir();target=snapshot/'m4-crouch-ground-v0.7.6.zip'
extras=[Path(__file__),summary,*case.glob('*.md'),*[p for p in e.rglob('*') if p.is_file()],
        *[ROOT/'validation'/name for name in ('inspect_ground_v076.py','check_ground_v076.py','run_ground_v076.py','review_ground_v076.py')]]
with zipfile.ZipFile(ROOT/'snapshots/v0.7.5 MVP/m4-candidate-speed-v0.7.5.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as archive:
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
    for p in extras+[ROOT/'core/motion/correction.py',ROOT/'app/animation_job.py',ROOT/'tools/animate_reference_rig.py',ROOT/'tests/test_motion_correction.py',ROOT/'tests/test_animation_job.py']:
        assert archive.read(p.relative_to(ROOT).as_posix())==p.read_bytes()
with target.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
meta={'version':'0.7.6','bytes':target.stat().st_size,'files':len(names),'sha256':digest,'md_archive':case.name,'tests_passed':76,'skipped':1,'user_visual_review_pending':True}
(snapshot/'snapshot.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');print(json.dumps(meta),flush=True)
