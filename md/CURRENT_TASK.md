## 2026-10-22 / Manny 기본3인칭 스켈레톤 리타게팅1차

사용자 요청: 기준22본 proxy 대신 Unreal 기본3인칭 Manny의 본/메시에 모션 적용. M5 진행 중이며 사용자 요청으로 Manny 고정 타깃 리타게팅1차를 수행했다. 임의 캐릭터 자동매핑 전체 완료는 아니다.
설치된 UE5.8 TemplateResources/High/Characters의 원본 에셋128개를 새 검증 프로젝트의 Content/Characters에 복사했다. Manny_Simple은 실제 기본 SK_Mannequin 스켈레톤89본을 사용한다. 원본22본 구조는 변경하지 않았다.
tools/unreal_retarget_manny.py: source/target IK Rig,8체인,IKRetargeter default5ops,타깃 ChainToChain 기준자세 정렬, RunBatchRetarget로 /Game/MannyMotion/Manny_ReferenceMotion_Anim 생성·저장. 손가락/얼굴은 추적 데이터가 없으므로 별도 추적동작을 만들지 않는다.
검증: 실제 UE5.8.1 commandlet 생성과 별도 재열기 PASS. Manny skeleton 동일,30fps447키/446구간14.86667초. 전체447샘플의 주요15본 좌표 유한값 및8개 팔다리 세그먼트 길이 유지 PASS,시작~끝 root 이동323.31cm. 이 검사는 동작 정답률/접지 품질의 검증은 아니다. 실제 GUI에서 Manny 메시와 머티리얼,팔·다리 자세 변화/몸회전/이동·반복재생 확인. 애니메이션 창을 Manny 결과가 재생되는 상태로 두었다.
별도 /Game/MannyMotion/MannyPreview 레벨에 Manny 단일애니메이션 actor/바닥/이동식 조명을 저장했다. 이 레벨은 commandlet 저장 확인이며 GUI 레벨 시각검사는 하지 않았다. 기존 Preview 시작맵은 유지.
증거: validation/manny/report.json,verification.json,playback.png,retarget.log,verify.log. 프로젝트 안내: UnrealProjects/MotionCheckUE58/Manny_확인방법.md. sourceBlend/FBX SHA 일치,기존 MVP 및 추론결과 보존. GPU추론·앱 출력/GUI 변경 없음.
이슈: 원본proxy는 Manny 호환 skeleton이 아니므로 직접 지정 대신 체인 리타게팅/별도베이크로 해결. UE 경고2종(원본 curve 없음/임포트메타데이터 preload)은 에러 없이 결과 저장·재열기 통과. 새맵 조명은 Movable로 정적조명 rebuild 의존을 피했다. 기존맵의 경고는 수정하지 않았다.
3차검토: ①체인 본 이름/척추2→5개/타깃skeleton, ②전체프레임길이·유한좌표·root/원본SHA, ③실제GUI 재생/별도 저장·경고/변경범위 확인.
남음: 사용자의 Manny 체형 기반 접지·관통·손목 시각검토,다른영상 리타게팅,프로그램 자동출력 연결, 3인칭 AnimBlueprint/플레이어 동작 연결,손가락·얼굴 및 임의타깃프로필. 기존 v0.8.0 제품 MVP 유지.

---

## 2026-10-22 / 새 Unreal5.8 프로젝트 실제 에디터 재생 확인

사용자 요청으로 기존 검증 프로젝트와 별개의 새 MotionCheckUE58 프로젝트를 생성하고 Unreal5.8.1 실제 GUI에서 열었다. LongSword의 M4 기준 스켈레톤 FBX를 임포트해 Skeleton/SkeletalMesh/AnimSequence 및 바닥/조명 맵을 저장했다. 애니메이션 에디터의 ReferenceMotion_Anim에서30fps·447키/446구간·14.86667초를 확인했고 0/중간/446 끝 프레임과 실제 재생 중 팔·다리 자세 및 루트 이동 변화, 반복 재생을 확인했다. 동작 정확도/완전한 접지/다른 캐릭터 리타깃의 정답검증을 뜻하지 않는다.
고정 카메라에서는 이동하는 몸이 화면 밖으로 나가므로 원근 → 따라가기 모드 → 루트 공전을 적용했다. 에디터 애니메이션 창을 열린 상태로 남겼다. source .blend/FBX SHA 보존 확인, GPU 재추론/앱 보정 코드 변경 없음.
프로젝트: C:\Users\user1\Desktop\취미\UnrealMotionCaptureProgram\UnrealProjects\MotionCheckUE58\MotionCheckUE58.uproject
확인자료: validation/ue58-visual/visual-report.json, end-frame.png, MotionCheckUE58_project.zip 및 프로젝트 확인방법.md.
이슈/조치: 처음 긴 이름 MotionCaptureCheck_UE58에서20자 제한 경고가 떠 짧은 새 이름으로 프로젝트를 생성했다. 긴 이름의 시험 폴더는 보존하고 해당 에디터 창만 닫았다. 화면제어 도구 실행 승인 시간 초과는 사용자 승인 뒤 진행했으며, 파일 선택 모달 제어가 불안정하여 승인된 Unreal 프로젝트 경로 실행 옵션으로 열고 UI로 재생을 확인했다.
남음: 레벨 시작 카메라가 메시 안쪽인 초기값과 정적 조명 재빌드 경고는 남아 있다. 애니메이션 에디터 환경 조명에서는 재생 가능. FBX proxy 머티리얼은 화면에서 흰색으로 보였으며 좌우/몸통 컬러 복원은 미완료. 이번 실제 UI 시각검사는 LongSword 기준 리그1개이며 전체6영상 UE 시각검증·Unity·임의 캐릭터 리타깃은 미검증이다. M5 진행 중, 기존 v0.8.0 제품 MVP 유지.

---

## 2026-10-22 / MVP5 v0.8.0 엔진용 FBX·Unreal 기준 리그 미리보기1차

Milestone M5 IN_PROGRESS / FBX export + isolated Unreal reference preview first checkpoint.
Goal: 보정된 M4를 엔진에 전달하고 기준 리그로 미리보기 준비. Scope: engine_export_job/FBX·UE scripts/GUI 및 검증.
Acceptance: 프로그램 버튼·취소·원본 보존, 두FBX22본/위치 왕복, 실제UE5.8 import/reopen/시간·단위 검사.
사용자가 Norma 제외6영상 결과를 긍정 확인하고 다음 작업 진행을 요청했다. M4 결과 검증을 정리하고 계획의 M5 Unreal Motion Preview 첫 단계에 진입했다. M5.5 분석/Mapping/Profile/임의 캐릭터 Retarget은 아직 시작하지 않았다.
새 app.engine_export_job + tools/export_engine_fbx는 저장된 M4 animation.blend/animation.json을 읽어 animation-<id>/engine-<id>/Motion_Unreal.fbx, Motion_Unity.fbx 및 export.json을 생성한다. 새 GUI 버튼 Unreal · Unity FBX 저장을 기존 worker/취소/busy 경로에 연결했다. 기존 Blender 버튼 유지, 원시/M3/보정/이전Blend 보존, 모델·GPU 재추론/의존성 추가 없음.
정수 샘플 경계의 엔진 호환성을 위해 초 단위 시간을 유지하면서30fps로 리샘플한다. 원본 길이와 FBX 길이 차이는 종료점 반올림의 최대1/60초이며 source_fps/source_duration/fbx_duration을 기록한다. 22본과 rigid BoneProxy 메쉬를 출력하며 별도 타깃 캐릭터에 맞춘 결과는 아니다.
사용: StartPrototype.cmd로 재시작 → 기존 결과 선택 → Unreal · Unity FBX 저장. Unreal에는 Motion_Unreal.fbx를 Skeletal Mesh+Animation으로 임포트한다. Unity 파일은 생성·Blender 왕복만 확인했으며 Unity 실제 임포트는 미검증이다.
별도 Unreal5.8.1 테스트 프로젝트: validation/m5-release/MotionPreview/MotionPreview.uproject. 열면 /Game/MotionPreview/Preview에 기준 리그·평면 지면·조명이 있다. Content Browser에서 ReferenceMotion_Anim을 열어 Play로 확인한다. live 영상 동기화/임의 프로젝트 자동 연결/캐릭터 리타깃은 미구현.
검증99 PASS/기존 opt-in1 SKIP: 비GUI55+기존40+격리GUI4, compileall PASS. 새 export 취소/잘못된schema/인자배열/입력SHA/출력SHA/프로그램 버튼·busy 연결과 기존 M4 경로 회귀 통과. LongSword/춤/짧고긴누락·컷 합성3개×2종FBX=6개 Blender 재임포트,22본·평가된 관절위치 보존 확인(최대1mm 미만). Unreal5.8.1 실제 import+저장+다시 읽기에서 SkeletalMesh/Skeleton/AnimSequence,22본·447sample keys/446intervals·14.86667초 확인. 4개 시점 원본 대비 UE 관절위치 최대오차 0.00013287cm. 첫 자세에서 정규직교 좌표변환을 한 번 추정해 다른3시점에 고정 적용했고 Zup/미터→센티미터100배 확인. 이는 변환 보존 검사이며 동작 정답률/타깃 리타깃/화면 품질 검증을 뜻하지 않는다.
원인/조치: Blender FBX 재임포트가 pelvis를 connected bone으로 추정해 수직 local translation을 무시했고 anim_offset 기본값으로1프레임 밀렸다. 검증 importer를 연결 해제·offset0으로 맞추니 원본과 일치했다. 소스 .blend나M4보정은 바꾸지 않았다. 누락 visibility 애니메이션이 첫FBX bake 중 선택을 해제하여 두번째FBX가 비는 문제는 export 전 메모리 복제본의 visibility FCurve만 제거해 해결했다. 원본의 숨김/누락 정보는 보존된다. Unreal sandbox 실행이 로그/보고서 없이0종료하여 성공으로 취급하지 않았으며 승인된 로컬 실행으로 실제 보고서·자산을 검증했다.
이전 일괄 작업의 북북춤 checkpoint replace WinError5는 임시 Windows 파일 접근 충돌로 기록한다. 기본/후보 추론을 보존해 후처리를 재개했고6개 완료했다. 배치 기록 교체 재시도를 도구에 추가했다.
한계: FBX에는 관절별/전신 누락의 유효성 flag와 객체 숨김을 신뢰성 있게 전달하지 않는다. 누락 구간은 M4의 부모/rest fallback 또는 hold가 포함될 수 있으며 복원 동작이 아니다. export.json missing_spans/missing_pose_frames 및 원본 animation.json을 함께 확인해야 한다. M5 긴누락 클립 분리·엔진 표시 정책, 전체6영상 엔진 재생 시각확인, Unity 임포트, 엔진 화면 자동열기·영상 동기화는 남았다. 이번 UE 검증은 NullRHI commandlet이므로 화면의 조명/시점/재생 품질은 사용자 확인 대기다. 스킨은 기존 bone proxy이며 제작용 캐릭터가 아니다. M5 전체 완료 선언 없이 첫 체크포인트로 보관한다.
자체3차검토: ①초/프레임·좌표/단위·root/pelvis translation·22본·원본SHA, ②누락 visibility/FBX 선택·2형식 출력·별도project의실제UE저장/재열기, ③worker취소/실패/출력완료검사·기존GUI 경로·코드SHA/기존MVP보존 확인.
