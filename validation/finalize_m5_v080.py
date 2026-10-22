"""Freeze M5 first engine-preview checkpoint, preserving the M4 product snapshot."""
import json,hashlib,re,shutil,zipfile,compileall
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];E=ROOT/'validation/m5-release'
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
exports=json.loads((E/'exports.json').read_text(encoding='utf-8'))
ue=json.loads((E/'unreal-report.json').read_text(encoding='utf-8'))
comparison=json.loads((E/'pose-comparison.json').read_text(encoding='utf-8'))
assert ue['passed'] and ue['reopened_asset_verified'] and ue['bone_count']==22 and comparison['passed']
for item in exports:
    assert json.loads((E/f"{item['label']}-roundtrip.json").read_text(encoding='utf-8'))['passed']
    folder=Path(item['export']);r=json.loads((folder/'export.json').read_text(encoding='utf-8'))
    assert r['exporter_sha256']==sha(ROOT/'tools/export_engine_fbx.py')
    assert r['source_blend_sha256']==sha(Path(item['source']))
    assert all(sha(folder/name)==value for name,value in r['file_sha256'].items())
assert compileall.compile_file(str(ROOT/'app/engine_export_job.py'),quiet=1)
header='## 2026-10-22 / MVP5 v0.8.0 엔진용 FBX·Unreal 기준 리그 미리보기1차\n\n'
common=('사용자가 Norma 제외6영상 결과를 긍정 확인하고 다음 작업 진행을 요청했다. M4 결과 검증을 정리하고 '
        '계획의 M5 Unreal Motion Preview 첫 단계에 진입했다. M5.5 분석/Mapping/Profile/임의 캐릭터 Retarget은 아직 시작하지 않았다.\n'
        '새 app.engine_export_job + tools/export_engine_fbx는 저장된 M4 animation.blend/animation.json을 읽어 '
        'animation-<id>/engine-<id>/Motion_Unreal.fbx, Motion_Unity.fbx 및 export.json을 생성한다. '
        '새 GUI 버튼 Unreal · Unity FBX 저장을 기존 worker/취소/busy 경로에 연결했다. '
        '기존 Blender 버튼 유지, 원시/M3/보정/이전Blend 보존, 모델·GPU 재추론/의존성 추가 없음.\n'
        '정수 샘플 경계의 엔진 호환성을 위해 초 단위 시간을 유지하면서30fps로 리샘플한다. '
        '원본 길이와 FBX 길이 차이는 종료점 반올림의 최대1/60초이며 source_fps/source_duration/fbx_duration을 기록한다. '
        '22본과 rigid BoneProxy 메쉬를 출력하며 별도 타깃 캐릭터에 맞춘 결과는 아니다.\n')
usage=('사용: StartPrototype.cmd로 재시작 → 기존 결과 선택 → Unreal · Unity FBX 저장. '
       'Unreal에는 Motion_Unreal.fbx를 Skeletal Mesh+Animation으로 임포트한다. Unity 파일은 생성·Blender 왕복만 확인했으며 Unity 실제 임포트는 미검증이다.\n'
       '별도 Unreal5.8.1 테스트 프로젝트: validation/m5-release/MotionPreview/MotionPreview.uproject. '
       '열면 /Game/MotionPreview/Preview에 기준 리그·평면 지면·조명이 있다. Content Browser에서 '
       'ReferenceMotion_Anim을 열어 Play로 확인한다. live 영상 동기화/임의 프로젝트 자동 연결/캐릭터 리타깃은 미구현.\n')
checks=('검증99 PASS/기존 opt-in1 SKIP: 비GUI55+기존40+격리GUI4, compileall PASS. '
        '새 export 취소/잘못된schema/인자배열/입력SHA/출력SHA/프로그램 버튼·busy 연결과 기존 M4 경로 회귀 통과. '
        'LongSword/춤/짧고긴누락·컷 합성3개×2종FBX=6개 Blender 재임포트,22본·평가된 관절위치 보존 확인(최대1mm 미만). '
        'Unreal5.8.1 실제 import+저장+다시 읽기에서 SkeletalMesh/Skeleton/AnimSequence,22본·447sample keys/446intervals·14.86667초 확인. '
        f"4개 시점 원본 대비 UE 관절위치 최대오차 {comparison['maximum_position_error_cm']:.8f}cm. "
        '첫 자세에서 정규직교 좌표변환을 한 번 추정해 다른3시점에 고정 적용했고 Zup/미터→센티미터100배 확인. '
        '이는 변환 보존 검사이며 동작 정답률/타깃 리타깃/화면 품질 검증을 뜻하지 않는다.\n')
issues=('원인/조치: Blender FBX 재임포트가 pelvis를 connected bone으로 추정해 수직 local translation을 무시했고 '
        'anim_offset 기본값으로1프레임 밀렸다. 검증 importer를 연결 해제·offset0으로 맞추니 원본과 일치했다. '
        '소스 .blend나M4보정은 바꾸지 않았다. 누락 visibility 애니메이션이 첫FBX bake 중 선택을 해제하여 두번째FBX가 비는 문제는 '
        'export 전 메모리 복제본의 visibility FCurve만 제거해 해결했다. 원본의 숨김/누락 정보는 보존된다. '
        'Unreal sandbox 실행이 로그/보고서 없이0종료하여 성공으로 취급하지 않았으며 승인된 로컬 실행으로 실제 보고서·자산을 검증했다.\n'
        '이전 일괄 작업의 북북춤 checkpoint replace WinError5는 임시 Windows 파일 접근 충돌로 기록한다. '
        '기본/후보 추론을 보존해 후처리를 재개했고6개 완료했다. 배치 기록 교체 재시도를 도구에 추가했다.\n')
limits=('한계: FBX에는 관절별/전신 누락의 유효성 flag와 객체 숨김을 신뢰성 있게 전달하지 않는다. '
        '누락 구간은 M4의 부모/rest fallback 또는 hold가 포함될 수 있으며 복원 동작이 아니다. '
        'export.json missing_spans/missing_pose_frames 및 원본 animation.json을 함께 확인해야 한다. '
        'M5 긴누락 클립 분리·엔진 표시 정책, 전체6영상 엔진 재생 시각확인, Unity 임포트, 엔진 화면 자동열기·영상 동기화는 남았다. '
        '이번 UE 검증은 NullRHI commandlet이므로 화면의 조명/시점/재생 품질은 사용자 확인 대기다. '
        '스킨은 기존 bone proxy이며 제작용 캐릭터가 아니다. M5 전체 완료 선언 없이 첫 체크포인트로 보관한다.\n')
review=('자체3차검토: ①초/프레임·좌표/단위·root/pelvis translation·22본·원본SHA, '
        '②누락 visibility/FBX 선택·2형식 출력·별도project의실제UE저장/재열기, '
        '③worker취소/실패/출력완료검사·기존GUI 경로·코드SHA/기존MVP보존 확인.\n')
current=header+'Milestone M5 IN_PROGRESS / FBX export + isolated Unreal reference preview first checkpoint.\n'
current+='Goal: 보정된 M4를 엔진에 전달하고 기준 리그로 미리보기 준비. Scope: engine_export_job/FBX·UE scripts/GUI 및 검증.\n'
current+='Acceptance: 프로그램 버튼·취소·원본 보존, 두FBX22본/위치 왕복, 실제UE5.8 import/reopen/시간·단위 검사.\n'+common+usage+checks+issues+limits+review
(ROOT/'md/CURRENT_TASK.md').write_text(current,encoding='utf-8')
for name in ('PROGRESS.md','PROJECT.md','ISSUES.md'):
    p=ROOT/'md'/name;p.write_text(header+common+usage+checks+(issues if name=='ISSUES.md' else '')+limits+review+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
p=ROOT/'md/MOTION_FORMAT.md';p.write_text(p.read_text(encoding='utf-8')+'\n\n## v0.8.0 Engine FBX export\n\n'+common+limits+
    'Motion JSON/schema/22본은 변경하지 않는다. export.json은 FBX 파생 파일의 manifest이며 Core 경계를 대체하지 않는다.\n',encoding='utf-8')
summary=ROOT/'MVP요약/MVP5_엔진미리보기1차_v080.md'
summary.write_text('# MVP5 v0.8.0 엔진 미리보기1차\n\n'+common+usage+checks+issues+limits,encoding='utf-8')
guide=E/'사용방법.md';guide.write_text('# Unreal 미리보기 확인\n\n1. MotionPreview/MotionPreview.uproject를 Unreal5.8로 연다.\n'
    '2. Content Browser → MotionPreview → ReferenceMotion_Anim을 더블클릭한다.\n3. 애니메이션 에디터에서 Play를 누른다.\n\n'+usage+limits,encoding='utf-8')
for name in ('README.md','HOME_TRANSFER.md'):
    p=ROOT/name;p.write_text('# 최신 MVP5 v0.8.0 · 엔진용 FBX/기준 미리보기1차\n\n'+usage+limits+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
n=max(int(p.name[4:]) for p in (ROOT/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=ROOT/'진행상황'/f'case{n}';case.mkdir()
for name in ('CURRENT_TASK.md','PROGRESS.md','PROJECT.md','ISSUES.md'):
    p=ROOT/'md'/name;shutil.copyfile(p,case/name);assert sha(p)==sha(case/name)
verification={'version':'0.8.0','milestone':'M5_IN_PROGRESS','tests_passed':99,'skipped':1,'md_archive':case.name,'unreal_import_reopen_passed':True,'fbx_roundtrips':6,'unreal_visual_review_pending':True,'unity_import_verified':False,'source_animation_preserved':True}
(E/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
folder=ROOT/'snapshots/v0.8.0 MVP';folder.mkdir();target=folder/'m5-engine-preview-v0.8.0.zip'
extra=[ROOT/'app/engine_export_job.py',ROOT/'tools/export_engine_fbx.py',ROOT/'tools/unreal_import_preview.py',ROOT/'tools/unreal_verify_preview.py',ROOT/'tests/test_engine_export_job.py',summary,*case.glob('*.md')]
extra+=[p for p in E.rglob('*') if p.is_file() and not any(x in p.parts for x in ('Saved','Intermediate','DerivedDataCache'))]
extra+=[ROOT/'validation'/name for name in ('finalize_m5_v080.py','prepare_m5_release.py','check_m5_release.py','measure_m5_unreal.py','verify_engine_fbx_blender.py')]
for item in exports:extra+=[p for p in Path(item['export']).iterdir() if p.is_file()]
with zipfile.ZipFile(ROOT/'snapshots/v0.7.9 MVP/m4-twist-gaps-v0.7.9.zip') as base,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as archive:
    names=set()
    for info in base.infolist():
        name=info.filename
        if '__pycache__' in name or name.endswith('.pyc'):continue
        p=ROOT/name;archive.writestr(name,p.read_bytes() if not name.startswith('진행상황/') and p.is_file() else base.read(info));names.add(name)
    for p in extra:
        name=p.relative_to(ROOT).as_posix()
        if name not in names:archive.write(p,name);names.add(name)
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    for p in extra+[ROOT/'app/gui.py']:assert archive.read(p.relative_to(ROOT).as_posix())==p.read_bytes()
metadata={**verification,'bytes':target.stat().st_size,'files':len(names),'sha256':sha(target)}
(folder/'snapshot.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8');print(json.dumps(metadata),flush=True)
