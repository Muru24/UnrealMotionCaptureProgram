"""Preserve tested Manny checkpoint and current task records once."""
from pathlib import Path
import json,hashlib,shutil,re
ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'validation/manny'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
r=json.loads((E/'report.json').read_text(encoding='utf-8'))
v=json.loads((E/'verification.json').read_text(encoding='utf-8'))
assert r['passed'] and v['passed'] and (E/'playback.png').is_file()
exports=json.loads((ROOT/'validation/m5-release/exports.json').read_text(encoding='utf-8'))
item=next(x for x in exports if x['label']=='LongSword');out=Path(item['export'])
signature=json.loads((out/'export.json').read_text(encoding='utf-8'))
assert sha(Path(item['source']))==signature['source_blend_sha256']
assert sha(out/'Motion_Unreal.fbx')==signature['file_sha256']['Motion_Unreal.fbx']
guide=ROOT/'UnrealProjects/MotionCheckUE58/Manny_확인방법.md'
guide.write_text('# Manny 리타게팅 확인\n\n'
    'MotionCheckUE58.uproject를 Unreal5.8로 연다.\n\n'
    'Content Drawer → MannyMotion → Manny_ReferenceMotion_Anim을 더블클릭하고 재생한다. '
    '기본3인칭 Manny(SKM_Manny_Simple), SK_Mannequin 스켈레톤용 LongSword 애니메이션이다. '
    '30fps,447키,446구간,14.86667초. 원근 → 따라가기 모드 → 루트 공전으로 화면을 맞춘다.\n\n'
    'IK_Motion22와 IK_Manny의8체인(척추/목머리/좌우쇄골/좌우팔/좌우다리)을 '
    'RTG_Motion22_Manny에 연결하고 타깃 기준자세를 자동 정렬한 뒤 베이크했다. '
    '원본22본/FBX/Blend는 유지한다. MannyPreview 레벨은 별도 저장했다.\n\n'
    '손가락/얼굴 추적, 무기 장착,3인칭 이동 AnimBlueprint 교체 및 제품 GUI의 자동 Manny출력은 미구현이다. '
    '본 길이 검사는 구조 보존 검사이며, 발 미끄러짐/관통/손 위치의 시각적 품질은 추가 확인해야 한다.\n',encoding='utf-8')
title='## 2026-10-22 / Manny 기본3인칭 스켈레톤 리타게팅1차\n\n'
body=('사용자 요청: 기준22본 proxy 대신 Unreal 기본3인칭 Manny의 본/메시에 모션 적용. '
      'M5 진행 중이며 사용자 요청으로 Manny 고정 타깃 리타게팅1차를 수행했다. 임의 캐릭터 자동매핑 전체 완료는 아니다.\n'
      '설치된 UE5.8 TemplateResources/High/Characters의 원본 에셋128개를 새 검증 프로젝트의 Content/Characters에 복사했다. '
      'Manny_Simple은 실제 기본 SK_Mannequin 스켈레톤89본을 사용한다. 원본22본 구조는 변경하지 않았다.\n'
      'tools/unreal_retarget_manny.py: source/target IK Rig,8체인,IKRetargeter default5ops,타깃 ChainToChain 기준자세 정렬, '
      'RunBatchRetarget로 /Game/MannyMotion/Manny_ReferenceMotion_Anim 생성·저장. '
      '손가락/얼굴은 추적 데이터가 없으므로 별도 추적동작을 만들지 않는다.\n'
      '검증: 실제 UE5.8.1 commandlet 생성과 별도 재열기 PASS. Manny skeleton 동일,30fps447키/446구간14.86667초. '
      '전체447샘플의 주요15본 좌표 유한값 및8개 팔다리 세그먼트 길이 유지 PASS,시작~끝 root 이동323.31cm. '
      '이 검사는 동작 정답률/접지 품질의 검증은 아니다. 실제 GUI에서 Manny 메시와 머티리얼,팔·다리 자세 변화/몸회전/이동·반복재생 확인. '
      '애니메이션 창을 Manny 결과가 재생되는 상태로 두었다.\n'
      '별도 /Game/MannyMotion/MannyPreview 레벨에 Manny 단일애니메이션 actor/바닥/이동식 조명을 저장했다. '
      '이 레벨은 commandlet 저장 확인이며 GUI 레벨 시각검사는 하지 않았다. 기존 Preview 시작맵은 유지.\n'
      '증거: validation/manny/report.json,verification.json,playback.png,retarget.log,verify.log. '
      '프로젝트 안내: UnrealProjects/MotionCheckUE58/Manny_확인방법.md. '
      'sourceBlend/FBX SHA 일치,기존 MVP 및 추론결과 보존. GPU추론·앱 출력/GUI 변경 없음.\n'
      '이슈: 원본proxy는 Manny 호환 skeleton이 아니므로 직접 지정 대신 체인 리타게팅/별도베이크로 해결. '
      'UE 경고2종(원본 curve 없음/임포트메타데이터 preload)은 에러 없이 결과 저장·재열기 통과. '
      '새맵 조명은 Movable로 정적조명 rebuild 의존을 피했다. 기존맵의 경고는 수정하지 않았다.\n'
      '3차검토: ①체인 본 이름/척추2→5개/타깃skeleton, ②전체프레임길이·유한좌표·root/원본SHA, '
      '③실제GUI 재생/별도 저장·경고/변경범위 확인.\n'
      '남음: 사용자의 Manny 체형 기반 접지·관통·손목 시각검토,다른영상 리타게팅,프로그램 자동출력 연결, '
      '3인칭 AnimBlueprint/플레이어 동작 연결,손가락·얼굴 및 임의타깃프로필. 기존 v0.8.0 제품 MVP 유지.\n')
for name in ('CURRENT_TASK.md','PROGRESS.md','PROJECT.md','ISSUES.md'):
    p=ROOT/'md'/name;old=p.read_text(encoding='utf-8')
    assert title not in old
    p.write_text(title+body+'\n---\n\n'+old,encoding='utf-8')
case_number=max(int(p.name[4:]) for p in (ROOT/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=ROOT/'진행상황'/f'case{case_number}';case.mkdir()
for name in ('CURRENT_TASK.md','PROGRESS.md','PROJECT.md','ISSUES.md'):
    p=ROOT/'md'/name;shutil.copyfile(p,case/name);assert sha(p)==sha(case/name)
(E/'checkpoint.json').write_text(json.dumps({'md_archive':case.name,'source_preserved':True,'visual_playback_confirmed':True,
    'scripts_sha256':{name:sha(ROOT/name) for name in ('tools/unreal_retarget_manny.py','tools/unreal_verify_manny.py')}},indent=2),encoding='utf-8')
print(case.name)
