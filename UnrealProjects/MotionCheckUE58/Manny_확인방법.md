# Manny 리타게팅 확인

MotionCheckUE58.uproject를 Unreal5.8로 연다.

Content Drawer → MannyMotion → Manny_ReferenceMotion_Anim을 더블클릭하고 재생한다. 기본3인칭 Manny(SKM_Manny_Simple), SK_Mannequin 스켈레톤용 LongSword 애니메이션이다. 30fps,447키,446구간,14.86667초. 원근 → 따라가기 모드 → 루트 공전으로 화면을 맞춘다.

IK_Motion22와 IK_Manny의8체인(척추/목머리/좌우쇄골/좌우팔/좌우다리)을 RTG_Motion22_Manny에 연결하고 타깃 기준자세를 자동 정렬한 뒤 베이크했다. 원본22본/FBX/Blend는 유지한다. MannyPreview 레벨은 별도 저장했다.

손가락/얼굴 추적, 무기 장착,3인칭 이동 AnimBlueprint 교체 및 제품 GUI의 자동 Manny출력은 미구현이다. 본 길이 검사는 구조 보존 검사이며, 발 미끄러짐/관통/손 위치의 시각적 품질은 추가 확인해야 한다.
