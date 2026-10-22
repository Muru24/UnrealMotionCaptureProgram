"""Record the completed real editor inspection; archive current four MD files once."""
from pathlib import Path
import json,re,hashlib,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1];E=ROOT/'validation/ue58-visual'
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
project=json.loads((E/'project.json').read_text(encoding='utf-8'));folder=Path(project['folder'])
report=json.loads((E/'import-report.json').read_text(encoding='utf-8'))
assert report['passed'] and report['bone_count']==22
assert (E/'end-frame.png').is_file()
exports=json.loads((ROOT/'validation/m5-release/exports.json').read_text(encoding='utf-8'))
item=next(x for x in exports if x['label']=='LongSword');out=Path(item['export']);signature=json.loads((out/'export.json').read_text(encoding='utf-8'))
assert sha(Path(item['source']))==signature['source_blend_sha256']
assert sha(out/'Motion_Unreal.fbx')==signature['file_sha256']['Motion_Unreal.fbx']
state={'status':'visual_playback_confirmed','engine':'Unreal 5.8.1','project':project['project'],
       'asset':'/Game/MotionPreview/ReferenceMotion_Anim','bones':22,'sample_keys':447,'sample_intervals':446,'fps':30,
       'duration_seconds':report['duration_seconds'],'observed_frames':[0,13,17,25,41,111,120,238,446],
       'observed_pose_and_translation_change':True,'camera_follow_mode':'Root Orbit (루트 공전)',
       'raw_and_source_blend_preserved':True,'scope':'LongSword reference proxy only; no target-character retarget',
       'remaining':['map_startup_camera_not_framed','map_static_lighting_rebuild_warning','proxy_materials_display_white','other_clips_not_visually_reviewed_in_UE']}
(E/'visual-report.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
guide=('# MotionCheckUE58 · Unreal5.8 화면 확인\n\n'
       '프로젝트: MotionCheckUE58.uproject\n\n'
       '1. Unreal5.8로 프로젝트를 연다.\n2. Content Drawer(Ctrl+Space) → MotionPreview → ReferenceMotion_Anim을 더블클릭한다.\n'
       '3. 아래 재생 버튼을 누른다. 30fps /447키 /약14.87초다.\n'
       '4. 원근 메뉴 → 따라가기 모드 → 루트 공전을 선택하면 이동하는 몸을 화면 중앙에서 볼 수 있다.\n\n'
       '레벨 Preview에서는 Outliner의 Motion Reference를 선택하고 F로 화면을 맞춘다. '
       '기본 레벨 조명 재빌드 경고와 시작 카메라 초기값은 아직 남아 있다. '
       '애니메이션 에디터의 환경 조명에서는 리그가 보이며 실제 재생을 확인했다.\n\n'
       '기준 BoneProxy용이며 제작용 캐릭터에 리타깃한 결과는 아니다. 원본 추론과 .blend는 보존했다.\n')
(folder/'확인방법.md').write_text(guide,encoding='utf-8')
bundle=E/'MotionCheckUE58_project.zip'
with zipfile.ZipFile(bundle,'x',zipfile.ZIP_DEFLATED) as archive:
    sources=[Path(project['project']),folder/'확인방법.md',*[p for directory in ('Content','Config') for p in (folder/directory).rglob('*') if p.is_file()]]
    for p in sources:archive.write(p,p.relative_to(folder).as_posix())
with zipfile.ZipFile(bundle) as archive:assert archive.testzip() is None
header='## 2026-10-22 / 새 Unreal5.8 프로젝트 실제 에디터 재생 확인\n\n'
text=('사용자 요청으로 기존 검증 프로젝트와 별개의 새 MotionCheckUE58 프로젝트를 생성하고 Unreal5.8.1 실제 GUI에서 열었다. '
      'LongSword의 M4 기준 스켈레톤 FBX를 임포트해 Skeleton/SkeletalMesh/AnimSequence 및 바닥/조명 맵을 저장했다. '
      '애니메이션 에디터의 ReferenceMotion_Anim에서30fps·447키/446구간·14.86667초를 확인했고 '
      '0/중간/446 끝 프레임과 실제 재생 중 팔·다리 자세 및 루트 이동 변화, 반복 재생을 확인했다. '
      '동작 정확도/완전한 접지/다른 캐릭터 리타깃의 정답검증을 뜻하지 않는다.\n'
      '고정 카메라에서는 이동하는 몸이 화면 밖으로 나가므로 원근 → 따라가기 모드 → 루트 공전을 적용했다. '
      '에디터 애니메이션 창을 열린 상태로 남겼다. source .blend/FBX SHA 보존 확인, GPU 재추론/앱 보정 코드 변경 없음.\n'
      f"프로젝트: {project['project']}\n"
      '확인자료: validation/ue58-visual/visual-report.json, end-frame.png, MotionCheckUE58_project.zip 및 프로젝트 확인방법.md.\n'
      '이슈/조치: 처음 긴 이름 MotionCaptureCheck_UE58에서20자 제한 경고가 떠 짧은 새 이름으로 프로젝트를 생성했다. '
      '긴 이름의 시험 폴더는 보존하고 해당 에디터 창만 닫았다. 화면제어 도구 실행 승인 시간 초과는 사용자 승인 뒤 진행했으며, '
      '파일 선택 모달 제어가 불안정하여 승인된 Unreal 프로젝트 경로 실행 옵션으로 열고 UI로 재생을 확인했다.\n'
      '남음: 레벨 시작 카메라가 메시 안쪽인 초기값과 정적 조명 재빌드 경고는 남아 있다. '
      '애니메이션 에디터 환경 조명에서는 재생 가능. FBX proxy 머티리얼은 화면에서 흰색으로 보였으며 좌우/몸통 컬러 복원은 미완료. '
      '이번 실제 UI 시각검사는 LongSword 기준 리그1개이며 전체6영상 UE 시각검증·Unity·임의 캐릭터 리타깃은 미검증이다. '
      'M5 진행 중, 기존 v0.8.0 제품 MVP 유지.\n')
for name in ('CURRENT_TASK.md','PROGRESS.md','PROJECT.md','ISSUES.md'):
    p=ROOT/'md'/name;p.write_text(header+text+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
number=max(int(p.name[4:]) for p in (ROOT/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=ROOT/'진행상황'/f'case{number}';case.mkdir()
for name in ('CURRENT_TASK.md','PROGRESS.md','PROJECT.md','ISSUES.md'):
    p=ROOT/'md'/name;shutil.copyfile(p,case/name);assert sha(p)==sha(case/name)
state.update(md_archive=case.name,project_bundle_sha256=sha(bundle));(E/'visual-report.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'project':project['project'],'archive':str(bundle),'md_archive':case.name}),flush=True)
