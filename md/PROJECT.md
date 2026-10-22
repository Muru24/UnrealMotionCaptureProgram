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

사용자가 Norma 제외6영상 결과를 긍정 확인하고 다음 작업 진행을 요청했다. M4 결과 검증을 정리하고 계획의 M5 Unreal Motion Preview 첫 단계에 진입했다. M5.5 분석/Mapping/Profile/임의 캐릭터 Retarget은 아직 시작하지 않았다.
새 app.engine_export_job + tools/export_engine_fbx는 저장된 M4 animation.blend/animation.json을 읽어 animation-<id>/engine-<id>/Motion_Unreal.fbx, Motion_Unity.fbx 및 export.json을 생성한다. 새 GUI 버튼 Unreal · Unity FBX 저장을 기존 worker/취소/busy 경로에 연결했다. 기존 Blender 버튼 유지, 원시/M3/보정/이전Blend 보존, 모델·GPU 재추론/의존성 추가 없음.
정수 샘플 경계의 엔진 호환성을 위해 초 단위 시간을 유지하면서30fps로 리샘플한다. 원본 길이와 FBX 길이 차이는 종료점 반올림의 최대1/60초이며 source_fps/source_duration/fbx_duration을 기록한다. 22본과 rigid BoneProxy 메쉬를 출력하며 별도 타깃 캐릭터에 맞춘 결과는 아니다.
사용: StartPrototype.cmd로 재시작 → 기존 결과 선택 → Unreal · Unity FBX 저장. Unreal에는 Motion_Unreal.fbx를 Skeletal Mesh+Animation으로 임포트한다. Unity 파일은 생성·Blender 왕복만 확인했으며 Unity 실제 임포트는 미검증이다.
별도 Unreal5.8.1 테스트 프로젝트: validation/m5-release/MotionPreview/MotionPreview.uproject. 열면 /Game/MotionPreview/Preview에 기준 리그·평면 지면·조명이 있다. Content Browser에서 ReferenceMotion_Anim을 열어 Play로 확인한다. live 영상 동기화/임의 프로젝트 자동 연결/캐릭터 리타깃은 미구현.
검증99 PASS/기존 opt-in1 SKIP: 비GUI55+기존40+격리GUI4, compileall PASS. 새 export 취소/잘못된schema/인자배열/입력SHA/출력SHA/프로그램 버튼·busy 연결과 기존 M4 경로 회귀 통과. LongSword/춤/짧고긴누락·컷 합성3개×2종FBX=6개 Blender 재임포트,22본·평가된 관절위치 보존 확인(최대1mm 미만). Unreal5.8.1 실제 import+저장+다시 읽기에서 SkeletalMesh/Skeleton/AnimSequence,22본·447sample keys/446intervals·14.86667초 확인. 4개 시점 원본 대비 UE 관절위치 최대오차 0.00013287cm. 첫 자세에서 정규직교 좌표변환을 한 번 추정해 다른3시점에 고정 적용했고 Zup/미터→센티미터100배 확인. 이는 변환 보존 검사이며 동작 정답률/타깃 리타깃/화면 품질 검증을 뜻하지 않는다.
한계: FBX에는 관절별/전신 누락의 유효성 flag와 객체 숨김을 신뢰성 있게 전달하지 않는다. 누락 구간은 M4의 부모/rest fallback 또는 hold가 포함될 수 있으며 복원 동작이 아니다. export.json missing_spans/missing_pose_frames 및 원본 animation.json을 함께 확인해야 한다. M5 긴누락 클립 분리·엔진 표시 정책, 전체6영상 엔진 재생 시각확인, Unity 임포트, 엔진 화면 자동열기·영상 동기화는 남았다. 이번 UE 검증은 NullRHI commandlet이므로 화면의 조명/시점/재생 품질은 사용자 확인 대기다. 스킨은 기존 bone proxy이며 제작용 캐릭터가 아니다. M5 전체 완료 선언 없이 첫 체크포인트로 보관한다.
자체3차검토: ①초/프레임·좌표/단위·root/pelvis translation·22본·원본SHA, ②누락 visibility/FBX 선택·2형식 출력·별도project의실제UE저장/재열기, ③worker취소/실패/출력완료검사·기존GUI 경로·코드SHA/기존MVP보존 확인.

---

## 2026-10-21 / v0.7.9 Norma 제외6영상 일괄 출력

Scope: 원본 폴더 MP4 중 Norma만 제외, 총6개. 이전 취소 batch는 재시작하지 않고 별도 요청 batch를 생성했다. 기존 현행 결과는 source/raw/M3/code SHA로 확인 후 재사용, 없는 영상은 SAM2/SAM3D·기본 full 자동후처리·M3·현행 Blender까지 실행.
상태: completed. 완료 6/6. 결과 및 개별 검사: validation/all-except-norma-v079/결과목록.md, batch.json. 완료 항목은 독립 Blender 재열기·접지/위치·fractional SLERP/누락경계 검사와 원본/기존 .blend SHA 보존 확인. 사용자 시각확인 대기. 코드/모델 변경 없음, 기존 v0.7.9 MVP 유지.
원인/조치: Sword 첫 프레임에 실제 인물과 거울 반사2후보가 있어 자동 단일대상 선택 가드가 실행을 중단했다. 첫 화면의 후보 이미지를 직접 확인해 실제 인물 index1을 명시한 별도 새 출력으로 재시도했다. 기존 실패 폴더와 완료된 다른 영상은 보존했다. 최종 상태/검사 결과는 위 batch.json을 기준으로 확인한다.

---

## 2026-10-21 / v0.7.9 Norma 제외6영상 일괄 출력

Scope: 원본 폴더 MP4 중 Norma만 제외, 총6개. 이전 취소 batch는 재시작하지 않고 별도 요청 batch를 생성했다. 기존 현행 결과는 source/raw/M3/code SHA로 확인 후 재사용, 없는 영상은 SAM2/SAM3D·기본 full 자동후처리·M3·현행 Blender까지 실행.
상태: completed_with_errors. 완료 4/6. 결과 및 개별 검사: validation/all-except-norma-v079/결과목록.md, batch.json. 완료 항목은 독립 Blender 재열기·접지/위치·fractional SLERP/누락경계 검사와 원본/기존 .blend SHA 보존 확인. 사용자 시각확인 대기. 코드/모델 변경 없음, 기존 v0.7.9 MVP 유지.

---

## 2026-10-21 / v0.7.9 뒤차기4종류 추가 영상 확인

사용자가 v0.7.9 결과를 긍정 확인하고 다른 영상 추출을 요청했다. 회전·발차기가 많은 뒤차기4종류를 선택했다. 기존 SAM2/SAM3D/M3 추론을 재사용해 현행 보정·축 방향 정책으로 새 Blender 애니메이션을 출력했다. GPU 재추론 없음.
결과 313프레임 / 29.924fps, 골반 유효 310프레임. 실제 Blender 독립 재오픈의 본 위치·회전·접지 및 fractional SLERP/누락경계 검사 PASS. 원본영상·원시JSON·M3·이전 .blend SHA 보존.
출력: C:\Users\user1\Desktop\취미\UnrealMotionCaptureProgram\outputs\뒤차기 종류 4가지_ _태권도 _발차기 _뒤차기 _겨루기 _태권도입시 _tkd _taekwondo _kick_sam3d_20261021_153218_249115c1\motion\animation-f1749a338b64\animation.blend
짧은 확인경로: validation/kick-v079/example/animation.blend
코드/모델/의존성 변경 없음, 기존 v0.7.9 MVP는 유지. 새 영상 사용자 시각확인 대기. 기계적 검사 통과는 추정 자세의 정답률이나 모든 발차기 접지의 정확도를 뜻하지 않는다.

---

## 2026-10-21 / MVP4 v0.7.9 축 비틀림 사전값·가림 뒤 연결

우선순위5의 첫 보정 적용. 기존 단순 평행이동 회전 전달은 몸통 회전과 무관한 축 방향을 오래 유지할 수 있었다. 상완·전완·허벅지·종아리8본에서 부모의 현재 회전과 rest 상대방향으로 축 사전값을 만들고, 관측된 본 방향으로 swing을 맞춘 뒤 기존 전달 방향에서 축 roll만 보정한다. Quaternion 사용, 시간상수0.18초·최대120도/초이며 관측된 빠른 swing 자체를 속도 제한하지 않는다. 접지 발의 바닥 기준 roll, 위치·본길이·루트·접지·점프 및 v0.7.8 잔떨림 보정은 그대로다.
동일 추적/장면 안의 부분 누락은 최대0.25초까지만 이전 roll을 기억한다. 긴 부분 누락 뒤에는 부모 사전값으로 재시작하고, 전신 분실/장면·추적 경계에서는 기억을 버린다. 누락 위치/Quaternion은 계속 null이며 보간하지 않는다. animation.json의 orientation_policy에 본별 short_missing/long_missing 구간, 재연결 수, 적용 최대roll, filled=false를 기록한다. 이는 가려진 동작을 생성하는 모델이 아니라 보수적인 방향 재연결 정책이다.
프로그램 연결: 재시작 → 기존 결과 선택 → Blender 애니메이션 저장. 새 animation-<id>로 출력하며 GPU 재추출 불필요. 축 roll은 Blender 메쉬/본 방향에서 확인한다. 관절점 위치가 같으므로 오른쪽 선 스켈레톤의 외형은 동일할 수 있다. 원시/M3/이전 .blend를 보존했다. root_motion_kind도 실제 보정본의 값을 animation.json에 전달하도록 맞췄다.
정량 확인(실제 비틀림 정답률이 아님): dance 평균 부모축 사전값 차이 79.92→20.14도; LongSword 평균 부모축 사전값 차이 48.17→15.59도; 정답 라벨 없이 설정한 사전값을 따르는 정도만 측정했다. 일부 순간 큰 차이는 남는다.
검증102 PASS/기존 opt-in1 SKIP: 기존 비GUI91+격리GUI3+Blender 수학속성8, compileall PASS. 축 rate·정규직교·0/180도 swing·±179도 shortest path·30/60fps·수렴·누락/컷 구간 보고 검증. 춤411/LongSword445/기존합성80/새 가림합성150 프레임 실제 Blender 저장·독립 재오픈·fractional SLERP 검사 통과. 새 합성은3프레임 부분 누락,21프레임 부분 누락,11프레임 전신 분실,장면 변경을 포함한다. 가림 중 null 유지·짧은 roll 연결·긴 부분 누락 재시작 확인. 실제2개영상+기존합성의 corrected-motion.json은 v0.7.8과 바이트 단위 동일하므로 접지/점프/루트/관절위치를 보존했다. 원본영상/원시/M3·이전Blender SHA 보존, 의존성·GPU모델·22본/schema 변경 없음.
한계: 관절 위치만으로 팔뚝 회내/회외·피부 축 비틀림을 직접 관측할 수 없어 부모 기준의 보수적 prior다. 실제 독립적인 팔다리 비틀림을 일부 완화할 수 있으며 사용자 시각확인이 필요하다. 긴 가림 동작 복원은 미해결이고 재등장 자세 차이도 남을 수 있다. 부분 누락의 Blender proxy는 기존 부모/rest fallback을 표시하므로 관측/복원 결과로 해석하면 안 된다. 전신 누락은 숨김 유지. 옷·머리카락에 붙은 유효값 오추정은 이번 정책의 누락으로 간주하지 않으며 후순위3으로 남긴다. 손가락·얼굴/애니메이션FBX·게임엔진 리타깃도 아직 미구현이다.

---

## 2026-10-21 / MVP4 v0.7.8 작은 관절·루트 잔떨림 완화

우선순위4 잔떨림 추가 완화. 6속도/1접지/2영상·접지 이동 추정 유지. 다음5비틀림·긴 가림, 3옷·머리카락 오추정은 후순위.
v0.7.8 correction.revision=7: 기존 SLERP 강도를 전체적으로 올리지 않고, 앞뒤 약1/30초 quaternion midpoint와 현재 회전의 작은 차이만 대칭으로 완화한다. 상체2~8도/다리1~5도 범위에서 가중치를 줄여 큰 빠른 변화는 보존한다. 새 영상 루트 후보의 XY에서도5~25mm 크기의 작은 곡률만 완화하고 루트 후보Z/공중 판정은 별도로 유지한다. 일정 속도 회전/직선 이동은 그대로이며, 누락·장면·camera epoch/유효구간 경계를 넘지 않는다. 접지/IK 뒤에 필터를 추가하지 않아 잠긴 발·본 길이를 재차 움직이지 않는다.
기존 프로그램 경로에 연결했다. 프로그램 재시작 → 기존 결과 선택 → Blender 애니메이션 저장으로 새 animation-<id> 생성 및 오른쪽3D 보정본 갱신. GPU 재추출 불필요. 원시/M3/이전 .blend와 빠른 후보 추론·영상 루트/접지 경로를 보존했다.
v0.7.7 대비 전체 프레임의 부모상대 관절 위치2차차분 평균 지표: LongSword 손목 좌17.70%/우17.60%, 무릎 좌1.89%/우2.58% 감소, 루트3.81% 감소. 춤 손목 좌4.61%/우6.66%, 무릎 좌4.90%/우9.16%, 루트3.46% 감소. 실제 Blender 키의 팔/종아리 angular-speed-change 지표도 확인한12개 모두 감소했고 최대1프레임 회전각 증가는1도 미만. 이 지표는 시간적 완화 정도이며 동작 정답률이 아니다. 춤 공중판정147~153프레임 동일, 루트Z최대0.18111→0.17917m(약1.94mm차), 175~185프레임 발목0.07m 접지 유지.
검증 고유94 PASS/기존 opt-in1 SKIP, compileall PASS. core/app/루트/새필터51+기존회귀40+격리GUI3. 작은 회전/루트 노이즈 감소, 일정속도 운동 보존, 빠른90도 peak 시점/높이 보존, Quaternion 부호/±180도·30/60fps·짧은span, 큰 루트급변/Z보존 및 기존 접지·공중/착지·누락/컷·원본해시/취소 회귀 통과. 춤411/LongSword445/합성80 프레임 실제 새 Blender 저장·재오픈 head/Quaternion·메쉬밑면·접지 및 fractional SLERP/누락경계 검사 통과. 원본영상/원시JSON/M3·이전Blender SHA 보존. GPU추론·의존성·22본/스키마 변경 없음.
한계: 작은 실제 빠른 손짓도 잔떨림과 비슷하면 일부 완만해질 수 있다. 팔·다리 축 비틀림, 지속적으로 잘못 잡힌 관절·머리카락/옷·긴 가림은 해결하지 않았다. 골격 자세 오류/큰 순간 회전은 잡음으로 단정해 지우지 않으며 다음5에서 별도 검사한다. 거리·깊이·접지는 계속 모델 추정이고 모든 떨림 해결/동작 정확도 개선을 보장하는 수치는 아니다. 사용자 새 보정본 시각확인 대기.

---

## 2026-10-21 / MVP4 v0.7.7 영상·접지 결합 이동·높이 추정

우선순위2 이동·높이 추정 확장. 6속도 사용자 개선확인, 1웅크림 접지 유지. 다음 4잔떨림 → 5비틀림·긴 가림, 3옷/머리카락 오추정은 후순위.
v0.7.7 correction.revision=6: 기존 접지 루트에 영상 골반·발 투영과 원시 SAM pred_cam_t 깊이를 결합했다. 정확한 원본영상/원시JSON SHA가 일치할 때만 CPU로 영상을 읽고, 대상 bbox를 제외한 배경 특징의 전후 optical flow 및 RANSAC 유사변환으로 pan/roll/zoom을 보정한다. 3D SLAM은 아니다. 보정 투영좌표와 zoom 보정 모델 깊이에서 골반 이동 후보를 만들고, 접지 제약과 속도 제한으로 결합한다. 카메라 epoch/장면/누락 경계의 기준을 재설정해 이어 붙이지 않는다. 배경/원본/발 근거가 없거나 부적합한 구간은 기존 접지 계산을 유지한다.
양발 발목·발끝 투영 높이가 바닥 기준보다0.055m, 골반이0.06m 이상 올라가며 최소0.06초 지속되고 3D 다리도 유효한 경우만 estimated_airborne으로 판단한다. 이 구간의 잘못된 접지 잠금을 해제하고 루트Z도 움직인다. 착지 전환은 부드럽게 복귀하며, 이미지/3D 모순으로 발이 바닥 아래로 내려가지 않도록 공중 최소 여유0.015m를 둔다. 바닥 위 수평 발 이동은 수직 지지만 남기고 XY잠금을 해제한다. 한쪽 발차기·웅크림을 양발 점프로 취급하지 않는다.
프로그램 경로 연결 완료. 재시작 후 기존 결과 선택 → Blender 애니메이션 저장. 기존 추론을 재사용하며 새 animation-<id>에 저장하고, 오른쪽 3D에도 보정본을 표시한다. 카메라 보조분석에는 원본영상이 필요하지만 GPU 재추출은 필요 없다. 원본이 없으면 접지 보정으로 대체한다. 원시/기존 M3 motion.json·이전 .blend·22본/모델/의존성과 빠른 후보 추론 옵션을 유지했다.
검증 고유88 PASS/기존 권한 opt-in1 SKIP, compileall PASS. core/app33+새 루트12+기존회귀40+격리GUI3. 실제 합성MP4로 수평/수직 pan·zoom·느린 pan과 인물 이동을 분리하고, 점프/착지·한발들기·웅크림 유지·누락/카메라epoch·장면경계·본길이·수평이동·투영 불일치 시 바닥관통 방지·원본변조/취소를 검증했다. 춤411/LongSword445/합성80 프레임 새 Blender 저장·실제 재오픈 head/Quaternion·proxy밑면 및 fractional SLERP/누락·컷 경계 검증 통과. 춤175~185프레임 발목0.07m 유지. 춤 배경분석 유효386/411, 루트새근거380프레임, 공중추정147~153프레임, 루트Z범위약0.181m. LongSword는 유효164/445, 새근거145프레임만 적용하고 나머지 구간은 기존 계산을 유지했다. 이 수치들은 실측 이동거리/접지 정확도/점프 정답률이 아니다. 새 GPU추론 없음; 춤 CPU 분석+보정 표본약3.8초, 전체GPU 처리속도는 재측정하지 않았다. 원본영상/원시JSON/M3·기존Blender SHA 보존 및 새 root/camera 코드 SHA도 export report에 기록·확인.
자체3차검토: 접지/공중/착지·본길이/바닥 여유, root helper의 순환 의존성 제거 및 기존 fallback 보존, 해시/로컬경로/디코더timeout·취소/18,000프레임·최대1920해상도/배경거부 경계 확인. 미세 pan이 무시되어 인물 이동으로 누적되지 않도록 정지 deadband를 축소하고 느린 pan 테스트를 추가했다. 최종 guard와 코드 SHA 반영 후 release3종을 다시 저장·검증했으며 중간 실험 결과는 보존했다.
한계: 기준 스켈레톤/모델 크기와 기본 FOV를 사용한 추정이며 실제 인물 키·미터 이동거리·지면을 보정한 측량 결과가 아니다. 깊이는 모델 추정이라 자세·원근·카메라 pitch/3D parallax·움직이는 배경·반사에 오차가 남는다. 배경 특징 부족/가려진 발/프레임 밖 발은 새 근거가 제한된다. 작은 도약·긴 가림·모든 카메라 이동과 실제 월드궤적 복원은 미해결. 사용자 시각확인 대기, 다음은4잔떨림 보정.

---

## 2026-10-21 / MVP4 v0.7.6 웅크림 접지·골반 높이

사용자 v0.7.5 빠른 후보 추론 속도개선 확인 후 우선순위1 접지 작업. 다음 순서는 2루트 이동·높이 → 4잔떨림 → 5비틀림·긴 가림, 3옷/머리카락은 후순위 유지.
v0.7.6 correction.revision=5: 기존 3D 발높이 기반 접지가 놓치는 양다리 웅크림에 동일 추출 packet의 2D 발목·발끝·골반 투영좌표를 보조 근거로 사용한다. 양 무릎 굽힘≥30도, 접지 seed의 영상 바닥 근처, 발 대비 골반 하강, 최소0.1초 조건에서 골반을 낮추고 고정 본 길이 IK로 발목0.07m/발끝0.03m를 맞춘다. 새 inferred_ground_support는 수직 지지만 적용하고 XY를 고정하지 않아 회전·바닥 이동을 허용한다. 이륙/조건해제 후 추가 골반 오프셋을 해제하며 누락·컷·추적구간·화면밖 발에는 확장하지 않는다. 새 지지 상태도 Blender 발 roll의 바닥 기준 처리에 포함했다.
기존 프로그램 경로 연결 완료. 프로그램 재시작 → 결과목록에서 영상 선택 → Blender 애니메이션 저장. 기존 추출을 재사용하고 새 animation-<id>에 저장하므로 GPU 재추출 불필요. M3 motion.json/원시 결과/기존 .blend를 덮어쓰지 않는다. app.animation_job은 motion의 input_sha256과 정확히 일치하는 원본/후처리 packet만 읽고 프레임·좌표를 검증한다. 근거가 없으면 기존 3D 접지만 사용하며, 사용한 근거의 SHA와 생성후 무결성을 검사한다. M3 규격/22본·모델·의존성·GPU 경로는 그대로다.
검증 고유76 PASS/권한 opt-in1 SKIP, compileall PASS. 비GUI core33+기존 SAM/자동후처리/5분입력/늦은등장40+격리실제GUI3. 웅크림 수직지지·XY비고정·본길이·발차기/공중굽힘·웅크린뒤 이륙·화면밖 발·누락/컷·근거SHA/프레임검사 통과. 춤411/LongSword445/합성80 프레임 실제 Blender 새저장·재오픈과 fractional SLERP·분절경계 검증 통과. 춤175~185프레임 발목Z기존0.26~0.39m에서0.07m, 골반도 함께 하강. 춤 최대 발목1프레임 이동0.39127m는 기존과 동일(빠른 발차기), LongSword0.23434m. 춤 새 지지123프레임, 모든접지 정답검증을 뜻하지 않음. 원본영상/원시JSON/M3와 기존Blender 보존 확인. 자체3차검토 완료: 조건/접지해제/본길이, core와 파일근거 경계, provenance·취소·기존경로/누락 회귀.
한계: 2D 근거도 모델 투영값이며 실제 바닥/접지 라벨·카메라 보정값이 아니다. 평면에서 크게 벗어나는 이동·카메라 이동/줌·작은 도약·가림/오추정에는 한계가 있다. 전 구간 양발을 바닥에 강제 고정하지 않으며 실제 점프높이/월드궤적 복원은 아직 미완료. 사용자 새 .blend 시각확인 대기. 다음 작업2에서 실제 이동·높이 추정의 제한을 다룬다.

---

## 2026-10-21 / MVP4 v0.7.5 후보 추론 속도 선택

사용자 우선순위: 6속도 → 1접지 → 2루트 이동·높이 → 4잔떨림 → 5비틀림·긴 가림. 3옷·머리카락 오추정/Norma는 후순위. 기존 v0.7.4 춤 결과는 사용자가 양호하다고 확인.
v0.7.5: GUI 빠른 후보 추론(시험) 체크를 추가했다. 기본 OFF/full 유지. 체크 시 추가 observed/tight/stable-flip 후보만 body decoder를 사용하며 원본 SAM3D full, 부분 재추정, 추적, M3, M4 보정은 동일하다. 후보 수/프레임 수를 줄이지 않는다. full/body 결과 캐시를 분리하고 자동후처리 report에 stage_seconds/seconds/프로필을 기록한다. 기존 결과를 열 때도 실행 전 체크 상태를 적용한다. 프로그램 재시작 필요.
RTX4060 로컬 실측: 춤 초반4프레임×2ROI full 약6.04초 대 body1.74초(3.47배), 전반8프레임×2ROI full 평균13.46초 대 body3.64초(3.70배). 전반 표본의 최대 차이2D28.83px/카메라상대3D0.0871m. 손 전용 추론의 팔·손목 보정이 사라질 수 있으므로 품질 동등/무손실 최적화가 아니다. 초기 표본만으로 동등하다고 결론내리지 않았다. 전체 처리시간/여러 영상/5분영상의 속도·정확도 검증은 아직 없고 후보 단계 수치를 전체 배수로 해석하지 않는다. cache유지0.99배, bbox2개 batch1.004배(관절차1.86px), threads1개1.016배, TF32 1.019배는 유의한 개선 근거 부족으로 제품에 적용하지 않았다.
검증: 비GUI28 PASS, 격리실제GUI 기본출력·빠른출력·기존결과열기3 PASS(총31), compileall PASS. 실제 CUDA candidate worker body3프레임×3후보9회와 선택/비교영상 저장 통과, 원본/기존raw SHA불변. 자체3차검토: 프로필·캐시·프레임/본 규격 / 기존 full·raw 경로 보존 / 취소·로컬프로세스·원본보존. 검증 실행기 최초 선택저장에 필요한 parent sam3d.json fixture가 없어 FileNotFoundError; 분리된 짧은 fixture와 selection 폴더로 수정해 GPU재실행 없이 재검증 통과. 제품오류 아님.
6속도는 시험옵션 제공·부분완료이며 기본 품질모드의 큰 속도개선은 미완료. 빠른 모드 전체 시각검증/직전 약33분 전체추출 대비 시간 비교 대기. 다음 1: M4-GROUND-CROUCH-001 웅크림·착지 시 접지/골반높이. 이후 2→4→5. 이번 변경은 기존 접지·잔떨림·비틀림 문제를 해결하지 않는다.

---

## 2026-10-21 / v0.7.4 추가 춤 영상 실제 추출

사용자 요청 영상 이게 실제로 가능한 춤이였다고_ #부리부리마신소환춤.mp4를 새 결과폴더에 추출했다. 제품코드는 v0.7.4 그대로. SAM2 대상후보는 전경 실제인물1개(index0), TV애니메이션 인물을 선택하지 않았다. SAM2→SAM3D→기존 자동후처리→M3→v0.7.4 접지/잔떨림 보정→Blender 경로. 실제 411프레임, tracking 관측411, 자동후처리 상태 completed_with_estimates, motion 입력 checked_reconnection.
실행/검증 증거 validation/dance-v074, 제품 v0.7.4/참조22본/모델·스키마 그대로. 결과: C:\Users\user1\Desktop\취미\UnrealMotionCaptureProgram\outputs\이게 실제로 가능한 춤이였다고_ _부리부리마신소환춤_sam3d_20261021_140252_d135fce6
Blender: C:\Users\user1\Desktop\취미\UnrealMotionCaptureProgram\outputs\이게 실제로 가능한 춤이였다고_ _부리부리마신소환춤_sam3d_20261021_140252_d135fce6\motion\animation-5ef51df7bcae\animation.blend
확인복사본: validation/dance-v074/example/animation.blend
M4-GROUND-CROUCH-001 OPEN: 새 영상175~185프레임(약5.8~6.2초) 웅크림에서 보정JSON의 양발이 swing이며 발목Z약0.26~0.39m로 접지목표0.07m보다 높게 남는다. 원본 표본에서는 발의 바닥 접촉이 유지되는 것으로 보이지만 정답 접지라벨/실제미터 측정 검증은 아니다. 골반높이 고정으로 정규화한 관절에서 발높이 조건으로 접지를 추정하면 웅크림을 발들기로 오인하고 골반 하강을 복원하지 못할 수 있다. 이번 요청은 현버전 실제추출이므로 알고리즘을 즉석 변경하지 않고 결과/이슈를 보존했다. 후속 접지·골반 보정 검토 필요.
컨테이너 메타데이터414프레임/30fps/13.8초였으나 현재 OpenCV 원본디코드 및 추적/추출은411프레임으로 일치. 이 차이의 컨테이너/타임스탬프 원인은 이번에 확정하지 않았다. 윈도우 사전 CIM 프로세스정보 조회는 접근불가였으며 권한상승/사용자 프로세스 종료 없이 사용가능한 GPU/프로세스 조회로 대체. 배치추출 중지 상태는 유지하고 요청된 이 한 영상만 수행했다. 접지·월드이동은 추정이며 옷/가림·지속관절 오추정은 해결 보장하지 않는다. 사용자 결과확인 대기.

---

## 2026-10-21 / MVP4 v0.7.4 보간·잔떨림 추가 완화

사용자가 v0.7.3에서 더 부드럽게 보간하도록 요청. 기존 Quaternion 보정 파라미터만 강화했다. 저속 cutoff1.5→0.9Hz, 속도에 따른 cutoff 상승계수3→2, 상한18Hz 유지. IK 무릎 굴곡면 안정화0.07→0.10초, 큰 방향변화0.025초는 유지. 고립 impulse/방향일관성·접지/전환/길이·누락/컷 보호 및 quarter-frame 재생방식 유지. 보간 키 개수를 늘린 것이 아니라 유효구간의 시간필터를 더 강하게 적용한 버전이다.
correction.revision=4, cutoff_hz=[0.9,18], ik_pole_smoothing_seconds=0.10. 기존 positions/animation schema·22본·Quaternion 순서·quarter-frame 샘플은 동일. 원본은 유지하고 새 파생 보정결과로 저장한다.
사용: 프로그램 재시작→완료된 SAM3D 결과 선택→Blender 애니메이션 저장 다시 실행. 기존 파일은 자동변경하지 않고 새 motion/animation-<id>/에 고유 저장한다. 새 오른쪽3D 보정 미리보기도 갱신. 확인파일 validation/m4-smooth/LongSword-example/animation.blend. 원시/M3 motion·22본·모델·이전 .blend/MVP 보존, GPU추론·의존성 추가 없음.
한계: 더 강한 저속필터는 작은 동작·급변을 더 완만하게 만들 수 있다. 단일프레임 실제 빠른 peak도 고립잡음과 혼동할 수 있다. 정답접지/실제월드이동/지속관절오추정·Norma·긴누락은 미해결. 사용자 전체영상·5분 bake 자원부하·엔진임포트 미검증. 새파일 사용자 시각확인 대기, M5 자동진입 없음.

---

## 2026-10-21 / MVP4 v0.7.3 잔떨림 보정 강화

사용자 v0.7.2 연속성 개선 확인, 잔떨림 추가 보정 요청. M4 회전/움직임 보정만 강화했다. 원시SAM3D/후처리/M3 motion.json·22본·이전애니메이션/MVP 보존, 모델/패키지/GPU추론 변경 없음.
원인/조치: 기존 적응형 필터는 저속3Hz 하한과 각속도 기반 적응 때문에 잔떨림이 남고, 시간상 역방향으로 오가는 잡음도 빠른동작으로 취급할 수 있었다. 저속 하한을1.5Hz로 강화하고 주변0.10초 순이동각/누적이동각의 일관성으로 속도 가중치를 조정한다. 일관된 빠른동작은 최대18Hz 반응을 유지한다. 이웃 두 회전이6도 이내로 비슷하고 중앙만12도 이상 벗어난 고립된1프레임 회전은 이웃의 최단SLERP 중간값으로 억제. 관절 누락/scene/segment별 유효span 안에서만 적용한다. 접지/충돌/전환 IK의 무릎 굴곡평면은 직전 평면을 현재 다리축에 투영하고 시간간격 기반으로 완만하게 갱신 (기본0.07초, 큰 방향변화0.025초). 본길이·도달거리·굴곡면 부호 보호는 유지한다.
correction.revision=3, cutoff_hz=[1.5,18], motion_coherence_weighting=true, isolated_impulse_degrees=12, ik_pole_smoothing_seconds=0.07 기록. 기존 positions/animation 스키마와22본·부모계층/Quaternion 순서는 그대로다. 정상구간의 quarter-frame 재생 보간 및 scene/missing hold 정책은 v0.7.2 그대로 유지.
사용: 프로그램 재시작→SAM3D 결과 선택→Blender 애니메이션 저장을 다시 실행. 새 motion/animation-<id>/에 저장, 오른쪽3D 보정 미리보기에도 표시. 기존 파일은 자동수정하지 않는다. 확인용 파일 validation/m4-jitter/LongSword-example/animation.blend.
남은 한계: 실제 빠른 단발 동작이 고립잡음과 비슷하면 약해질 수 있고 필터로 작은 동작도 감쇠될 수 있다. 원시 지속오추정/Norma 의상·긴누락·정답접지/월드이동·전관절 해부학적 제약은 해결하지 않는다. 전체 사용자 영상/5분 bake 자원부하/엔진임포트는 이번 검증 대상 아님. 연속재생·접지 기반 추정과 누락/컷 보호는 유지, 사용자 v0.7.3 시각확인 대기.

---

## 2026-10-21 / MVP4 v0.7.2 자세 전환 연속 재생

사용자: 자세가 이어지지 않고 순간이동처럼 바뀜. 정상 구간의 재생 보간과 접지 제약의 진입/해제 전환을 수정했다. 원본22본/M3 motion/모델출력·이전애니메이션/MVP는 보존. GPU추론·새의존성 없음.
원인/조치: v0.7.0/1은 누락 경계 보호를 위해 모든 FCurve를 CONSTANT로 저장해 정상프레임 사이도 자세가 계단식으로 변했다. 동일 segment/scene의 두 유효 bone pose 사이만 1/4프레임 간격 Quaternion 최단SLERP와 위치선형키를 bake, 그 사이 FCurve는 LINEAR로 변경. 실제 장면전환·관절누락·전체미검출과 가시성 채널은 CONSTANT 유지. 기존 q/-q 부호연속과 단위Quaternion 유지. 더 촘촘한 키 사이 회전은 Blender 선형성분 보간의 근사다.
접지 제약도 갑자기 끊겼다. 루트 예측이0.15m를 넘으면 앵커를 버리던 처리를 연속적인 속도제한/감쇠로 바꿨다. 앵커 유무만으로 골반높이를 즉시 재설정하지 않고 같은 관측구간에서는 완만하게 갱신한다. 고정발 해제는 제약오프셋을 점차 제거하고, 새 접지/지면충돌 진입은 이전 발 위치에서 목표로 접근시킨다. 접지→지면충돌 전환도 별도 release로 처리한다. 무릎 IK/도달거리 투영/다리길이/지면 한계를 유지. 보정 offset 해제속도3m/s, 추정 루트XY soft1.8m/s/Z soft1.2m/s; 원래 swing 속도 전체를 동일 제한하지 않는다.
사용: 프로그램 재시작→결과 선택→Blender 애니메이션 저장을 다시 누른다. 이전 .blend는 바뀌지 않는다. 새 결과는 motion/animation-<id>/에 고유 저장되고 오른쪽 보정 미리보기도 갱신. 확인용 최신파일: validation/m4-continuity/LongSword-example/animation.blend.
schema/22본/기존파일 변경 없음. correction.revision=2, 전환상태 contact_transition/collision_transition/release_blend와 속도 메타데이터 추가. animation.json.playback_interpolation으로 valid span의 quarter-frame bake 방식을 명시한다. 정수 pose 데이터는 유지하고 재생파일에 subframe 키를 추가하며 미검출/컷 보호는 유지한다.
남은 한계: 추정접지·접지기반 루트이고 영상의 실제 월드이동을 측정하지 않는다. 위치 연속성은 개선했으나 고속 원본/오추정/몸통 회전 급변·개별 누락 fallback은 여전히 튈 수 있다. 긴 누락/컷은 동작을 꾸며 연결하지 않는다. 전환 보정은 작은 시간 지연/발 미끄러짐을 유발할 수 있다. 사용자가 본 영상/구간은 이번에 새로 특정하지 않았고 실제 재검증은 LongSword 및 합성이다. 5분 대용량의 subframe 키4배 bake 속도·메모리 미측정, 엔진임포트 미검증. 사용자 새 결과 확인 대기.

---

## 2026-10-21 / MVP4 v0.7.1 접지·회전 떨림 1차 보정

사용자 Blender 본 연동 확인 후 발 지면접촉·이동과 심한 관절 떨림 보정 요청. MVP4 범위에서 요청한 접지/회전 보정 부분을 우선 구현했다. 기존22본·원시SAM3D/후처리·M3 motion.json·v0.7.0 애니메이션·T-pose 자산은 보존, 모델/패키지/GPU추론 추가 없음.
구현: core/motion/correction.py에서 본 head 간 방향을 swing Quaternion으로 표현하고 최단경로 양방향 SLERP(3~18Hz, 약0.08초 이웃 각속도로 적응)를 적용한 뒤 같은 참조 길이로 계층 재구성. 단일프레임 흔들림을 빠른 동작으로 오인하지 않도록 이웃 구간 속도를 사용한다. joint 누락/추적 segment/scene 경계를 넘지 않으며 관절을 새로 채우지 않는다. 발 높이·수직 속도·최소지속시간으로 접지를 추정하고 지지 발목XY를 고정한다. 발목Z0.07m/발끝Z0.03m는 이 참조 본 프록시 메쉬의 밑면이 바닥Z0에 오도록 한 값이다. 루트XY는 접지 앵커 제약에서 추정, 골반 높이는 접지·도달거리 조건에 맞춰 조정, 무릎 2-link IK로 허벅지/종아리 길이·굴곡 방향 유지. 도달 불가 접지는 해제하고 별도 상태를 남긴다. 미접지 발도 관통 시 XY를 고정하지 않는 지면 충돌 IK를 적용한다. 접지/충돌 발의 회전축은 수평 지면 기준으로 안정화, .blend에 Ground 평면 추가.
사용: 프로그램 재시작→완료된 SAM3D 결과 선택→Blender 애니메이션 저장. 자동 보정 후 새 motion/animation-<id>/animation.blend, animation.json, corrected-motion.json, report.json 생성. 완료 시 오른쪽3D 패널도 보정 위치를 표시하고, 이후 결과 재선택 시 완료report·원본motion SHA·보정JSON SHA가 일치하는 최신 보정만 자동 표시한다. 기존 원시 영상의 선은 다시 렌더하지 않았으므로 오른쪽 보정 패널과 구분한다. Blender 파일을 열어 Space로 지면과 함께 재생. 이전 .blend에는 소급 반영되지 않으며 새로 저장해야 한다.
원래 standard_motion_positions_v1 경계와22본 규격을 보존. 보정JSON은 같은 스키마의 별도 파생파일이며 correction 객체에 파라미터·프레임별 접지상태/루트오프셋을 추가한다. 파생파일의 root_motion=true와 root_motion_kind=contact_constraint_estimate는 추정이동임을 명시한다. 원본M3 root_motion=false 및 bone_rotations=null은 변경하지 않는다. standard_bone_animation_v1 root_motion의 bool 타입도 유지하며 kind 필드를 추가했다. Python독립core에서 보정, Blender는 재현/bake, UI는 응용job 호출과 준비결과 표시만 담당.
한계: 평평한 지면과 참조 신체 비율 가정이며 실제 신발 모양·바닥 검출·정답 접지 라벨은 없다. 추정접지가 틀리면 발 끌기/피벗/점프/웅크림을 과도하게 제한할 수 있고 발목 고정 중 발끝 yaw는 변할 수 있다. 루트XY는 접지 제약으로 만든 경로이며 영상과 동일한 전역 이동·카메라 움직임을 복원한 것이 아니다. 공중 이동·실제 골반높이 복원, 전 관절 해부학적 제한, 지속 오추정/Norma 망토 문제는 미해결. SLERP는 떨림을 줄이지만 일부 동작을 감쇠시킬 수 있다. 5분 Blender 속도/메모리 미측정, UE/Unity 임포트·애니메이션FBX·손가락/표정은 미구현/미검증. 사용자 실제 영상 시각확인 대기.

---

## 2026-10-21 / MVP4 v0.7.0 Blender 본 애니메이션

사용자가 MVP3 영상1개 출력·스켈레톤 정상 확인. 떨림은 본 연결 뒤 보정하기로 하고 MVP4 진행 승인. 22본 정의·MVP2 원시/후처리·MVP3 motion.json과 T-pose/정지FBX를 보존한다. 새 모델/패키지/네트워크/GPU추론 없음. 기존 일괄추출 취소 유지.
M4 승인 범위: 기존 standard_motion_positions_v1를 바꾸지 않고 별도 standard_bone_animation_v1 파일과 .blend Action으로 확장. 본22개·계층·기존 JSON 유지. Blender backend는 tools 스크립트, 응용 process orchestration은 app/animation_job.py, UI는 해당 job 호출만 담당. 명시적 저장 버튼을 사용하며 GPU 재추론·추출시 자동 Blender 실행 없음. M4 첫 MVP는 위치를 로컬 quaternion과 키프레임으로 재현하는 범위이며 관절 해부학적 제한·떨림 필터·world root·접지·임의 리타게팅·Unity/UE 직접재생은 완료 아님.
사용: StartPrototype.cmd 재시작 → 결과목록에서 완료된 SAM3D 결과 선택 → 3D 패널 아래 Blender 애니메이션 저장. 필요하면 먼저 같은 M3 CPU 변환을 수행한다. motion/animation-<고유값>/animation.blend 및 animation.json/report.json 생성. Blender로 .blend를 열어 Space 재생. 새 영상 출력 때 애니메이션 저장은 버튼으로 명시적으로 실행한다.
한계: 제자리 root/참조 골반높이 유지, 실제 전역이동·골반높이·접지/Foot Lock 없음. 손가락/표정 본과 추적 연결, 애니메이션 FBX와 엔진 직접 임포트는 미구현/미검증. 관절점만으로 축 비틀림을 관측할 수 없어 몸 좌우 방향·팔다리 최소회전 운반 기준을 사용한다. 끝 본은 부모 회전을 상속한다. 개별 관절 누락은 JSON null/missing이며 .blend에서는 부모/기준 자세 fallback이라 복원된 동작이 아니다. 대상 전체 누락은 전신 숨김, 구간 경계/누락은 회전 이력 초기화. CONSTANT 샘플 키프레임으로 긴 누락/컷을 보간하지 않는다. 떨림/SLERP 필터는 기본 미적용. 5분18000프레임 Blender 속도·메모리는 미측정, 처리 제한30분. Norma 의상 오추정/M2 후보 첫26프레임 제약/QA-002 잔여는 해결 선언하지 않는다.

---

## 2026-10-21 / MVP3 v0.6.0 표준 스켈레톤·Blender 참조 리그

사용자2026-10-21승인: M3에Blender제작 공통휴머노이드와Unreal/Unity용FBX자산, 결과영상옆3D스켈레톤을포함. 현재22본정의assets/skeletons/humanoid_v1.json 및 새stable경계standard_motion_positions_v1를md/MOTION_FORMAT.md에정의했다. 기존M2JSON포맷/모델출력은변경하지않고새motion하위파일로저장. Unity는이번참조리그/정적역할표대상이며Unity Animator Clip생성/엔진어댑터전체완료를뜻하지않는다. M3는관절위치/계층까지, M4로컬회전→M5엔진미리보기→후속Retarget/Bake순서유지. 기존MVP2와Norma회귀보류상태유지.
사용자 승인 M3: Blender제작 참조본을 Unreal/Unity 양쪽 임포트 대상으로 제공하고 영상 옆에 동기화된 표준스켈레톤을 표시한다. v0.6.0, 원시MHR70·회전·MVP2결과 보존. 본회전/메쉬모션/Bake/엔진직접임포트는 미구현·미검증으로 구분한다. 새모델/의존성/다운로드/GPU재추론 없음.
4MD/case64 동일SHA 보관/v0.6.0 MVP 저장.

---

## 2026-10-21 / MVP2 전체 주요 이슈 총괄

MVP2 전체 인계 기준 문서: MVP요약/MVP2_전체_주요이슈와_해결내역.md. 직전 MVP요약/v0.5.24_MVP_이슈해결_요약.md는 최근 변경 상세 참고 자료로 유지한다. MVP2의 큰 문제 18개군과 잔여한계 8개군을 정리, 일반영상 기준 M3 준비와 Norma 보류 방침 유지. 최종 본회전/UEworld/root/retarget 미구현은 후속 기능 경계로 구분하며 현재 버그 해결로 오표시하지 않는다.

총괄: [MVP2 전체 주요이슈와 해결내역](../MVP요약/MVP2_전체_주요이슈와_해결내역.md)

---

## 2026-10-21 / v0.5.24 MVP 이슈 요약·사용자 확인

문서 인계 기준 추가: MVP요약/v0.5.24_MVP_이슈해결_요약.md. v0.5.24 정상 동작 사용자 확인을 기록하고, 일반 영상의 사용 가능한 범위를 기준으로 M3 Motion Skeleton 단계 준비. 보류한 Norma 의상 가림·누락과 관절 출처를 그대로 전달하며, M4 본 회전/Quaternion·SLERP 및 Unreal world/root/retarget을 현재 완료 기능으로 표시하지 않는다. 이번은 문서 작업으로 버전 증가나 새 코드 MVP ZIP 생성 없이 기존 v0.5.24 ZIP을 보존했다. 요약 문서는 기존 ZIP 생성 이후 추가된 별도 문서다.

요약: [v0.5.24 MVP 이슈해결 요약](../MVP요약/v0.5.24_MVP_이슈해결_요약.md)

---

## 2026-10-20 / v0.5.24 늦은 인물 등장·시작 프레임 선택

v0.5.24: 기본SAM2대상확인/추출은0프레임없음시첫YOLOX후보를탐색한다. 재생바를원하는위치로이동후대상확인을누르면해당프레임과후보번호를고정한다. 0프레임에서대상확인은자동등장탐색, 0보다뒤위치에서는정확한그프레임만검사한다. 최초후보가오검출/배경인물이라면원하는뒤프레임에서명시선택가능. 초기프레임검색은identity검증이아니며후보가여럿이면사용자선택필요. 시작전프레임을잘라내거나보간하지않고None/빈mask로유지, 이후기존가림·분실정책은보존. 모델/가중치다운로드없음.
기본 SAM3D+SAM2 경로에서 인물이 나중에 등장해도 최초검출/사용자선택 프레임으로 추적을 시작한다. 원본 전체 프레임번호·시간은 유지하고 시작 전에는 ROI/관절/예측을 만들지 않는다. 기존5분/18000프레임 제한·모델·회전·후처리 순서는 유지. M2 IN_PROGRESS. 일괄추출 재시작/실제GPU추론/사용자GUI 종료 없음.
4MD/case61 동일SHA 보관/v0.5.24 MVP 저장.

---

## 2026-10-20 / v0.5.23 최대 5분 입력

v0.5.23: GUI/CLI 처리 입력은 최대300초·18000프레임, MP4/최대2GiB/각변1920px 이하 짝수 해상도. M0 메타데이터 검사 자체는 더 큰 해상도를 읽을 수 있지만 추출 규격과 다르다. 길이공통정책 core/video/limits.py, 긴SAM2 저장수 제한 core/pose2d/sam2_memory.py. 기존 모델·SAM2대상추적→SAM3D→후보→관절검사→부위재추정→재관측 순서 유지. 기존 프로그램 프로세스는 재실행해야 새 제한 적용. 배치추출 재시작/사용자 프로세스종료 없음.
사용자 요청으로 입력·추출 지원을 최대5분(300초)/18000프레임으로 확장했다. 1920px 이하 짝수 해상도/2GiB 파일 제한은 유지한다. 5분60fps까지 프레임 한도에 들어가며 더 높은fps는 길이 이내라도 총프레임 한도에 걸릴 수 있다. 모델·대상선택·회전·추론횟수는 유지. Norma 의상가림은 알려진 한계로 보류, M2 IN_PROGRESS.
원본4MD 갱신/case60 동일SHA 보관/v0.5.23 MVP 저장.

---

## 2026-10-20 / 일괄 추출 사용자 중지

MP4 일괄 작업은 사용자 요청으로 취소, 자동 재개 없음. 사용자가 프로그램에서 직접 추출한다. 기존 완료분/부분 출력 보존 및 상태 명시. 추론 알고리즘/버전/기본 설정 변경 없음.

---

## 2026-10-20 / v0.5.22 MP4 7개 일괄 추출·성능 확인 (진행 중)

실행 현황: v0.5.22 기본 GUI 경로로 원본 폴더 MP4 7개 새 일괄 추출 중. 최근 의상 mask/MotionBERT/native point 실험은 자동 경로에 추가하지 않았다. batch.json이 영상별 상태/출력경로/선택 대상/검증 프레임 수를 기록한다. 현재 LongSword 보정 진행/나머지 대기, 전체 완료나 M2 통과 아님. GPU 배치와 GUI 추출 동시 실행으로 성능 비교 오염이 확인됐으며 단독 실행 비교가 필요하다.

---

## 2026-10-20 / v0.5.22 독립 관측 검사·SAM3D 관절 프롬프트

독립관측검사→SAM3D positive point conditioning→관절가설후검사의별도비교경로를추가했다. 원본이미지픽셀/선택대상ROI를유지하며기존SAM3D의학습된관절prompt기능을이용한다. MotionBERT3D/XYproxy를측정으로전달하지않고시간모델과독립2D의역할을구분한다. 새모델/의존성없고기존full기본모드는유지한다.
가이드재추정은bodydecoder전용대조이며수동앵커UI를복구하지않았다. 사용자클릭을받는것이아니라조건통과한독립모델관절최대2점을nativeprompt로전달한다. 결과는미검증MHR70joint sidecar만저장하고native MHR회전/UE/스켈레톤규격은변하지않는다. 관측이없는2초대망토다리는미해결범위다.
독립2D관측을검사한뒤SAM3D native positive point token으로재추정하는비교경로를연결했다. M2 IN_PROGRESS. 이경로는미검증모델관측을조건으로쓴새모델추정이며실제관절정답확정이아니다. 기본자동프로그램/원시/native MHR회전은유지하고새관절sidecar만별도저장한다. 새모델/가중치/패키지다운로드없음.
실제Norma218frame검사→80eligibleframe→12고른표본/47focus포함→24image추론+23point decoder갱신.10표본후검사통과/18·156거부대조유지.47의가이드잔차는24.68/14.39px→1.55/3.16px이나입력관측정답은미검증.2초대다리관측통과0. 모든기존입력과requestSHA불변. 새GPU실행/초기API실패원인·해결과정을증거로보존했다.
검증46고유PASS(신규16+mask prompt8+부위16+자동5=45/목록GUI1독립),모두exit0;compileallPASS. 신규는3프레임hint/2점한도·입력불변,score/의상/관측누락/점프/independentID5종보류,tracking/segment/scene/누락4경계,후검사개선·큰길이변화거부,정확한호환처리·hint범위,취소/순서,파일기반가이드·표본외None·원시보존/목록,무관측GPU미실행,실패미게시다. 증거validation/sam2/guidance-v0522.
원본4MD 갱신/case57 SHA 동일 복사/v0.5.22 MVP 저장. 기존 사용자 결과·MVP·HOME ZIP 보존.

---

## 2026-10-20 / v0.5.21 독립 RTMPose·MotionBERT 비교

독립시간모델비교경로 RTMPose-m(COCO17)→H36M17 adapter→MotionBERT-Lite(global-lite)를추가했다. 공식HF가중치저장소의Apache2.0 LICENSE/고정revision/SHAmanifest를확인·보존했다. 기존SAM3D/MHR70제품기본경로/사람mask추적은유지하고출력비교만추가했다. 동일대상ROI라모델간차이가대상갈아타기때문에생기지않도록했다. runtimeoffline/기존CPUONNX·GPUTorch환경사용/새패키지없음.
새sidecar는H36M17정규화모델출력이며MHR70joint로확장하거나UE본회전으로변환하지않는다. root/foot/retarget단계와도구분한다. 입력2D의의상오류가남아M2 IN_PROGRESS/정확도개선미확정.
기존SAM3D와독립적인RTMPose2D→MotionBERT-Lite시간추론의명시적비교경로를추가하고Norma218프레임을실행했다. M2 IN_PROGRESS. 기본SAM3D/사람추적/자동후처리는그대로유지한다. 모델교체배포나MHR70회전변환은하지않는다. 새출력은별도H36M17정규화좌표이며미터/UEworld가아니다.
실제Norma218frame1clip최종실행완료. RTM218새CPU추론,MotionBERT정방향/flip2GPUforward,strictcheckpoint/weights_onlyloadPASS. source/raw/modelmanifest/requestSHA불변.55/60/66/73표본을2D·3D로시각확인했으나관절정답개선확정없음. confidence와smoothness를정확도지표로쓰지않음.
검증34PASS(신규11+기존pose2d17+자동5=33/GUI목록1독립),모두exit0,compileallPASS. 신규는COCO/H36M좌우·proxy/입력불변,nonfinite/outsideconfidence,정규화·역변환/low-scoreclip,flipinvolution,3종경계분리,누락/243chunk/순서,파일기반별도출력/원시불변,취소/실패미게시,MHRread-only비교매핑이다. 증거validation/sam2/independent-v0521.
원본4MD 갱신/case56 SHA 동일 복사/v0.5.21 MVP 저장. 기존 사용자 결과·MVP·HOME ZIP 보존.

---

## 2026-10-20 / v0.5.20 SAM3D 직접 마스크 입력 비교

현재SAM3D의native mask조건후보를표본비교하는명시적실험경로를추가했다. 사람전체mask또는의상축소mask를원본픽셀·동일ROI와함께직접전달한다. 추적박스/후처리감점/시간보간과구분한다. 기존worker의기본호출은변하지않고자동후처리에도연결하지않았다. 결과는새MHR70카메라상대joint sidecar이며원시MHR회전/Skeleton/UE규격변경없음. 독립시간모델은이번에추가하지않았으며상업조건과입력2D오류해결가능성을추가검토해야한다.
가림 영상 근거 보강을 위해 같은 SAM3D의 native mask conditioning을 비교했다. M2 IN_PROGRESS. 원본픽셀·같은ROI를유지한3변형이며후보선택후감점/보간과다르다. 기존자동제품/원시/앞단계결과는유지하고표본추론만별도저장했다. 새모델/패키지/다운로드없음.
실제Norma55/58/59/60/61/62/64/66/68/70/73/75의12표본,새GPU33회(무mask12/사람mask12/의상축소9). 같은ROI확인·원본RGB미수정·모든입력해시불변. 출력2D변경량은후보차이일뿐정확도수치가아니다. 심한60/66의상오류미해결,새기본값채택안함. 증거validation/sam2/mask-prompt-v0520/{verification.json,body-comparison.jpg,model-audit.md}.
검증47PASS(신규8+부위16+내부mask17+자동5=46,목록GUI1독립),모두exit0;compileallPASS. 신규는정상축소/입력불변,과다삭제·빈/동일mask·크기거부,estimator동일픽셀·ROI/선택적mask전달,3종invalid/stale/cancelGPU차단,파일기반3변형계획·표본외None·목록/원본보존,실패미게시다.
원본4MD 갱신/case55 SHA 동일 복사/v0.5.20 MVP 저장. 기존 사용자 결과·MVP·HOME ZIP 보존.

---

## 2026-10-20 / v0.5.19 양방향 가림 자세 후보 비교

가림 복원의 새 후보를 만들기 위한 양방향 시간 후보 생성기를 실험 경로로 추가했다. 팔다리 방향/길이 보간과 제한적인 몸통 reference 보강의2변형이며 관측을 새로 얻는 모델이 아니다. MHR70 camera-relative joint sidecar만 저장하고 native MHR회전/Skeleton/UE 규격은 바꾸지 않는다. 기존 자동 파이프라인은 그대로다. 긴가림/회전의다리복원은실패한범위로명시하고0.6초이내의근거제약후보만비교한다. 다음은더나은영상신체·발관측또는별도시간모델후보검토가필요하다.
앞뒤 기준 프레임을 이용한 팔다리 후보와 몸통 기준 보강 후보를 분리 구현·비교했다. M2 IN_PROGRESS. 모델 미검토 프레임은 실제 보이는 정상 관절로 확정된 것이 아니며 새 결과는 unobserved_temporal_hypothesis_not_measurement다. SAM3D새추론/새모델/패키지 없음. 기존 자동 제품 및 입력 데이터는 유지한다.
실제Norma218프레임/후보구간45~90: 두변형모두45/46/51~55/59~64/68/69의15프레임변경. limb16가설(왼팔15/오른다리1), body-context17가설(위16+torso1). limb에서151요청은기준부족/긴간격,5요청은영상이동충돌로보류; body-context는body이동17요청보류. source/raw/선택/전신/검사/의상감점baselineSHA불변,새GPU추론0. 정확도개선미확정,심한다리문제미해결.
검증57PASS(신규13+부위16+영역8+재관측14+자동5=56/GUI목록1독립),모두exit0,compileallPASS. 신규는요청부위/몸통고정·입력불변,4종경계,누락/장기간격거부,구면방향·SO3/반대방향,취소/순서,무요청분리출력·stale거부,큰영상/몸통이동거부,취소미게시,기존provenance오색표시방지를포함한다. 증거validation/sam2/temporal-v0519.
원본4MD 갱신/case54 SHA 동일 복사/v0.5.19 MVP 저장. 기존 사용자 결과·MVP·HOME ZIP 보존.

---

## 2026-10-20 / v0.5.18 내부 마스크 일관성·후보 감점 비교

내부 영역 일관성 보강 및 후보 감점 실험을 추가했다. 사람 밖에 있는, 사람과 연결된 hair/cape 픽셀을 제한 보존하며 불일치/가림은 낮은 가중치로 반영한다. 기존 사람 tracking 및 자동 후보·관절 결과에는 적용하지 않는다. 사용자seed 의상 분리의 진단→부모 불일치 보강→soft penalty 비교까지 진행했다. 다음은 의상에 붙은 후보밖에 없는 구간에서 가림 자세/몸통 기준의 후보 생성 개선이다. 최종 UE애니메이션/회전 보정 단계가 아니며 camera-relative MHR70 sidecar다.
사용자 승인에 따라 사람 밖 내부 영역의 제한적 보존과 후보 soft cost 비교를 구현했다. M2 IN_PROGRESS. 망토/머리카락은 기존 작업자seed SAM2 결과를 재사용하며 자동 semantic 인식이 아니다. 기존 사람 추적/마스크/관절/회전/자동 결과는 바꾸지 않았다. 이번은 명시적 실험 CLI/별도 결과다.
실제Norma218프레임 CPU 비교(의상 근거45~90): baseline 저장본과 정확히 동일 재현 후 감점만 추가,58/59/60/72/73/76/77의7프레임 변경. 실험 구간 밖 변경0. 의상 weight활성 cape45/hair16프레임, person밖 픽셀 보존 cape37/hair18프레임(의미 정확도나 개선률 아님). 모든 입력 해시 보존/새GPU추론0. validation/sam2/region-v0518/verification.json 및 body-comparison.jpg 참조.
검증61PASS(신규8+부위16+내부마스크17+재관측14=55,자동5,목록GUI1 독립), 모두exit0; compileall PASS. 신규 검사는 외부 붙은 hair 보존/시간확인,배경분리,넓은 cape감량,존재·시간누락 무감점,중복 비용상한/화면밖,잘못된 크기·NaN,기본0 비용 호환,무요청파일기반비교·목록·stale거부다.
원본4MD 갱신/case53 SHA 동일 복사/v0.5.18 MVP 저장. 기존 사용자 결과·MVP·HOME ZIP 보존.

---

## 2026-10-20 / v0.5.17 내부 의상 마스크 1단계 진단

사람 내부의 의상/머리카락 보조 마스크를 별도 진단 경로로 추가했다. 기존 제품 자동 경로(SAM2사람→SAM3D전신→검사→부위재추정→재관측연결)에는 아직 편입하지 않았다. Norma 한 구간의 작업자 seed 실험이며 자동 semantic parsing이 아니다. 원본 영상의 색/픽셀을 제거하지 않고 model joint/본/native회전/Skeleton도 바꾸지 않는다. 후보 검사에 사용할 근거가 되는지 먼저 확인한다.
단계: ①별도 영역 추적·품질 진단(이번) → ②부모mask/내부mask 불일치·가림 보강 → ③후보 감점 비교 → ④가려진 팔다리의 앞뒤 문맥 재추정 비교. 겹침만으로 팔다리 삭제/정상 확정하지 않는다.
사용자 승인 순서의1단계(사람 내부 망토·머리카락 별도 마스크 가능성 확인)를 구현·실제 검증했다. M2 IN_PROGRESS. 기존 SAM2 사람추적 및 5단계 관절 처리의 기본 알고리즘은 유지한다. SAM2는 의미 이름으로 의상을 자동 찾는 모델이 아니므로 이번 Norma 실험은 작업자가 영상60프레임에서 확인한 양성/음성 포인트를 seed로 준 것이다. 사용자 수동 앵커 UI를 복구하거나 모든 영상의 자동 의상 분리를 구현한 것으로 보지 않는다. 새 모델/패키지/다운로드 없음.
실제Norma46프레임: cape37프레임 기본검사통과(정확도 아님)/9검토, hair16통과/30검토,35프레임 관절 겹침 검토. 사람영역 과다9, hair 밖누출30/작음10/면적급변9는 중복 가능. source/raw/selected/fullbody/review/part SHA는 기존v0.5.16 완료본과 동일. 새SAM2 영역 추적만 수행/새SAM3D추론0. body-crops/overview/hair-parent-review를 시각 확인했다. 옷 관절 오류 해결 또는 정확도 개선은 주장하지 않는다.
검증34PASS(신규17+관련기존16+GUI목록1 독립), 모두exit0; compileall PASS. 새 테스트는 prompt조건/경계, clip와미수정원칙,영역크기·존재·급변,겹침review,경로·크기,scene/누락/취소/범위GPU차단,실패결과미게시,실제파일기반진단·목록연결 포함.
원본4MD 갱신/case52 SHA 동일 복사/v0.5.17 MVP 저장. 기존 사용자 결과·MVP·HOME ZIP 보존.

---

## 2026-10-20 / v0.5.16 5번 재관측 연결

현재 자동 경로: SAM2 사람추적 → SAM3D 전신후보 → 관절별 검사 → 선택적 팔·다리 재추정 → 검사 후 재관측 연결. 마지막 기본 미리보기는 ‘재관측 연결 비교’다. 원시 및 앞 단계 비교를 유지한다. 새 출력은 camera-relative MHR70 joint sidecar이며 Unreal world animation/최종 본 회전 출력이 아니다.
5단계 중5번까지 구현·제품 연결. M2 IN_PROGRESS. 재추정 부위가 끝난 뒤 같은 target/segment/scene/pose track의 2~5연속 프레임을 검사한다. 검사 중인 부위, 누락 몸통, 위치0.45torso 초과, 길이비0.75~1.33 밖, 반대 방향, 화면 밖/마스크 이탈,20px 초과 투영 이동은 거부한다. 통과하면 고정 어깨/골반 아래의 두 본 방향을 정규화 혼합하며 현재 본 길이를 유지하고 마지막 프레임은 관측 모델값으로 정확히 돌아간다. 손/발·팔꿈치 보조점은 현재 wrist/ankle/elbow 상대 오프셋을 보존한다. Euler/native MHR회전은 변경하지 않는다. 사람 전체 누락을 채우거나 다른 장면/대상을 잇지 않는다. 모든 관측도 SAM3D 모델 추정이며 실제 관절 정답/가시성 보장이 아니다.
실제 Norma218프레임: 연결 후보44곳,1곳 수락/164~165프레임 전환,42곳 검토 지속/1곳 영상 이동 충돌 거부. 새 GPU추론0. source/sam3d/selected/fullbody/review/part SHA 불변. overview164~165에서 오른다리 전환 표시를 확인했으나 정확도 개선/의류 오류 해결은 판정하지 않았다.
검증: 이번 관련73 PASS(새 연결14+자동 비GUI5+기존 부위/검사/전신/목록52+GUI2 독립 프로세스), 모두exit0. compileall PASS. 전체 과거 테스트 재실행 수치가 아니다. 신규 검사는 길이/몸통/마지막 관측 복귀,4종 경계,누락,검토 지속/마스크/위치/길이 충돌의 부분 적용 방지,순서/취소,캐시/출처,자동 단계 실패의 앞 결과 보존을 포함한다. 증거 validation/sam2/reconnect-v0516.
원본4MD 갱신/case51 SHA 동일 복사/v0.5.16 MVP 저장. 이전 결과·MVP·HOME ZIP 보존.

---

## 2026-10-20 / v0.5.15 4번 팔·다리 선택 재추정

5단계의4번 요청 기반 팔·다리 문맥 재추정을 제품에 연결했다. 같은 ROI worker와 SAM3D full 모델을 쓰고 주변 frame으로 공간 crop/시간 경로를 구성한다. 시간 신경망으로 바꾼 것이 아니다. 고정 어깨·골반 아래/이후의 요청 부위만 바꾸며 native MHR회전/Skeleton 규격을 유지한다. 팔의 보조 elbow·손/발 child 정합도 보존한다.
자동 제품 경로: SAM2사람추적→SAM3D후보→전신묶음→관절검사→선택적부위재추정. 기존 전체 신발+다리 자동실행은 새 단계로 대체하고, 기존 leg 데이터/엔진은 비교·CLI용으로 보존한다. 미리보기는 ‘부위 재추정 비교’를 기본으로 연다. 검사/기준축/옛다리 비교 옵션은 남는다. 새 part-joints는 MHR70 joint sidecar이며 final UE animation이 아니다. source/raw/selected/review/fullbody hashes/revision1으로 캐시를 검사한다.
검증430고유PASS/권한1SKIP, 실제Norma218frame/212새GPU추론/48변경frame64부위frame. 정확도 정답은 미검증, M2 IN_PROGRESS/QA-002 VERIFYING 유지. 다음5번 실제 재관측 연결이며 의류 공통오추정과 초반무요청 사각지대가 남는다.
원본4MD 갱신, case50 SHA 동일 복사, snapshots/v0.5.15 MVP 저장. 이전 사용자 결과·MVP·HOME ZIP 보존.

---

## 2026-10-20 / v0.5.14 3번 관절별 궤적·검사

5단계의3번 관절 궤적·검사를 추가했다. SAM2 사람 추적과 SAM3D 전신 추정은 고정하고 선택된 전신 모델 관절을 구간별로 검사한다. 출력물 joint-review.json/영상 및 부위별 joint-repair-requests.json은 진단 자료이며 native MHR/Skeleton/관절 좌표를 바꾸지 않는다. 미리보기 ‘관절 검사’를 새 출력·기존 결과 양쪽에서 제공한다.
사람 마스크의 영상 근거·모델 후보 합의·시간/기하 기준은 각기 한계가 있다. 미표시 관절은 model_estimate_unverified이고 화면 안 또는 마스크 안이라는 이유로 가시성/관절 정확도를 확정하지 않는다. repair 요청에는 동일 구간 내 문맥과 이유·목표 부위를 넣고 torso는 별도 기준 검토 요청으로 구분한다. 이 요청을 실제 부위 재추정에 사용하는4번과 재관측 연결5번은 후속 작업이다. 기존 자동 다리 재추정은 별개로 유지한다.
검증 범위:414고유 테스트/권한1SKIP, 실제 Norma2개 각218프레임 검사·원본 SHA 보존. 새 GPU 추론0, 관절 좌표 교정0. M2 IN_PROGRESS 및 QA-002 VERIFYING 유지.
원본4MD 갱신, case49 SHA 동일 복사, snapshots/v0.5.14 MVP 저장. 이전 사용자 결과·MVP·HOME ZIP 보존.

---

## 2026-10-20 / v0.5.13 2번 전신 후보·몸통 기준 전달

승인된5단계의 2번을 보강: 사람 추적 결과를 고정한 상태에서 SAM3D 전신4후보와 몸통 기준을 공통 sidecar로 넘긴다. 신규 모델·의존성·기본 Skeleton/회전 포맷 변경 없음. native70관절/원시 MHR회전은 보존한다. spine_axis_proxy는 골반–어깨 파생 기준축이며 native 척추 체인과 다르다. 이미지 경계 여부와 가시성/정답 신뢰도를 구분한다.
자동 제품 경로: SAM2 사람 추적 → SAM3D full/전신 후보 선택 → fullbody-candidates.json 및 fullbody-reference.mp4 → 기존 다리 재추정. 새 전신 패킷에는4후보/부위별 관절/골반·어깨 중심/neck/길이/추적segment/원본 해시/입력 반전 출처가 포함된다. 관절별 시간 추적·검사(3번), 주변 프레임 부위 재추정(4번), 실제 관측 재연결(5번)은 후속이다. 현재 M2 IN_PROGRESS.
검증된 범위는395고유 테스트, 실제 기존Norma2결과 각218프레임 패킷, 회전8프레임 대체24회 새 GPU추론이다. 전체 새 영상의 관절 정확도가 개선됐다는 의미는 아니다. QA-002 기존VERIFYING 유지.
원본4MD 갱신 및 case48 SHA 동일 복사, snapshots/v0.5.13 MVP 저장. 이전 사용자 출력·MVP·HOME ZIP 보존.

---

## 2026-10-19 / v0.5.12 5단계 계획 중 1번 사람 추적 1차 보강

Milestone M2 IN_PROGRESS. Task: 사람 추적으로 선택 대상과 위치 유지. Goal: 관절 오추정이 대상 연결을 바꾸지 않도록 마스크 관측과 위치 예측·재연결 상태를 분리한다. Scope: core/pose2d/mask_tracking.py, app/sam2_worker.py, GUI 버전 표기, 관련 tests/validation. Acceptance: 2D 관절 없이 마스크 중심 Kalman 예측, 짧은 누락 상태 보존, 위치 이탈 마스크 거부, 연속 관측 재연결, 예측값을 실제 SAM3D ROI로 전달하지 않음. 이번 범위 구현·검증 완료. 2~5번의 전신 후보/관절별 검사/팔다리 주변 프레임 재추정/관절 관측 재연결은 후속 작업이다.

기존 경로는 첫 프레임 YOLOX 대상 선택 → SAM2 영상 메모리 마스크 추적 → SAM3D 자세 추정으로 이미 분리되어 있었다. 매 프레임 사람 detector나 관절 similarity를 새로 추가하지 않았다. 기존 BodyMotion의 constant-velocity Kalman을 재사용하되 실제 입력은 전체 사람 마스크의 가시 영역 중심이고 골반/척추/root 관측이라는 뜻은 아니다. 마스크가 옷·머리카락까지 포함할 수 있으며 관절 정답을 검증하지 않는다.

변경: 기본 SAM2 사람 추적에 motion_guard를 켠다. 마지막 박스와의 이동거리만이 아니라 예측 중심에 대한 잔차(직전 크기 대각선 0.65 이내)를 검사한다. 거부한 마스크는 예측기를 갱신하지 않는다. 최대0.5초 짧은 누락의 예상 중심/박스를 sidecar motion 필드 및 마스크 프리뷰 주황 박스로 표시한다. roi/person_bbox는 실제 유효 관측이 없으면 None이라 SAM3D가 예상 영역을 실제 관측으로 오인하지 않는다. 두 프레임 이상 누락 후 재연결은 2회 연속 위치 관측을 확인한다. 단순히 bbox IoU가 낮다는 이유로 회전 후보를 버리지 않는다. 장기 분실은 requires_reselection으로 남겨 다른 사람으로 자동 갈아타지 않는다. 중간 프레임 수동 재선택 UI/장기 재검출은 미구현이다.

전환 검사에서 발견한 원인·해결: 최초안은 hard cut에서 영구 잠금해 vivian265프레임 뒤229프레임, 뒤차기104프레임 뒤209프레임을 추가로 누락시켰다. 실제 vivian264~266 영상은 동일 캐릭터의 편집 시점 전환이었다. 이를 그대로 채택하지 않고, 전환 전 운동 예측을 폐기한 뒤 마스크 내부 HSV 히스토그램 reference bank(최대12개, 초기값 보존)와의 Bhattacharyya 거리0.55 이내 및 2연속 관측으로 새 위치 필터를 시작하도록 수정했다. 전환 확인 시간도0.5초로 제한하고 근거가 없으면 재선택 필요로 남긴다. HSV 색상은 학습된 ReID embedding/신원 증명이 아니며 같은 복장·다른 인물/거울·조명 변화의 한계가 남는다. track_id=1은 고정 선택 ID이지 신원 정답률 지표가 아니다. 별도 SAM2 신발3객체 경로는 기존 정책으로 유지한다.

실제 검증(수정 후 4영상 전체 새 SAM2 GPU 추적, 새 SAM3D 자세 추론 없음): Norma 218프레임/관측누락0/최장0.000초/박스점프검토5건; vivian 494프레임/관측누락1/최장0.033초/박스점프검토0건; kick 313프레임/관측누락3/최장0.033초/박스점프검토1건; LongSword 445프레임/관측누락0/최장0.000초/박스점프검토0건. 신규 ROI 예측 오인 전달0건. Norma와 뒤차기만 같은 첫 상자·프레임 수의 기존 outputs 기준이 있어 직접 비교했고 vivian/LongSword는 동일 조건 기존 outputs 기준이 없어 개선률을 주장하지 않는다. 박스 점프는 자세 확장/회전에 의해서도 발생하므로 오류 확정 수가 아니다. 신원/관절 정답 라벨이 없으므로 자동 대상 변경0건이나 관절 오추정 해결을 확정하지 않는다. 증거 validation/sam2/person-track-v0512/confirmed/{comparison.json,각영상/sam2-plan.json,mask-tracking.mp4}. 최초 실패안도 상위 폴더에 진단 증거로 보존한다.

테스트: 최종 코드의 비GUI376항목 및 GUI5항목을 분리 실행하여 총381 PASS/권한 opt-in1 SKIP. 새 사람 추적 검사11개(짧은 누락·잘못된 먼 마스크·재연결 연속성·컷·장기 분실·웅크림·프레임 순서·외형 확인·전환 속도 폐기), 기존 mask 검사14개 모두25 PASS/exit0. GUI5는 각 별도 프로세스 PASS. compileall PASS. QA-002 재관측: 초기 통합373 PASS 요약 후 exit -1073741816(0xC0000008), 재실행도 같은 비정상 종료. 원인 미확정, 테스트 assertion 실패는 없었다. 34파일 분리 중 test_video도15 PASS 요약 후 같은 종료가1회 있었으나 단독 재검15 PASS/exit0. 나머지 파일별 검사 exit0. 원인 해결 선언 없이 QA-002 VERIFYING을 유지한다. 분리 로그 test-split/summary.json 및 각 로그, 마지막25/15 재검은 도구 출력 참조.

사용: StartPrototype.cmd 재시작 → SAM3D+SAM2 모드에서 새 출력. 기존 생성 결과는 재계산하지 않는다. 사람 영역 추적과 뼈대 오추정은 별개이며 Norma 망토·옷에 다리 관절이 붙는 문제는 3~4번 관절 검사·부위 재추정에서 이어간다. 원본4MD 및 case47 해시 일치 보관, v0.5.12 MVP 저장. 기존 사용자 출력·MVP·HOME ZIP 보존.

---

## 2026-10-19 / v0.5.11 결과 패널 다크 색상 통일

증상: 새 결과 패널의 목록·탭·스크롤 영역에 기본 clam 밝은 색상이 남아 글자가 잘 보이지 않았다. 원인: 기존 공통 스타일만 설정했고 Treeview의 fieldbackground 및 Notebook/Scrollbar 전용 상태 색상을 지정하지 않았다.
조치: 목록 배경 #1b2637/글자 #e6edf6, 헤더·선택 탭 #293b52, 선택 행 #3478eb/흰 글자, 스크롤 홈과 패널 경계는 기존 화면의 #101722 계열로 통일했다. hover/선택 상태와 스크롤 손잡이·화살표 색상도 지정했다. 기능/파일 처리 동작은 변경하지 않았다.
검증: validation/check_v0511.py 실제 Tk 생성 및 스타일 lookup 6개 상태 PASS. 시각 변경이라 새 단위 테스트 및 GPU 추론은 실행하지 않았다. 사용자 출력 삭제 없음. 4MD 원본과 case46 해시 일치 복사, v0.5.11 MVP 저장. M2 품질 상태는 진행 중 유지.

---

## 2026-10-19 / v0.5.10 미리보기 옆 결과 패널

사용자 요청으로 결과 목록 버튼과 별도 모달 창을 제거하고 미리보기 오른쪽에 상시 결과 패널을 배치했다. Panedwindow 경계를 드래그해 미리보기와 목록 폭을 조절한다. 결과/프로그램 휴지통 탭, 결과 상세 상태, 하위 영상 선택, 미리보기, 삭제/복원/새로고침을 패널 안에서 제공한다. 결과를 선택한 뒤 미리보기 또는 더블클릭으로 열며 하위 영상 선택 변경도 바로 재생 화면에 반영한다. 추론을 재실행하지 않는다. 창 기본 1400x850/최소1200x700. 작업 종료 시 자동 목록 갱신, 작업 중 재생 전환/삭제/복원/갱신 차단. 파일 이동 검증 및 프로그램 휴지통 규칙은 v0.5.9 그대로다.
검증: 관련 8 PASS(파일 관리 3, 패널 통합 GUI 1, 기존 GUI 회귀 4). Tk GUI는 각 별도 프로세스로 검증했다. 실제 사용자 출력 삭제 없음, 새 GPU 추론 없음. 테스트는 패널의 메인 Panedwindow 소속/버튼 제거, 재생 후 패널 유지, 작업 중 삭제 비활성화, 재생 핸들 해제 후 삭제/복원과 기존 자동 처리·취소·입력 동작을 확인한다. 전체 비GUI 회귀는 직전 v0.5.9의 365 PASS/1 SKIP이며 이번에는 관련 검사만 실행했다.
원본4MD 및 case45 SHA 동일 복사, snapshots/v0.5.10 MVP 저장. 이전 MVP 및 HOME ZIP 유지. M2 진행 중이며 망토·회전 관절 오추정은 이번 UI 변경에서 수정하지 않았다.

---

## 2026-10-19 / v0.5.9 출력 결과 목록·미리보기·삭제·복원

요청: 기존 outputs 결과를 프로그램에서 조회하고 삭제한다. 상태: 구현 및 검증 완료, M2 품질 검증은 계속 진행 중.
StartPrototype.cmd를 재시작하고 하단 ‘결과 목록’을 연다. 결과 폴더별 이름/상태/프레임/수정 시간을 표시하고, 선택한 폴더의 하위 MP4 목록에서 원시·후보·다리·마스크 영상을 재추론 없이 재생한다. SAM 결과 열기의 자동 재개 경로와 별개다.
삭제 확인 후 선택한 최상위 결과 폴더 전체를 outputs/.trash/<UUID>/result로 이동한다. Windows 휴지통이 아닌 프로그램 휴지통이며 복원 탭에서 원래 이름으로 복원한다. 영구 삭제가 아니므로 디스크 공간은 즉시 확보되지 않는다. 이름 충돌 시 덮어쓰지 않는다. 실행 중 삭제/목록 열기는 차단하고 현재 재생 결과를 삭제할 때 캡처 핸들을 먼저 해제한다. 출력 루트/외부 경로/숨김 폴더/심볼릭 링크/junction은 이동 대상에서 제외한다. 새 의존성 없음. 기존 사용자 출력은 검증에서 삭제하지 않았다.
검증: 370 PASS, opt-in 권한 검사 1 SKIP. 비GUI 365건 및 GUI 5건은 별도 프로세스로 확인했다. 새 4건은 결과/하위 영상 발견, 휴지통·복원 내용 보존/충돌, 경로 이탈 거부, GUI 미추론 재생·핸들 해제·삭제·복원을 검증했다. 처음 기본 임시 폴더의 이동은 샌드박스 권한으로 실패해 workspace 검증 폴더로 변경했다. 기존 테스트 3건의 기본 cp949 읽기 오류는 명시적 UTF-8로 수정했다. 전체 회귀는 Python UTF-8 모드로 통과했다.
증거: validation/results-v059/verification.json. 기존 결과 12개, 미리보기 31개를 읽기 전용으로 발견했다. 새 GPU 추론 없음. 추정 알고리즘 변경 없음. 망토/회전 관절 오추정은 남는다. 원본4MD와 case44 SHA 일치, snapshots/v0.5.9 MVP 저장. 이전 MVP/HOME ZIP 보존.

---

# PROJECT.md

## Project

Video-to-Unreal Animation Tool

일반 RGB 영상에서 사람의 움직임을 추정해 3D Motion을 생성하고, 임의의 Humanoid Skeleton에 Retarget하여 Unreal Engine 5.8 Animation Sequence를 생성한다.

계획 기준: `계획서 수정/계획서 수정본2차.docx` (문서 버전 1.2, 2026-10-15) 및 이후 사용자가 승인한 본 MD의 보완 사항.

---

## Product Rules

2026-10-15 사용자 승인 보완: M2의 선택 기능으로 몸통 축/손발의 프레임별 수동 지정, 오검출 검사, 최대0.2초 2D 예측, 연속 관측 재연결을 추가한다. raw world와 최종 Motion Skeleton 규격은 유지하며 guidance2d sidecar로 출처를 분리한다. 모델 추정 몸통만으로 인물 후보를 강제 배제하면 회전 회귀가 생기므로 기존 동일 대상 보호를 유지한다. 수동 몸통 축은 초기/중간 명시적 대상 선택에 사용한다. 실제 3D 깊이 복원과 M8 전체 보정 완료를 뜻하지 않는다.

- PC Desktop Application으로 개발한다.
- Web App으로 만들지 않는다.
- 기본 기능은 인터넷 없이 실행 가능해야 한다.
- 로그인 / 회원가입 / 계정 기능을 만들지 않는다.
- 사용자 데이터는 로컬 PC에 저장한다.
- 영상, 프레임, Skeleton, Motion 데이터는 기본적으로 외부 전송하지 않는다.
- 외부 AI는 선택 기능으로만 사용한다.
- Core Motion Pipeline은 외부 AI 없이 동작해야 한다.
- 기본 UX는 단순하게 유지한다.
- 고급 옵션은 Advanced UI로 분리한다.
- Windows를 1차 지원 OS로 한다.
- Unreal Engine 5.8을 기준으로 한다.

---

## Architecture

```text
Desktop App
│
├─ UI
├─ Application
├─ Motion Core
└─ Local Storage / Worker
        │
        ▼
   Motion JSON
        │
        ▼
Unreal Plugin
├─ Skeleton Analyze
├─ Bone Mapping
├─ Retarget
└─ Animation Bake
```

### Responsibility

Desktop App:

- Video Input
- 영상 속 캡처 대상 1명 지정과 추적 유지
- 2D Pose
- 3D Pose
- Motion Skeleton
- Bone Rotation
- Motion Cleanup
- Preview
- Export

Unreal Plugin:

- Motion Import
- Target Skeleton Analysis
- Bone Mapping
- Retarget Profile
- IK Retarget
- Animation Sequence Bake
- 생성 이후 프레임별 본 디테일 편집의 엔진 연동과 수정본 저장

---

## Core Pipeline

```text
Video
→ 선택 인물 지정 / 동일 대상 추적
→ 2D Pose
→ 3D Pose
→ Motion Skeleton
→ Bone Rotation
→ Root / Foot / Ground Correction
→ Motion JSON
→ Target Skeleton
→ Retarget
→ Animation Sequence
→ 필요 시 특정 프레임의 본 값 편집 / 수정본 저장
```

---

## Core Design Rules

- Pose Model 출력과 Unreal Skeleton을 직접 연결하지 않는다.
- 중간 표준으로 Motion Skeleton을 사용한다.
- Motion Processor와 Unreal 사이의 기본 데이터 경계는 Motion JSON으로 한다.
- Pose2D / Pose3D Backend는 교체 가능하게 설계한다.
- Motion Core는 UI에 의존하지 않는다.
- Motion Core는 Unreal API에 직접 의존하지 않는다.
- 좌표계 변환은 전용 계층에서 처리한다.
- 내부 단위와 Quaternion 규칙은 하나로 고정한다.
- 특정 Skeleton 이름에 종속하지 않는다.
- Bone Mapping은 이름 + 계층 + 위치 + 방향을 함께 사용한다.
- 자동 Mapping은 Confidence를 가진다.
- 수정된 Mapping은 Retarget Profile로 저장한다.
- 긴 Processing 작업은 UI Thread에서 실행하지 않는다.
- Processing은 Progress / Cancel을 지원한다.
- Cache는 삭제해도 원본 Project가 손상되지 않아야 한다.
- 영상 속 인물 선택과 Unreal Target Mesh 선택을 구분한다.
- 추적 대상이 모호하거나 분실되면 다른 인물로 임의 전환하지 않는다.
- 대상 추적 분실과 관절별 저신뢰 / 화면 이탈 / 결측을 구분한다.
- 원시 추정과 보정 결과를 구분하며 긴 가림이나 대상 전환 경계를 무조건 보간하지 않는다.
- 본 디테일 편집은 애니메이션 생성 이후에 수행하고 원본을 보존한 수정본으로 저장한다.
- 이번 계획 수정에서는 Motion Skeleton과 Motion JSON 규격을 변경하지 않는다.

---

## Model Licensing and M2 Backend

- 상업적 게임 제작·배포에 사용할 수 있는 코드와 가중치만 채택한다. VideoPose3D는 CC BY-NC로 도입 대상에서 제외한다.
- M2 기본 모델: MediaPipe Pose Landmarker Full, `pose_landmarker_full/float16/1/pose_landmarker_full.task`. 코드 Apache 2.0과 해당 Full 가중치의 개발팀 라이선스 답변을 확인했다. 다른 변형에 자동 확대 적용하지 않는다.
- 근거: https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE 및 https://github.com/google-ai-edge/mediapipe/issues/6306 (2026-06-10 개발팀 답변). 모델 사양: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker
- RGB 프레임 입력으로 image/world landmarks 33개를 출력한다. 기존 COCO17 JSON만으로 3D 추론할 수 없다. M1 TargetTracker 로직을 재사용하고 M2 후보는 MediaPipe segmentation 관찰 박스로 생성하고 무효 mask는 관절 박스로 fallback한다. crop 대신 전체 프레임으로 좌표·스케일을 유지하며 분실 경계에서 모델 추적 상태를 초기화한다. M2 실행에는 RTMPose/YOLOX 가중치가 필요 없다. 기존 M1 실행 경로는 유지한다.
- WorldLandmarks는 엉덩이 중점 기준 미터 단위 추정값이며 전역 Root Motion이 아니다. 관절 대응·축·스케일·visibility/presence 의미를 명시하고 Motion Skeleton 변환은 M3에서 처리한다.
- 설치 시 정확한 버전·가중치 URL·SHA256·라이선스/NOTICE를 기록하고 네트워크 없는 실행을 확인한다. v0.3.0 M2 preview에서 설치·연결·원시 출력·프리뷰를 구현했다. v0.3.2에서 vivian 중복과 LongSword 관절 박스 축소를 개선했다. Norma 회전 검출·재연결 실패(M2-005)가 남아 M2 최종 통과는 아님.
- Apache 2.0에는 추론 출력 애니메이션을 비상업용으로 한정하는 조항이 없다. 입력 영상의 권리는 별개다. 도구/가중치 재배포 시 라이선스와 해당 고지 조건을 준수한다.
- 기존 M1 RTMPose/YOLOX 가중치의 상업 사용 조건도 별도 확인한다. 전체 파이프라인이 검증되었다고 간주하지 않는다.

## Initial Scope

지원:

- 한 번에 선택한 인물 1명 캡처 (여러 인물 영상에서 1명 지정 포함)
- Full Body
- Humanoid
- 5~15초 영상
- 720p~1080p
- 24~60fps
- 걷기
- 달리기
- 팔 동작
- 앉기 / 일어나기
- 고정 또는 완만한 Camera

초기 제외:

- 여러 인물의 모션 동시 생성
- Finger Capture
- Facial Capture
- Non-Humanoid
- 심한 Camera Shake
- 고난도 Acrobatics
- 영화급 Motion Capture 품질

---

## Quality Modes

```text
Fast
Balanced
Quality
```

Balanced를 기본값으로 한다.

---

## Milestones

```text
M0  Project Foundation
M1  2D Pose / 대상 추적 보완
M2  영상 기반 3D Pose / 시간 연속성·가림·빠른 동작 검증
M3  Motion Skeleton
M4  Bone Rotation Solver
M5  Unreal Motion Preview
M5.5 Target Skeleton Analyzer
M5.6 Auto Bone Mapping
M5.7 Retarget Profile
M6  Generic Humanoid Retarget
M7  Animation Bake
M8  Motion Cleanup
M9  Desktop Workflow / 생성 후 본 디테일 편집
M10 Optional AI Assist
M11 Packaging
```

기본적으로 위 순서대로 진행한다.

M1 보완에서 UI 없는 초기 대상 지정과 동일 인물 유지 Core를 먼저 제공한다.
M2는 MediaPipe Pose Landmarker Full로 영상에서 33개 관절을 추정하고 시간 연속성과 결측 처리를 검증한다. VIDEO 모드 추적을 학습된 전후 프레임 Lifter와 동일시하지 않으며, 본격 떨림·짧은 누락 보정은 M8에서 구현한다.
M9에서는 클릭·드래그 대상 선택 UI와 M7 생성 결과의 프레임별 본 편집을 제공한다.
2026-10-15 사용자 요청으로 CLI 반복 입력을 줄이는 임시 Desktop prototype을 M2 개선 전에 추가했다.
v0.3.1은 Tkinter/tkinterdnd2 기반의 영상 파일 드래그 입력·출력 버튼·로컬 재생·진행률/취소 창이다.
기존 M1/M2 처리 API를 재사용하고 모델·포맷·추적/보정 알고리즘은 변경하지 않는다.
M9 전체 UI/프로젝트 관리/본 편집 완료나 향후 최종 UI 프레임워크 확정을 의미하지 않는다.
본 편집은 Retarget Profile의 본 역할 매핑 수정과 별개이며, 저장 형식과 편집 API는 해당 단계에서 확정한다.

머리카락·의상·장식품에 관절이 붙는 오추정은 다음 단계에서 나눠 다룬다.

- M2 초반: 해당 영상을 기준 테스트에 포함하고 전후 문맥의 효과와 지속 오추정을 평가한다. 필요하면 2D 모델 / 인물 crop 개선 여부를 판단하되, 모델 교체는 별도 결정 후 진행한다.
- M3 / M4: 일정한 3D 본 길이, 관절 계층과 회전 제약으로 비정상적인 구조를 억제한다. 2D 투영 길이는 고정하지 않는다.
- M8: 순간적인 튐과 짧은 누락을 보정한다. 지속적으로 잘못 붙은 위치를 smoothing만으로 복구했다고 간주하지 않는다.
- M9: 자동으로 해결하지 못한 구간을 생성 후 프레임별 본 디테일 편집으로 수정한다.

M1은 v0.2.2에서 사용자 확인을 받아 마무리했다. 잔여 관절 오추정이 완전히 해결된 것으로 간주하지 않는다.

---

## Portfolio MVP

최소 완료 조건:

- Desktop App 실행
- MP4 입력
- 지정한 인물 유지와 추적 분실 경고
- 3D Motion 생성
- Motion Skeleton 생성
- Bone Rotation 생성
- Unreal Import
- Target Skeleton 자동 분석
- Auto Bone Mapping
- Mapping 수동 수정
- Retarget Profile 저장
- 서로 다른 Humanoid 2종 이상 Retarget
- Animation Sequence 생성
- Root Motion On / Off
- Foot Lock On / Off
- Fast / Balanced / Quality
- Offline Core Processing
- No Login
- Local Storage
- 생성 후 특정 프레임의 본 값 수정 / 주변 구간 프리뷰 / 원본 보존과 수정본 저장

---

## Document Priority

```text
1. User Instruction
2. PROJECT.md
3. HARNESS.md
4. AGENTS.md
5. CURRENT_TASK.md
6. PROGRESS.md
```

제품 목표나 Architecture 변경은 일반 코드 수정으로 처리하지 않는다.

## M2 v0.3.3 보완 상태

Full 기본 모델과 전체 프레임 관찰을 유지하되, 원본 후보가 없는 짧은 구간만 직전 대상 crop을 동일 Full IMAGE 모드로 재검출한다.
좌표는 원본으로 역변환하고 실제 관측이 선택되지 않으면 null/invalid를 유지한다. Motion JSON/표준 Skeleton/모델/의존성은 변경하지 않는다.
Norma 추적은 부분 개선됐으나 후반 분실과 Vivian/Norma 팔 오추정은 M2-005/006 OPEN. M2 최종 통과/M3 착수로 간주하지 않는다.

## 2026-10-15 승인: 1차 추출 후 2차 보완

M2를 통과 선언하지 않고, M3/M4/M8에 관련된 본 길이 제약/누락 보간/다리IK의 작은 실험을 선택적 후처리로 연결한다. 기존 native33 원시 결과와 Motion Skeleton 규격은 유지. completion3d는 별도 실험 sidecar이며 UE animation schema가 아니다. 주황색 추정/미해결을 명시한다. 접지/수동3D편집/회전애니메이션은 후속 작업.

2026-10-16 사용자 승인: SAM 3D Body를 선택적 GPU 영상 모드로 연결. 기본 MediaPipe 유지, native MHR70 실험 JSON/overlay 별도 저장. 첫 프레임 선택 ROI 고정, 기존 MP33 guidance/completion 혼용 금지. SAM 적용만으로 M2 통과 선언하지 않음.

2026-10-16 사용자 승인 추가: SAM에도 2차 발 보간/명시적 긴 누락 추정 연결. 원본 MHR70 보존, hip-relative native70 보완 결과 별도 저장. 기존 MP33 본 규격은 변경하지 않음.

## SAM 현재 처리 구조 (2026-10-16 사용자 승인, v0.3.9)

기존 고정ROI 실험을 대체: 매프레임 YOLOX Person Detector → TargetTracker → 선택ID1 ROI갱신 → 해당ROI만SAM3D. 검출/추적 전처리 후 별도GPU추론으로 실행. 초기후보확인도 같은검출기, 다중후보 자동변경 금지. SAM native70/version2의 프레임별 ROI/tracking 및 누락 outputs=null 저장, 이전version1은 보완호환. 분실프레임 SAM/발보완 금지. SAM전용 짧은재연결은 약0.4초와연속2회확인, 장기분실/모호성은재선택필요. 기존 MediaPipe/M1 및 최종 Motion Skeleton 규격 유지. Norma65이후 모호성/관절오추정은 미해결.

## 복합 대상 연관 점수 (2026-10-16 사용자 제안, v0.4.0)

SAM추적 가중치 시작값 IoU.25/예측중심유사도.25/신뢰관절유사도.30/외형유사도.20. 기존 RTMPose2D를 추적연관 보조로 재사용하고 최종3D는SAM. 유효관절부족시해당항목제외·재정규화, 동일전역관절중복만통합, 모호·장기분실보호유지. 외형은현재HSV로학습형ReIDembedding미구현. 기존M1/MediaPipe 기본추적은유지. 점수/정규화/입력유효성은로그로검증하고 정확도개선은별도판정한다.

## Kalman 몸 중심 예측 / 비교 지표 (2026-10-16 사용자 승인, v0.4.1)

SAM추적에골반우선/어깨-골반offset/박스보조2D관측Kalman(위치·속도,픽셀·초) 적용. bbox는crop영역으로유지하되ID연관에몸중심예측·오차범위사용. 겹침즉시영구정지를제한시간임시보류·추가확인으로대체,관측없음/모호함은filterreference업데이트및SAM·발보완금지. 긴누락은여전히재선택필요. M1/MediaPipe기본정책유지.

tracking-metrics에끊김평균·최대·횟수,박스/신뢰몸중심점프,신원변경검토플래그와관측coverage를분리저장. 플래그는실제ID변경정답아니며신원정답없을때확정수null. 4개동일관측A/B와원본샘플/비교영상으로판정하고추적률을관절정확도로표현하지않음. root는2Dproxy이며3D루트이동아님.

## 몸 중심 관측 검사 / v0.4.2 (2026-10-16)

사용자 승인 순차 개선 1번: SAM Kalman에 골반/어깨 몸통 길이의 넓은 2D일관성 검사와 관측선택 진단 추가. 비정상쌍은 box_fallback이며 원시관절 무효판정/수정이 아니다. 4개 회귀에서 끊김 지표 동일. 다음2번Q/R,3번재연결,4번지역재검출,5번장기재식별,6번누락후처리로 작은 변경/개별비교 진행. 기존M1/MP·모델·스켈레톤·ML의존성 유지. M2미통과.

본 회전은 기존 M4 Local Bone Quaternion 계획에 따라 구현하며, q/-q 부호연속성·최단경로SLERP·시간간격기반alpha 및 빠른동작감쇠 검증은 M4/M8에서 수행. 현재 추적 끊김 개선과 별도이며 현버전 구현 기능으로 표시하지 않는다.

## Kalman 관측 전환 R 보정 / v0.4.3 (2026-10-16)

사용자 승인 순차 개선2번: 어깨기반중심→골반복귀첫승인에만 직전승인어깨base std하한을R에유지. 이후같은소스는기본오차,박스노이즈전파금지,승인되지않은후보로Q/R학습금지. Q/추적gate/재연결조건/장기분실보호유지. 같은4개캐시에서Sword2프레임회복·나머지선택박스동일,Norma긴분실미해결. 다음3번재연결조건을별도작업으로비교. ML확률보정/모델교체/스켈레톤규격변경아님. M2통과아님.

## 짧은 누락 후 재연결 / v0.4.4 (2026-10-16)

사용자승인3번: SAM만짧고모호성이없으며몸/관절/외형/위치근거가모두충분할때추가확인대기생략. 기존기본2확인및장기분실보호유지. 겹침이력은강한후보대기에도보존. LongSword421대기만제거,실제누락420은관측으로위장하지않음. 나머지선택결과동일. 다음4번예상위치주변검출은별도작업이며현재구현하지않음. 모델/포맷/스켈레톤변경없음. M2미통과.

## 예상 위치 주변 재검출 / v0.4.5 (2026-10-16)

사용자승인4번: SAM선택대상의짧은누락에서예상위치주변을동일로컬YOLOX/RTMPose로재검출하고원본좌표로추적후보에추가. 전체검출유지,기존추적gate유지,장기분실/모호성우회금지,예측ROI자체는SAM입력아님. 4개비교LongSword전체445프레임추적/Norma초반2프레임회복,나머지동일. 관절정확도·긴분실미해결. 모델교체/스켈레톤변경/장기재식별없음. 다음5번은별도작업. M2미통과.

## 긴 누락 뒤 조건부 재식별 / v0.4.6 (2026-10-16)

사용자승인5번:SAM만승인된HSV/COCO관절참조(최대8)기반장기후보평가. 모호성·겹침이력없음/누락5초내/독립근거충분/3연속확인에한해같은선택ID복귀. 학습형ReID/생체신원인증아님. 복귀시필터·속도초기화,새tracking_segment로SAM/보완에보존,긴공백무추론·무보완. 영상·metrics에검토표시. M1/MP기본유지. Norma170복귀부분개선,전체M2미통과. 다음6번짧은관절누락후처리만별도진행. 표준MotionSkeleton/본회전규격미변경.

## 짧은 관절 누락 후처리 / v0.4.7

사용자승인6번:SAM후처리에팔꿈치·손목0.2초이하명시적결측보간. 부모상대좌표/유효끝점/길이·방향제약/동일추적segment필수. 기존발보완유지,다리최근방향·보간도구간경계보호. 원시보존및추정표시,가려진실제동작/유한관절오추정정답복원아님. 1~6구현을마쳤으나M2는잔여긴분실/본오추정과사용자확인때문에IN_PROGRESS유지. 후속M3/M4자동진입하지않음.

## 관절 위치 검토 도구 / v0.4.8

다음품질작업승인에따라M2유한관절오추정의자동수정전검토도구추가. SAM보완후본길이·고립방향후보를자홍표시/pose-quality.json/다음검토로탐색. 관절값·모델·추적·표준Skeleton불변. 정상빠른동작도후보가능,지속오추정미검출가능. 후보수는확정오류/해부학정확도아님. 사용자검토후교정범위를별도검증. M2계속IN_PROGRESS.

## 추가 회귀 요구 / 웅크림·뒤돌기·편집 컷

사용자뒤차기영상에서자세변형분실뿐아니라후방다른인물연결이확인됨(M2-020 OPEN). 후속추적개선은검출존재/중심관측전환/겹침·중복/장면컷을분리하고,같은옷의두인물재연결을회귀기준으로포함한다. 단순허용범위완화로추적률만늘리지않는다. 현재코드정책변경아님.


## 2026-10-16 v0.4.9 / M2-020 다른 인물 재연결 방어 — 부분 개선

사용자 승인한 첫 단계: SAM 추적에 최근 주변 인물의 박스·HSV 외형 기억과 신뢰도 있는 얼굴 관절 중심 보조 검사를 추가했다. 원래 대상보다 기존 주변 인물 위치에 명확히 가까운 재연결 후보를 거부한다. 얼굴 관절 5개 중 신뢰도>.5/유한좌표 3개 이상, 주변 인물 거리<.15 대각선, 원래 대상 거리>주변 거리2배+.1, 면적비 .5~2, 외형거리<.55를 함께 요구한다. 최대 4개/약1초 기억, 짧은 분실 중 위치 갱신은 유일 후보 2회 연속 확인, 외형은 동결. 장기 latch/겹침 후보는 위치 학습 안 함. M1 기본 추적에는 적용하지 않음. 학습 기반 ReID나 모든 대상 전환 방지 보장은 아님.

원인·시도: 첫 박스/외형 방어와 두 번째 위치 갱신만으로는 실패했다. 76→88 후방 인물 박스는 가려짐 해제로 폭이 커져 IoU .419/HSV거리 .488로 기준 탈락했다. 신뢰도 있는 머리 중심 위치를 보조 증거로 추가한 세 번째 비교에서 88~103 후방 인물 연결 차단. 원본 313프레임의 캐시 검출을 공유하고 필요한 ROI 재검출만 실제 실행했다. 기존 출력/원시 관절값 덮어쓰기나 SAM GPU 재추론은 하지 않았다.

제한/악화도 기록: 뒤차기 추적181→78/313, 최장 공백3.208→7.853초. 78부터 원래 대상 복귀도 실패한다. 후방 인물 16프레임 제거 외에 기존 후속 추적87프레임도 유지되지 않음. 박스 점프2→0/신원검토표시3→0은 미추적 증가의 영향이므로 정확도 향상으로 해석하지 않는다. 웅크림·회전 끊김 해결/M2 통과로 처리하지 않는다. 원래 대상 복귀, 중심 관측 전환, 겹침 이력과 편집 컷 분리는 다음 작업이다.

회귀: Norma131/218, vivian494/494, Sword869/908, LongSword445/445. 네 영상은 추적 수뿐 아니라 모든 프레임 레코드가 baseline과 동일하다. 정답 라벨 기반 전 구간 ID 검증은 아니다. 신규9사례 포함 일반234PASS(비GUI174+48, GUI12 각 exit0), 권한 opt-in 1SKIP, compileall PASS. QA-002 기존 일괄 종료 문제는 해결 선언하지 않는다.

증거: validation/m2/rival-guard-v049/{final,selected,head-position}/summary.json 및 verification.json. 앱 새 추출부터 적용, 기존 출력은 변경하지 않음. M2-020 OPEN 유지. 원본4MD 다음 case 보관 및 v0.4.9 MVP 저장.


## 2026-10-16 v0.4.10 / M2-020 웅크림·뒤돌기 중심 관측과 재연결 보완

원인: 골반 관절이 사라지면 이전 골반-어깨 벡터를 현재 어깨에 더하는데, 몸을 숙이거나 회전하면 그 방향이 달라진다. 기존 어깨 관측 오차가 너무 작아 후보를 motion gate로 거부했다. 어깨 대리 관측 표준편차 하한을 max(박스대각선*.03, 보관몸통길이*.35,6px)로 조정해 Kalman이 이를 실제 골반처럼 확신하지 않게 했다. 좌표 자체를 바꾸지 않으며 골반/박스 기본 오차와 물리거리 제한은 유지한다. 첫 복귀 골반의 기존 어깨 오차 하한 정책도 유지한다.

초기 시도에서는 추적211프레임이지만 컷 뒤 후방 인물 선택을 영상에서 확인해 미채택했다. SAM 짧은 분실 재연결에서 뼈대유사도<.25(또는 없음)와 HSV외형거리>.3이 함께 나타나면 위치·박스 점수만으로 승인하지 않는 방어를 추가했다. .5 뼈대 조건의 중간 시도는 실제 숙인 대상도 막아 미채택했다. 이 기준은 학습된 신원 증명이 아닌 보수적 휴리스틱이다. TargetTracker 기본은 OFF/SAM 경로만 ON, 주변 인물 방어 유지.

확정 비교: v0.4.9와 같은 원본 검출 캐시/실제 필요 ROI 재검출로 비교했다. 뒤차기313프레임 중78→196추적, 최장공백7.853→2.506초. 78/79 관측과87복귀,88~103 원래 발차기 대상 유지.119/217/229/237의 전경 발차기 선택을 영상 샘플로 확인했다. 공백은80~86(7),104~118(15),137~148(12),219~226(8),238~312(75).119는 편집컷 뒤 긴 재식별이다. 전체 ID 정답 검증이나 컷 처리 완료로 표현하지 않는다. 박스점프0→1(119), 신원검토표시0→4는 복귀 증가와 함께 나타나므로 확정 ID 오류 수로 해석하지 않는다.

회귀: Norma131→132/218.45~48 누락이45~46으로 줄지만65~66 누락은65~67로1프레임 악화,92~169 긴누락 유지. vivian494/494,Sword869/908,LongSword445/445는 모든 선택박스·ROI·segment 동일. 정답 관절 개선 검증은 별개다. SAM GPU 재추론은 하지 않았으며 기존 출력/원시 관절/사용자 영상은 변경하지 않았다. 새 앱 추출부터 적용된다.

검증: 신규4사례 포함238PASS(비GUI178+48, GUI12 각각exit0), 기존권한opt-in1SKIP, compileallPASS. 어깨 보정 측정좌표 불변/미승인 관측의offset 학습 방지, 독립 신원 증거 부족 거부와 한쪽 증거 유효 승인 시험. QA-002 기존 통합 종료 문제 해결 선언 없음. 정책명 갱신에 따른 기존 테스트 기대값 수정, PowerShell Python 기본cp949로 한글 포함 파일 읽기 오류는 UTF-8 명시 후 수정·최종 검증했다.

증거: validation/m2/center-recovery-v0410/final/summary.json,verification.json,kick-review.jpg. 채택하지 않은 시도는 rival-guard-v049/center-{uncertainty,identity,independent-evidence}에 보관하며 확정 비교는 v0410 final이다. 다음은 겹침 뒤 복귀와 편집 컷 구간/대상 선택 정책, 머리카락·의류 관절오추정 M2-006. M2-020 OPEN/M2미통과 유지. 원본4MD 다음case·v0.4.10MVP 보관.


## 2026-10-16 / 개발 중지·SAM 2 인수인계 (제품 v0.4.10 유지)

사용자 최신 선택은 BoT-SORT가 아니라 SAM 2 마스크 추적이다. SAM 2 구현/설치/다운로드/검증은 시작하지 않았고 진행하겠다는 답변만 했던 상태를 명시했다. 직전 BoT-SORT 조사는 읽기만 했으며 공식 소스 셸 접근은 DNS Errno11001로 실패, 패키지 설치나 코드 변경 없음. 사용자가 개발 중지 후 다른 곳에서 이어가도록 요청해 CURRENT_TASK.md를 독립 인수인계로 확장했다. 완료 범위·실패 후보·정량 결과·남은 오류·SAM 2 실험 순서·파일/환경/검증 경로·보관 규칙을 정리. 기존 제품코드/환경/출력은 변경하지 않았고 새 MVP·버전 없음. 네 MD를 다음 case22에 복사·해시 확인한다. 같은 폴더에서는 CURRENT_TASK부터 읽고 관련코드를 확인하면 재개 가능하나, 다른 머신에는 프로젝트/모델/영상/환경도 필요하다.


## 2026-10-16 / 집 작업 이전 묶음 준비

사용자 요청으로 현재 프로젝트의 집 PC 이전 ZIP을 만든다. HOME_TRANSFER.md에 환경 복원/입력 경로 안내를 추가하고 transfer에 데스크톱·GPU 설치 목록을 기록했다. 코드·모델·필요 SAM 소스·CUDA torch wheel·검증 자료를 포함하고 인증정보/가상환경/중복MVP/캐시는 제외한다. 영상은 ZIP 내부 transfer/input_videos와 input-map.json으로 제공하며 과거 절대경로는 덮어쓰지 않는다. SAM 2는 여전히 미구현, 제품 v0.4.10 유지. 압축 생성 후 ZIP CRC와 파일별 manifest/전체SHA256을 검증한다. 새PC 복원 실행까지 검증한 것은 아니다.

포장 시 추가 확인: 기존 Videos의 LongSword/Norma/Sword/vivian 및 sam-request.json이 가리키는 뒤차기 원본이 모두 현재 경로에 없어 원본5개는 ZIP에 미포함. 기존 outputs/검증용 영상과 자료는 포함한다. 원본 재처리는 집에서 별도 원본 준비가 필요하며 input-map.json에 누락 상태를 기록한다.


## 2026-10-19 v0.5.0 / SAM 2 마스크 추적 시험 모드

사용자 재개 요청에 따라 BoT-SORT가 아닌 SAM 2.1 Small을 준비·연결했다. 첫 프레임 YOLOX 대상 박스만 초기화에 사용하고 이후 2D 관절 연결 없이 SAM 2 영상 메모리로 마스크를 추적한다. 마스크 외접박스+여유 ROI를 기존 SAM3D worker에 전달하며 RGB 원본을 보존한다. 기존 v0.4.10 SAM 추적 및 M1/MediaPipe 기본 경로 유지. GUI에 별도 SAM 3D + SAM 2 마스크 (시험), 대상 마스크 프리뷰 추가. 기존 발·팔 누락 보완/품질 검토 유지. M2 통과 아님.

공식 소스2b90b9f5ceec907a1c18123530e92e794ad901a4/가중치184416285bytes,sha256 6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38. 공식 Apache2.0 가중치/코드와 고지 보존. Windows native GPU 실행, 기존 CUDA Torch는 읽기 전용 공유하고 SAM 2 source/deps는 .validation/sam2에 분리. 연결요소 CUDA 확장/구멍채우기 OFF. 1024 프레임텐서를 전량 적재하지 않고 JPEG+2프레임 캐시 어댑터 사용, 모델 소스·가중치 미수정. 앱 실행 중 다운로드 없음.

검증: 원본5개는 여전히 없고 사용자 응답에 새 경로는 없었다. 남아 있는 짧은 원본클립을 두 추적기 모두 클립 시작에서 새로 초기화해 비교했다. Norma35→40/40(기존최장.1006초→0), Sword 실제전경12→12/12, LongSword12→12/12, vivian60→60/60. 합119→124/124. 첫 Sword index1 시험은 거울 반사를 잡아 제외, 실제 인물 index0 재검증. 잘린 영상의 후보 번호를 원본 시작 번호와 동일하다고 가정하면 안 됨. 샘플로 실제 대상 유지 확인했으나 전구간 정답ID/원본전체/뒤차기 검증은 아니다. 마스크는 의류·머리카락·장식도 포함하므로 3D 관절 오추정 해결과 구분한다. SAM 2는 기존 추적보다 느렸으며 plan elapsed는 child 시작/모델로딩을 전부 포함하는 전체처리시간이 아님.

LongSword12프레임 실제 SAM 2→SAM3D GPU 추출→기존 누락 보완 PASS,마스크/뼈대/보완영상각12전체디코딩,원시sam3d.json SHA유지. 실제Tk 새모드 선택/마스크보기/seek6 PASS. 일반252PASS(비GUI192+48/GUI12 각exit0),권한opt-in1SKIP,compileallPASS. 신규14사례는 불확실 마스크 ROI 차단/분할/점프/segment 분리/첫선택/관절미호출/취소자식정리/GUI설정 검증. QA-002 기존 통합 종료 문제 해결 선언 없음.

구현 중 오류: 테스트의 기본cp949로 UTF8 요청JSON 읽기 실패→테스트 UTF8명시 후PASS. 한글 절대경로 cv2.imwrite가 검토JPEG를 저장하지 않아→imencode+Path.write_bytes로 바꾸고4개 검토자료 생성·확인. 이는 추적 정확도 문제가 아니며 수정 후 확인했다. SAM 2 checkpoint/소스 다운로드와 추가 의존성 설치는 공식 공개 경로, 기존 인증정보 접근 없음.

잔여: 빈/불안정/과분할/급변 마스크를 hold하고 재관측은 새segment로 분리하지만 마스크는 신원증명이 아니다. 교차/완전가림/편집컷에서 다른 대상 연결 가능. 장면 전환 처리·중간 재지정 UI·3D시간축 회전 보정 미구현. 사람수/뼈대 중심 기반 지표는 SAM 2에 없어 관련 자동신원검토0을 정확도 개선으로 해석하지 않는다. metrics limits에 별도 표기. M2-020/M2-006 OPEN,다음은 원본 다중인물·회전영상으로 검증.

증거 validation/sam2/final/summary.json,verification.json,각review.jpg·mask-tracking.mp4, integration-longsword/integration-verification.json,gui-verification.json. 원본4MD 다음case 보관, v0.5.0MVP 저장. 20261016 HOME ZIP은 v0.4.10 묶음 그대로이며 새모드 포함으로 오해하지 않게 HOME_TRANSFER에 알림 추가.


## 2026-10-19 / SAM 2 원본 전체 검증 1차 (제품 v0.5.0 유지)

사용자 제공 C:/Users/user1/Desktop/애니메이션추출의 vivian/Norma/뒤차기4종류 + 추가1개 Sword만검증(LongSword제외). 첫대상0/0/0/1을직접확인했고세기존영상은v1원본SHA일치. 두추적기모두전체처음부터실제실행,기존짧은클립결과재사용없음. 전체1933프레임1691→1908관측. vivian494→494/494,Norma132→218/218,뒤차기196→313/313,Sword869→883/908. 최장누락각0→0/2.617→0/2.506→0/1.625→1.042초. Sword잔여25는883~907의어두운페이드/엔딩(unstable_mask1/object_not_visible24)으로일반회전중분실과구분,수치에서임의제외없음.

두비교/마스크영상각전체디코딩·JSON정렬·원본SHA/실행코드해시불변확인.190고정/사건샘플의26장sheet검토에서는원래대상을유지,후방인물/거울전환미확인.전체정답ID라벨검증아님,마스크/숫자ID유지만으로정확도판정안함. 기존추적보다SAM2 walltime이대략3~4배느렸음(전체값summary참고,렌더/3D제외).

M2-020 기존회전/대상연결은이번SAM2입력에서크게개선됐으나OPEN유지. M2-021 OPEN: Norma회전마스크의일부배경혼입/범위흔들림,박스점프69/90/91/92/95 확인. 5점프전부가오류라고확정하지않으며ROI범위안정성후속검토필요. 뒤차기컷104/157/238이같은segment로이어지는미구현도잔여. 정확한사람추적과연속애니메이션구간분리는별개. SAM3D전체추론/3D관절평가는이번범위밖,M2-006머리카락·의류오추정OPEN. 다음은마스크/ROI안정화·컷분리후올바른ROI의3D회전검증.

제품코드/기본모드/버전미변경. 전체자동테스트불필요하게재실행하지않았고새비교스크립트compileall및실제1933프레임검증완료. 기존252PASS/권한1SKIP는직전v0.5.0기록이다. 증거validation/sam2/full-v1/{README.md,summary.json,verification.json,manual-review.json,initial-targets.jpg},각영상tracking-comparison.mp4/review/sam2/mask-tracking.mp4. 원본4MD다음case25복사·해시검증. 기존MVP덮어쓰기없이v0.5.0검증1차증거ZIP별도보관.


## 2026-10-19 / v0.5.1 SAM2 입력 ROI 안정화 — M2-021 부분 개선

확인된 구조: SAM2 마스크의 외곽이 매 프레임 달라지면 그 박스에 고정 비율 여유만 더한 SAM3D 입력 ROI도 즉시 축소·확대된다. 실제 동작과 마스크 오류가 섞이므로 모든 이동을 오검출로 단정하지 않는다.

조치: core/pose2d/roi_envelope.py를 SAM2 worker에 연결했다. 외곽 확장은 즉시 반영하고 안쪽 축소만 시간상수 0.12초로 완만하게 한다. 현재의 패딩 포함 관측 ROI를 항상 전부 포함한다. 추가 면적 1.8배 초과, 큰 위치 변화, 프레임 불연속, segment 변경에는 초기화한다. 미관측 프레임에는 ROI를 만들지 않고 이력을 비운다. raw person_bbox·마스크·추적 ID·추적 판정·segment는 바꾸지 않는다. roi_observation/roi_stabilization으로 관측과 최종 입력 영역을 구분한다. 기존 pose 추적 모드에는 적용하지 않는다.

비교: 직전 full-v1의 같은 4개 영상 전체 1,933프레임에서 저장된 SAM2 관측을 재생했다. 새 전체 모델 추론이 아니다. 입력 영상 SHA 검증, 추적 관련 필드 불변, 모든 현재 관측 ROI 포함, 영상 경계·면적 제한·누락 보존을 확인했다. 관측 1908/1933 유지(vivian494/494, Norma218/218, 뒤차기313/313, Sword883/908). Sword 엔딩 미관측25는 그대로다.

Norma의 **SAM3D 입력 ROI 중심** 점프(전 프레임 raw mask bbox 대각선 대비 이동 >0.15)는 5→3회, 최대 이동 0.3154→0.2492. 중심 이차 차분 평균 0.03075→0.01632(약47% 감소). 나머지 ROI 중심 점프는 vivian0→0/뒤차기1→1/Sword0→0이다. raw 마스크 박스 점프5회가 줄었다는 뜻이 아니다. 이차 차분은 실제 움직임도 포함하는 입력 영역 지표로 관절 정확도가 아니다. 기존 패딩 ROI 대비 최대 추가 면적은 Norma1.563배/vivian1.511배/뒤차기1.511배/Sword1.354배: 주변 배경이 더 포함되는 절충이다.

검증: Norma ROI 비교영상218프레임 전체 디코딩, 사건6프레임(69/90/91/92/95/100) 시각 검토. 별도 보관 LongSword12클립은 새 CUDA SAM2→ROI보정→SAM3D 실제 실행, JSON12/마스크영상12/overlay12 정렬 및 전체 디코딩 PASS. 이것은 전체 영상 3D 품질 검증이 아니다. 자동테스트 **267 PASS/권한 opt-in 1 SKIP**, 신규15사례. GUI12는 비Tk9+실Tk3개별 실행, 각 exit0. compileall PASS. 기존 QA-002 통합 native 종료 이슈 자체를 해결한 것은 아니다.

남은 문제: M2-021 OPEN(부분 개선). 마스크 배경 혼입·머리카락 누락을 교정하지 않으며 머리카락/옷/장식 관절 오추정 M2-006, 회전 추적 M2-020도 OPEN. ROI가 넓어져 모델 결과가 달라질 수 있으므로 3D 관절 품질은 추가 검증해야 한다. 뒤차기 컷104/157/238 구간 분리도 미구현이며 abrupt_geometry 초기화는 컷 검출기가 아니다. M2 통과 아님. 다음은 컷 구간 분리 후 Norma 회전 구간의 실제 SAM3D 관절 결과 비교.

증거: validation/sam2/roi-stability-v051/{summary.json,README.md}, 각 sam2-plan-replay.json, Norma/{roi-comparison.mp4,review.jpg}, integration-longsword/verification.json. 적용은 새 추출부터, 기존 outputs는 그대로 보존한다. GUI를 재시작한 뒤 SAM 3D + SAM 2 마스크 (시험) 모드로 실행한다. v0.5.1 MVP 신규 저장, 원본 4MD case26 복사·해시 검증. 기존 HOME ZIP은 v0.4.10이며 갱신하지 않았다.


## 2026-10-19 / v0.5.2 장면 전환 구간 분리 — M2-022 부분 해결

증상·원인: 편집 컷 전후가 하나의 tracking_segment에 남아 있으면 짧은 관절 누락 보간/최근 방향 참조/ROI 축소 보정이 서로 다른 동작 구간을 연결할 수 있었다. 뒤차기104/157/238과 추가 확인된 vivian265는 실제 컷이다. Sword의 빠른 동작은 픽셀 차이만으로 컷으로 판단하기 어려웠다.

조치: core/video/scene_cuts.py에서 원본 BGR 축소영상의 픽셀 차이·변화 픽셀 비율·HSV 색 분포 차이를 함께 확인한다. 임계값은 평균차이0.08/변화비율0.20(픽셀차이0.12초과)/색분포거리0.20. 한 프레임 뒤를 확인해 직전 화면으로 돌아오는 단일 프레임 섬광의 양쪽 경계를 억제한다. 사람이 빨리 움직여도 색 분포가 유지되면 컷으로 보지 않는다. 원본 디코딩 중 계산하며 신규 패키지·모델·네트워크 요청은 없다.

SAM2 시험 모드에서 컷의 첫 프레임부터 scene.index와 tracking_segment를 증가시키고 ROI envelope를 초기화한다. 기존 분실 후 복귀 segment도 합산해 유지한다. 마스크/대상 선택/관측·누락 판정은 변경하지 않고 SAM2 영상 메모리도 유지한다. SAM3D JSON과 completion JSON에 scene/segment를 전달하며 이미 구현된 팔·다리 짧은 누락 보간 및 최근 방향 참조의 segment 경계 보호를 작동시킨다. 마스크/원본뼈대/보완 프리뷰에 scene 또는 CUT를 표시하고 SAM 리포트에 컷 목록과 신원 미검증 경고를 남긴다. 원본을 여러 파일로 분할하거나 애니메이션 에셋을 출력하는 기능은 아니다.

검증: 같은 원본4개의 1,933프레임을 새로 RGB 디코딩해 컷을 검사하고 저장된 full-v1 SAM2 관측에 구간 정보를 적용했다(이 비교 전체가 새 모델 추론은 아님). vivian265→2구간, 뒤차기104/157/238→4구간, Norma/Sword 컷0. 4개 전환점의 전후8프레임 시각 검토. 현재 입력들에서 관측1908/1933 유지, raw 박스·추적 판정 불변, 컷 ROI 초기화 확인. 전체 정답 컷 라벨 데이터셋 정확도 검증은 아니다.

별도로 뒤차기 원본 전체313프레임은 새 CUDA SAM2 실제 실행: 세 컷 검출, 기존 person_bbox/추적 판정 차이0. 그 전체 추적 이력을 유지한 원본100~107프레임(재인코딩 창8프레임)을 실제 SAM3D→보완까지 실행했고 segment [0,0,0,0,1,1,1,1]과 scene.cut 전달을 검증했다. 마스크영상313/overlay8/completion8 전체 디코딩 PASS, 원시 sam3d.json SHA 보존 PASS. 컷 프레임의 보완 프리뷰 라벨 시각 검토. 새 테스트는 합성 단일프레임 섬광/빠른 이동/페이드/구간 초기화/기존 분실 복귀 유지 및 컷을 가로지르는 손목 누락 보간 차단을 포함한다.

테스트 **275 PASS/권한 opt-in 1 SKIP**(신규8), GUI는 비Tk9+실Tk3개별 exit0, compileall PASS. QA-002 통합 native 종료 문제를 고친 것은 아니다. 검증 스크립트의 최초 확인 단계는 run_completion 반환값(path, counts)을 path로 취급해 TypeError가 났다. 반환값 분해로 수정하고 이미 생성된 GPU 결과를 재사용해 확인·렌더 단계만 재실행했다. 제품 추출 오류나 모델 재추론 실패가 아니다. --verify-existing 옵션으로 이를 재현·확인할 수 있다.

한계·남은 일: M2-022 OPEN(급격한 컷 분리 적용, 전환 처리 전체 완료 아님). 색·구도가 유사한 컷은 놓치거나 급격한 조명·카메라 변화는 컷으로 오인할 수 있다. 페이드/디졸브와 다중프레임 섬광은 지원하지 않고 한 프레임 삽입 컷은 섬광으로 억제될 수 있다. 컷 뒤 대상 신원은 보장하지 않으며 자동 재선택이나 SAM2 메모리 초기화도 하지 않는다. 기존 completion의 본길이·가림자세 prior 통계는 전체 클립에서 계산하므로 구간별 대상 교체를 지원한다고 해석하지 않는다. 이번에는 시간 보간 경계만 분리했다. M2-021 마스크 배경 혼입/ROI 흔들림 부분 개선, M2-006 머리카락·옷·장식 관절 오추정, M2-020 대상 유지 모두 추가 검증 필요. **M2 미통과**. 다음 우선 작업은 Norma 회전 구간의 실제 SAM3D 관절 결과를 기존/안정화 ROI로 비교해 마스크 문제와 3D 추론 문제를 분리하는 것이다.

증거: validation/sam2/scene-cuts-v052/{README.md,summary.json,integration-verification.json,completion-cut-review.jpg}, 각 scene-events.json/sam2-plan-replay.json, Kick/vivian/review.jpg, fresh-Kick/sam2-plan.json와mask-tracking.mp4, integration-Kick-100-108의sam3d.json/overlay.mp4/보완결과. 원본 영상 SHA 불변. 추출은 새 실행부터 적용하며 이전 outputs와 v0.5.1 결과는 그대로 보존했다. GUI 재시작 후 SAM 3D + SAM 2 마스크 (시험) 모드로 사용한다. 원본 4MD 갱신 후 case27 복사·해시 검증, v0.5.2 MVP 별도 저장. 거대 SAM3D 환경/가중치는 기존 것을 재사용하고 20261016 HOME ZIP은 갱신하지 않았다.


## 2026-10-19 / Norma 전체 3D 입력 영역 A/B 검증 / 제품 v0.5.2 유지

실행: C:/Users/user1/Desktop/애니메이션추출/Norma.mp4의 동일 원본 전체218프레임을 기존 패딩 ROI(observed-roi)와 현재 안정화 ROI(stable-roi)로 각각 새 SAM3D GPU 추론했다. 두 입력 모두 같은 원본 파일을 직접 디코딩했으며 클립/재인코딩/검은 마스크 입력을 사용하지 않았다. SAM2는 전체 원본 이력이 담긴 저장 관측을 재사용했고, 대상·마스크·raw 박스·추적 판정은 고정했다. 입력 ROI 차이에는 흔들림뿐 아니라 면적·정규화된 크기·배경 맥락 변화가 함께 포함된다. 프레임별 독립 모델 출력의 원인 비교이며 3D 정답이 있는 정확도 시험은 아니다.

| 입력 영역 | 유한 70관절 출력 | 전체 상대관절 이동 P95 | 회전55~110 이동 P95 | 어깨축 최대 변화 | 자동 검토 후보 프레임 |
|---|---:|---:|---:|---:|---:|
|observed-roi|218/218|1.2501|1.6591|169.79°|19|
|stable-roi|218/218|1.2042|1.6639|160.94°|16|

상대관절 이동은 매 프레임 hip 중심을 뺀 12개 관절의 연속 이동을 두 조건 공통의 중앙 torso 길이로 나눈 값이다. 어깨축 변화는 연속3D 좌우 어깨 벡터의 각도다. 실제 회전 동작도 수치에 포함되며 작을수록 정확하다고 단정하지 않는다. 화면 안 투영은 가시성·정확도 또는 숨은 손발을 관측했다는 증거가 아니다. 구간0~217/55~110/92~169와 관절별 투영 누락·본 길이 변동의 원자료는 summary.json에 있다. 자동 검토 후보 수 역시 정답 오류 개수가 아니다.

시각 검토·결론: 입력 영역 안정화의 효과는 혼합적이며 Norma 회전 관절 문제를 해결하지 못했다. 전체 상대관절 이동P95는1.2501→1.2042로 소폭 감소하지만 회전55~110 구간은1.6591→1.6639로 거의 같다. 전체 어깨축90도초과는15→14회, 자동 검토후보는19→16프레임이나 실제 오류수로 해석하지 않는다. 44/45와66/67의 몸이 포함된 연속 원본에서도 예측 자세가 크게 달라지고,86의 안정화 조건에서는 손목이 머리카락에 붙는다. ROI는 출력에 영향을 주지만 ROI 흔들림만이 원인이라는 설명은 불충분하다. 추적은 유지된 상태에서도 가림·의상·머리카락이 있는 모습에서 프레임별 3D 관절 추정과 연속성이 불안정하다. 가림/비인체 외형/모델 학습 범위의 기여 비율이나 숨은 관절의 실제 위치는 이번 자료만으로 확정할 수 없다.

다음 작업: 기존 3D 검토 후보와 구분해 관절별 시간축 신뢰도 판정을 시험한다. 몸 중심·본 길이·부모 상대 방향과 이웃 프레임의 합의로 고립된 오추정 후보를 먼저 표시하고, 양끝이 신뢰 가능한 짧은 구간만 보간하는 방식을 비교한다. 실제 빠른 회전을 오류로 지우지 않는 검증과 불확실/긴 가림 표시를 포함한다. 현재 팔 보간은 화면 밖/명시적 누락만 처리하므로 화면 안의 잘못된 좌표를 정상으로 계속 전달하는 점을 개선 대상으로 삼는다. 전체 자세의 좌우·깊이 뒤집힘은 손목 보간만으로 해결됐다고 판정하지 않는다. 안정화 ROI의 전역 우월성이 확인된 것은 아니므로 단순 확장/평활 강화나 자동 전면 수정은 하지 않는다.

검증: 두 조건 원시 JSON218개씩, 보완 JSON218개씩, 원본 겹침 비교/공통 스케일 XY·ZY 비교/각 overlay·보완영상 총6개를 각각218프레임 전체 디코딩했다. 원본 SHA와 추론 worker SHA 불변, 원시 JSON SHA 보존 확인. 고정·사건·조건간 손목 차이가 큰 샘플 39프레임을 내보내 검토했으며 상세 시각 검토 범위는 manual-review.json을 따른다. 전체218프레임의 수동 정답 관절 라벨은 없다. 신규 검증 스크립트 compileall PASS. 제품 코드 변경이 없어 자동테스트 전체를 반복하지 않았다. 이전275PASS/권한1SKIP는 v0.5.2 제품 검증 이력이며 이번의 신규 테스트 수가 아니다.

M2-006 머리카락·의류·장식 관절 오추정과 M2-021 마스크/ROI 부분 개선은 완료 처리하지 않는다. M2 미통과. 이번에는 진단과 증거 저장만 진행했으며 GUI 기본값·모델·보정 알고리즘·버전은 변경하지 않았다. 기존 outputs와 v0.5.2 MVP를 보존하고 검증 증거 ZIP을 별도 저장했다. 원본4MD 갱신→case28 복사·SHA 검증. 다른 PC에서는 최신 CURRENT_TASK.md 및 코드/모델/환경/영상을 함께 준비한다.

증거 validation/sam2/norma-3d-v052/{run-manifest.json,summary.json,verification.json,manual-review.json,README.md}, roi-pose-comparison.mp4(왼쪽기존/오른쪽안정화), native3d-comparison.mp4, review의원본겹침/XY·ZY이미지와sheet, 각 조건의sam3d.json/overlay.mp4/verification.json과보완폴더. 원본 영상1개와 입력 경로 매핑은 검증 ZIP의 original_inputs에 포함한다. 기존 20261016 HOME ZIP은 갱신하지 않았다.


## 2026-10-19 / v0.5.3 관절 시간축 검사·제한적 보간 / M2-023 OPEN

확인된 원인: 기존 SAM 보완은 화면 안의 유한 좌표를 기본 유효값으로 전달했다. 이 때문에 화면 안 머리카락·의류에 붙은 관절이나 프레임별 자세 변경은 명시적 누락 보간의 입력이 되지 않았다. 단, 시간축 급변만으로 실제 빠른 동작과 오추정을 구분할 수는 없다.

구현: SAM 보완 단계에 core/pose3d/temporal_guard.py를 연결했다. SAM2나 SAM3D 추론·대상 선택은 변경하지 않는다. 원시 관절·2D 투영과 부모 상대 벡터를 검사한다. 최대2프레임/0.1초의 손목·발목 이탈에 대해 양끝 및 바깥 이웃의 방향 합의, 양끝 길이 일치, 고립 구간의 본 길이 이탈(0.65~1.35범위 밖), 2D 투영의 동시 이탈, 몸통·부모 위치 안정성, 같은 tracking_segment, 대상 유지, 기존 보완값의 출처를 모두 확인한다. 조건이 맞는 때만 부모 상대 방향/길이를 보간하며 나머지는 검토 표시로 남긴다. 급격한 어깨축 변화는 검토 전용이다. 장면 전환/추적 분실/긴 오류/지속된 잘못된 자세를 넘겨 보간하지 않는다.

수정값은 temporal_interpolated, 연결 손가락·발끝의 위치 이동은 temporal_parent_offset으로 구분하고 before_temporal/before_temporal_source를 보존한다. 손목·발목과 연결된 관절의 상대 오프셋을 유지하며 연결 그룹 자체가 일관되지 않으면 수정을 막는다. 손가락/발 모양을 새로 추론하는 것이 아니다. 원시 sam3d.json 및 이전 outputs는 바꾸지 않는다. 보완 JSON에 temporal_guard 이벤트·차단 사유·검토 프레임을 남긴다. 기존 자홍색 관절 검토 및 다음 검토 버튼의 pose-quality.json/리포트에도 새 후보를 합쳐 전달한다. 품질 후보/규칙 합의는 실제 오류 확정이나 관측 신뢰도의 확률값이 아니다.

실제 저장 추론 결과 재생: Norma 기존 ROI218프레임과 안정화 ROI218프레임, LongSword 짧은12, 뒤차기 컷 창8의 총456프레임을 기존 보완/새 보완으로 비교했다. 4개 전체 원본 영상 회귀나 새 GPU 추론이 아니다. **실제 자료 자동 보간0건, 좌표 변경0건**이다. Norma는 앞뒤 관절도 불안정하거나 몸 전체 방향이 바뀌어 조건을 충족하지 않았다. 안정화 Norma의 전체 검토 후보는16→24프레임(새 시간축 후보17프레임, 기존 후보와 겹침), 기존 ROI Norma는19→28(시간축22). 이는 검토 범위 증가이며 오류 감소나 정확도 향상 수치가 아니다. LongSword12/뒤차기8은 새 후보0이다.

주입 오류 검증: 30프레임의 합성 정상 자세에서 손목의 방향·길이와 투영을2프레임만 어긋나게 만든 별도 자료에서는 두 손목 값을 알려진 원래 값으로 복원했다. 손가락 상대 오프셋 보존도 확인했다. 실제 영상 개선 사례로 해석하지 않는다. 테스트18개는 손목/발목·1/2프레임 복원, 기존 관측·원본 보존, 컷/분실/몸 회전/3프레임 오류/길이 일정한 빠른 왕복/투영 불일치/부모 이동/경계/연결 그룹 불일치의 수정 금지 및 취소를 포함한다.

검증: 자동테스트 **293 PASS/권한 opt-in 1 SKIP**(신규18). 비GUI233+pose48+GUI12, 실제Tk3개별 exit0. compileall PASS. 기존 QA-002 통합 native 종료 문제 자체를 해결한 것은 아니다. 실제 입력 raw SHA 불변, 보완 비교 영상4개 각218/218/12/8 전체 디코딩, 합성 비교30프레임 디코딩 확인. Norma-stable을 제품 run_completion으로도 실행하여 raw 보존 및 report/pose-quality.json의 검토 프레임24 일치를 확인했다. 실제 비교45/86/95와 합성10 프레임 시각 검토. 현재 모델 원시값을 재사용했으며 모델/패키지 다운로드나 GPU 재추론은 없다.

남은 문제: **Norma의 머리카락·옷 오추정과 회전 불안정은 해결되지 않았다.** 특히86의 지속된 잘못된 손목 위치는 이번 고립 오류 판정으로 정확히 식별·복원됐다고 말할 수 없다. 전체 몸의 좌우/깊이/팔·다리 배치가 바뀐 것을 단일 손목 보간으로 고치는 데 한계가 있다. 실제 빠른 왕복과 잘못된 길이가 함께 관측되면 규칙이 실제 동작을 바꿀 위험도 남으므로 수정 출처와 이전 값을 보관한다. 기준을 낮춰 수정 건수를 늘리지 않았다. M2-023 OPEN(실제 자동 교정 효용 미입증), M2-006/M2-021/M2-020 및 M2 전체 미통과 유지.

다음 우선 작업: Norma44→45·66→67과 같은 몸 전체 추정 변경을 단일 관절 문제와 분리해 구간 단위로 진단한다. 현재 유효 프레임 자체가 잘못될 때는 전후 프레임 합의만으로 복원할 기준이 부족하므로, 같은 입력의 포즈 가설 재검토/신뢰할 수 있는 기준 자세 확보 방식을 먼저 비교한다. 무조건 평활·기준 완화·Euler 회전 보간으로 넘어가지 않는다. Quaternion/SLERP 본 회전 출력 단계는 여전히 후속 계획이다.

적용: GUI 재시작 후 SAM 결과의 보완 실행부터 적용한다. MediaPipe 보완·기존 추적 모드는 변경하지 않았다. 기존 출력/보완 폴더는 보존하며 새 보완 폴더를 만든다. 원본4MD 갱신→case29 복사·SHA 확인, v0.5.3 MVP 새 저장. 거대 SAM3D 환경/가중치는 기존 것을 재사용한다. 이전 HOME ZIP은 갱신하지 않았다.

증거 validation/sam2/temporal-guard-v053/{summary.json,integration-verification.json,README.md}, 각 completion-before.json/completion-after.json/comparison.mp4, synthetic-only의input/before/after와비교영상. 실제 추론 입력 출처와 SHA는 summary.json에 있다. 비교영상 왼쪽은v0.5.2보완/오른쪽은시간축검사추가, 자홍색은검토후보이다. 합성 폴더의 결과를 실제 Norma 수정 사례로 혼동하지 않는다.


## 2026-10-19 / Norma ROI·반전 후보 비교 1차 / 제품 v0.5.3 유지

사용자 요청으로 보간 대신 후보 재추론을 비교했다. 범위는 Norma 원본32~107의76프레임이다. 원본을 처음부터 디코딩했고 클립 재인코딩은 하지 않았다. 전체 원본에서 얻은 SAM2 대상·마스크 이력은 유지했다. 후보는①기존패딩ROI ②안정화ROI ③raw mask bbox에5%여유를 더한좁은ROI ④안정화ROI의수평반전이다. ①②는이전원본전체SAM3D출력의같은프레임을재사용(152자세),③④는같은로컬SAM3D GPU로새로추론(152자세)했다. 총304후보자세 비교이며4조건모두새모델추론이나4영상전체검증은아니다.

반전 후보는70관절 이름의left/right 매핑으로관절을바꾸고,영상x=width-1-x/카메라3D x부호반전으로원래기준에복원했다. 모든실제이름의매핑왕복과합성좌표왕복을검증했다. 입력ROI경계는width-x2,width-x1로반전한다. 반전전관절도같이보존했다. **관절좌표만비교**하며MHR body_pose/global_rot/카메라파라미터를변환하거나Unreal애니메이션으로출력하지않는다. 후보결과를정상SAM3D회전파일로위장하지않고joint-only별도schema로저장한다.

후보 선택 시험: 안정화ROI의0~25프레임에서얻은모델본길이·torso중앙값을공통prior로썼다(수동정답아님). 각후보의본길이로그편차,후보들2D중앙값과의차이,hip상대3D연속이동과후보전환벌점을비용으로삼아동적계획으로경로를구했다. 단항비용0.4*길이+0.2*2D합의,전이비용0.4*상대이동(3에서상한)+후보전환0.03. 여러후보가함께틀리면합의도틀릴수있고,매끈한오류가낮은비용을받을수있다. 자체예측의재투영을독립정답으로사용하지않았다.

수치(모두76프레임범위): 기존/안정화/좁은/반전고정경로의어깨축90도초과15/13/12/11회,선택경로7회. 안정화대비hip상대관절이동P95는1.5883→1.2870. 고정경로비용21.937/20.347/20.889/21.799,선택17.416. 비용최소화로정한지표가줄어드는것은정확도증명이아니다. 선택횟수는기존14/안정화23/좁은18/반전21,후보전환24회로아직잦다. 이전전체218프레임지표와직접비교하지않는다.

시각검토: 30샘플의기준대비선택영상5sheet,45/67/86/95의4후보확대,66/67/86의공통스케일XY·ZY를확인했다. **86에서좁은ROI후보는안정화조건의머리카락쪽손목을팔·장갑주변으로옮겨국소개선가능성을보였다.** 하지만66~67등에서후보들모두팔·다리배치가불확실하며선택3D자세도여전히크게바뀐다.80의손목등잘못된추정도남는다. 숨은관절의깊이/정확한좌우정답은없다. 전체적으로자동교체할정확도가검증된것은아니다.

결론: 후보를늘리는방법은일부프레임에서유용할가능성이있지만,**현재자동후보교체는채택하지않았다.** GUI/제품기본동작/보완/추적/버전은v0.5.3그대로다. 선택관절파일은검토용이며기존outputs·raw JSON·MVP를바꾸지않았다. M2-006/M2-020/M2-021/M2-023미해결및M2미통과유지. 다음은국소적으로좋은후보와모든후보실패구간을구분하고,확실한키프레임의손발·몸방향제약을쓴구간최적화또는여러프레임을활용하는추론방식을검토한다. 현재SDK가수동관절프롬프트를바로받는다고가정하지않으며,실패했던2D추적앵커를그대로재도입하는작업도아니다.

검증: 새후보152개는체크포인트키·형상감사및70관절유한좌표검증PASS. 원본/기준raw SHA와worker SHA확인,반전매핑왕복PASS,3개비교영상각76프레임전체디코딩PASS. 새시험10PASS(반전왕복/좌우·x축/이름오류/형상/순위동일후보/이동불변성/이탈후보/잘못된입력). 신규스크립트compileall PASS. 제품코드미변경이므로전체테스트반복없음;293PASS/권한1SKIP는이전v0.5.3제품검증이력이다. 새모델/패키지다운로드·가중치교체없음.

증거 validation/sam2/norma-candidates-v1/{request.json,candidates.json,summary.json,verification.json,manual-review.json,selected-joints.json,README.md}. four-candidates.mp4배치는좌상기존/우상안정화/좌하좁은/우하반전복원. selected-vs-stable.mp4는왼쪽안정화/오른쪽점수선택(미채택). native3d-selected-vs-stable.mp4는같은조건의XY·ZY공통스케일. 원본4MD case30 복사·해시검증, v0.5.3검증1차증거ZIP별도저장. 기존v0.5.3MVP및HOME ZIP은유지한다.


## 2026-10-19 / 다리가 옷으로 이동하는 관측 검사 / v0.5.3 유지

사용자는 직전 후보 비교에서 회전이 좋아졌다고 시각 확인했고, 남은 다리·옷 오추정을 기준 뼈대에서 벗어날 때 검사하자고 제안했다. 이 시각 평가는 기록하되 M2 전체 정확도 통과나 미변환 MHR 회전값의 애니메이션 출력 승인으로 확대하지 않는다. 이전76프레임 후보 선택 결과를 보호 기준으로 삼아 검사 실험을 진행했다.

확인1: 첫 프레임 무릎·발목 주변 특징을 LK optical flow로 계속 추적하는 간단 시험에서는 무릎 특징이 일찍 사라지고 발목도33~34프레임까지 성공한 뒤 끊겼다. 처음 자세/위치를 끝까지 강제하면 회전·가림에서 오래된 값을 기준으로 삼을 수 있다. 따라서 최초 뼈대를 고정하는 방식은 채택하지 않았다.

확인2: 각 후보의 무릎·발목 주변 영상 특징을 한 프레임 앞으로 추적하고 역추적 오차1.5px/영상오차25/그룹 내 이동편차4px/특징3개 이상으로 검사했다. 76프레임에서 이 점수를 후보 전체에 바로 더한 v1은 어깨축90도초과가7→9회로 늘고, 지원 없는 관절·프레임도135→156으로 늘어 미채택했다. 기존 upper-body 기준과 어깨축 합의cos0.94/상체hip상대RMS0.25torso/최소2개영상지원 및10px·20%이상 다리오차 감소를 요구한 v2는61/69 두 프레임만 바뀌었고 회전급변7회를 유지했지만, 핵심44/67의옷오추정은 해결하지 못했다. optical flow는 옷의 움직임도 따라가므로 다리라는 독립 증거가 되지 않는다. 두 실험은 validation/sam2/norma-leg-check-v1,v2에 보존하고 제품에 적용하지 않았다.

주요 검사 시험: **신발을 사람과 별도의 SAM2 마스크 객체로 추적**했다. 첫 프레임을 직접 확인해 모델 왼발(관절13)쪽 신발박스[375,860,437,983], 오른발(14)쪽[246,877,311,1001]을 실험자가 지정했다. 자동 신발 검출/UI 구현이 아니다. 기존 SAM2를 재사용해 원본0~107프레임108개에서 사람ID1/신발ID2,3을 새 GPU 전파했다. SDK·제품 worker는 수정하지 않고 실험 자식 안에서 빌더·원본 디코더를 감쌌다. 원본을 재인코딩하지 않고108프레임에서 디코딩을 종료했다. 발목 좌표를 마스크 중심으로 바꾼 것은 아니다.

마스크 관측 기준은 object score>0, 면적32이상, 최대 연결성분비율>0.7,logit안정성>0.55,초기면적대비0.2~4배다. 이 내부 기준 통과는 실제 신발 정확도나 신원 보장이 아니다. 발이 교차하면 두 ID가 같은 신발을 따라가는 현상을 확인했으므로, 마스크IoU>0.4일 때 한 영역으로 합쳤다. 한 신발만 보이면 한 발 후보만 검사하고 다른 다리는 미확인으로 남긴다. 두 영역이면 좌우 신원을 가정하지 않고 두 발목과 두 신발에 서로 다른 일대일 대응을 요구한다. 신발 영역과 예측 발목의 거리가18px를 넘으면 불일치 검토로 표시한다. 가려진 신발을 실제 관측처럼 만들지 않는다.

결과: 기존 후보 구간32~107의76프레임 중 신발관측이 한 영역44/두 영역31/없음1이었다. **신발 영역과 예측 다리가 불일치하는18프레임**은43,44,58,59,60,61,62,64,66,67,76,77,78,79,80,81,87,104다. 실제 오류 정답18개나 18개 수정 성공이 아니라 독립 관측과의 검토 후보다.44/67의옷에붙은다리를원본의실제신발영역과대조해검사하는사례를확인했다. 상체/팔 기준을 지키면서 신발관측까지 맞는 대체 후보가 없어 **자동 교체0건**이며, 기존 후보의 좌표·회전은 그대로다. 보완 비교 오른쪽은 신발 마스크 청색/검토 다리 주황색으로 표시하며 수정된 자세가 아니다.

검증: 기존3D후보 재사용(새SAM3D추론없음), 새SAM2 108프레임 전파 완료. 신발마스크 프리뷰12샘플0/32/44/45/61/66/67/69/86/95/100/107에서 영역 확인, 좌우ID중복 관측. 광류v2의44/61/67/69, 신발검사의44/67 시각 검토. 마스크·신발프리뷰각108, 광류v1/v2·신발검사비교각76 전체 디코딩. 원본/기준 raw SHA 불변 및 제품 주요 소스가v0.5.3 MVP와 같음을 확인했다. 관련시험 **21PASS=직전후보시험10+신규11**(합성텍스처이동/무특징미확인/지원된이탈/후보제한/잘못된비용/신발마스크중복/두영역일대일/관측없음). compileall PASS. 제품 자동테스트293PASS/권한1SKIP는 이전v0.5.3검증 기록이며 이번 전체 재실행 수가 아니다.

다음: 검사를 통과하지 못한 다리를 계속 정상값으로 신뢰하지 않도록 하는 근거를 확보했다. 복원을 위해서는 잘 잡힌 상체를 유지한 채 **신발의 2D 영역을 제약으로 다리만 다시 추정/최적화**하는 별도 단계가 필요하다. 신발 마스크 중심은 발목 관절이 아니고,2D신발관측만으로무릎굽힘·깊이·좌우가정해지지않으므로 본길이·투영·전후자세의 합의와불확실성 처리가 필요하다. 단순히 신발 중심에3D발목을옮기거나 숨은발을확정하는 방식은 사용하지 않는다. 기존모델 후보가모두틀린구간은 후보교체검사만으로 복원되지 않는다.

제품 v0.5.3/기본GUI/기존추적·보완 유지. 후보·다리검사 모두 현재 검증용 결과이며 아직 GUI 자동 실행에 연결하지 않았다. M2-006/M2-020/M2-021/M2-023 및 M2미통과 유지. 원본4MD case31 복사·SHA 확인, v0.5.3검증2차 증거 ZIP 별도 보관, 기존MVP·HOME ZIP 보존. 출력과 원시 추정값은 덮어쓰지 않았다.

증거 validation/sam2/norma-boot-check-v1/{summary.json,events.json,comparison.mp4,README.md}, norma-boot-mask-v1의sam2-request.json/boot-records.json/boot-ID마스크/boots-preview.mp4/review.jpg. 실패한 광류후보와 상체보호 버전은 norma-leg-check-v1/v2. 핵심 새파일 boot_mask_worker.py,boot_evidence.py,compare_boot_evidence.py,leg_flow_guard.py,compare_leg_flow.py. 후보 비교1차의원본입력및후보데이터는동일기존폴더를참조한다.


## 2026-10-19 / 신발 제약 다리 IK 시험 / v0.5.3 유지

목적: 개선된 후보 비교의 상체·회전을 유지하면서 옷으로 이동한 다리만 신발 관측에 맞춰 복원할 수 있는지 시험했다. validation/sam2/norma-shoe-ik-v1에 결과를 분리했다. 제품 적용 없음, M2 미통과 유지.

입력: 기존 Norma 후보 선택32~107의76프레임과 별도 SAM2 신발 마스크0~107의108프레임을 재사용했다. 새 모델 추론/다운로드 없음. 첫 프레임 신발 박스는 이전 실험에서 사람이 지정한 것으로 자동 검출 구현이 아니다. SDK camera_head의 points_3d+pred_cam_t 투영 관계를 확인하고 저장된70관절의2D/3D 대응으로 모델 카메라를 복원했다. 최대 잔차0.03245px이며 실제 카메라 교정/실측 깊이를 의미하지 않는다.

방법: 초기0~25프레임 모델의 본 길이 중앙값과 몸통 기준 무릎·발목 위치를 사전값으로 사용했다(정답 라벨 아님). 신발 PCA 장축 내부의 추정 발목 위치로 투영 광선을 만들고, 고정 고관절·허벅지/종아리 길이·무릎 내각10~175도 조건에서 가능한 깊이를 탐색해 two-bone IK를 계산했다. 한 신발만 보이면 다른 다리는 미확인으로 그대로 두었다. 두 마스크가 겹치면 같은 관측으로 합치고, 좌우 대응의 여러 가설을 비교했다. 발 관절은 발목 변화만큼 이동하며 발 회전은 재추정하지 않았다. 고관절·상체·팔·머리·손가락은 원본 후보와 정확히 동일하다.

수치: 신발 불일치18프레임 중15프레임에서 제약을 만족하는 가설을 얻었고, 남은 불일치는 [43, 44, 81]다. 이는 신발 영역 일치도 개선이며 15개 정확한 3D 복원 성공이 아니다. 좌우 대응 비용이 비슷한66/76/77은 모호하다고 표시했다. 숨은 다리는 복원하지 않았다. 영상 comparison.mp4/native3d.mp4 각각76프레임 디코딩 완료.

시각 검토: 전체4개 contact sheet와67/78의3D 비교를 확인했다. 일부 발목은 옷에서 신발 쪽으로 이동하지만58~67 등에서 무릎이 바깥으로 꺾이는 부자연스러운 가설이 보인다. 2D 신발 위치와 본 길이만으로 깊이·무릎 방향·좌우를 확정할 수 없으며 프레임별 최적화로 시간 연속성도 보장되지 않는다. 따라서 **자동 보정 채택 보류**하고 비교 영상만 제공한다. 좋아진 기존 후보 상체·회전은 보존한다. joint-only 데이터이며 MHR body_pose/global_rot를 변환하지 않았으므로 애니메이션 에셋 출력용이 아니다.

다음 작업: 앞뒤 신뢰 가능한 프레임의 무릎 굽힘 방향·다리 좌우 연결을 시간 구간 전체에 제약으로 주고, 다리 영상 증거와 함께 후보를 평가한다. 관측 불충분·도달 불가능 구간은 억지 이동하지 않고 검토 표시한다. 신발 관측18→3만으로 채택하지 않는다. 검증 후에만 GUI 연결과 회전 파라미터 변환을 검토한다.

검증: 신규 기하 시험8PASS, 관련 기존21PASS 합계29PASS. 카메라 복원/퇴화·비유한 입력 거부, IK 본 길이/투영/무릎각/입력 불변, 도달불가 거부, 몸통 좌표계, 마스크 내부 앵커를 검사했다. 원본/기준 raw SHA 불변, 제품 주요 소스 v0.5.3 MVP와 동일 확인. 제품 전체293PASS+권한1SKIP는 이전 기록이며 이번 재실행 수가 아니다. MD4개 원본 업데이트 및case32 SHA동일 복사, 검증3차 증거ZIP 별도 저장. 제품 버전/기존 MVP/HOME ZIP 변경 없음.


## 2026-10-19 / 다리 시간 연속성·좌우 연결 비교 / v0.5.3 유지

사용자 요청에 따라 직전 신발 IK 실험을 확장했다. validation/sam2/norma-shoe-ik-temporal-v1은 원본 Norma32~107의76프레임 후보와 기존108프레임 신발 마스크를 재사용한다. 새 모델 추론/다운로드 없음. 기존 v1 결과는 보존했다. 제품/GUI 적용 없음, M2 미통과 유지.

구현: 발목이 신발 영역12px 안에 있고 반대 발목은 같은 영역에서30px보다 멀며, 본 길이가 초기 모델 중앙값의20% 이내인 프레임을 참조 후보로 삼았다. 실제 정답/수동 관절 라벨은 아니므로 trusted라는 내부 변수명은 정확도 보장이 아니다. 어깨·고관절로 만든 몸통 좌표계에서 같은 이름의 다리 무릎·발목을 앞뒤 참조 사이 선형 보간하며, 간격16프레임 초과/양쪽 참조 없는 구간은 미확인으로 남겼다. 이 참조를 신발 투영 광선과 정확한 two-bone IK의 깊이·굽힘 사전값으로 사용했다. 상체·고관절·팔·손·머리·회전 결과는 이전 후보 그대로다.

각 프레임에 원본 유지 후보와 가능한 신발/좌우 대응 IK 후보를 만들고, 전체76프레임 dynamic programming으로 경로를 골랐다. 같은 이름의 다리의 몸통 상대 위치 변화와 무릎 굽힘 방향 변화를 비용에 포함했다. 신발 관측 비용과 비교하며 원본으로 돌아갈 수 있다. 이것은 제한된 IK 후보 집합의 경로 선택이며 연속 좌표 전체의 최적화나 좌우 정답 보장이 아니다. 가려진 다른 다리를 새로 만들지 않고 발 관절은 발목 변화만큼 평행 이동한다. MHR 회전 파라미터 변환 없는 joint-only 결과다.

결과: 직전 단일 프레임 IK의15수정/신발불일치3에서 이번13수정/불일치5로 바뀌었다. 남은 불일치 [43, 44, 66, 67, 81]. 특히66/67은 충분한 참조가 없어 억지로 바꾸지 않았다. 검사 대상 원래18개 중13개가 신발 제약과 맞지만 13개 정확 복원이라는 뜻은 아니다. 좌우 후보 비용이 비슷한58/59는 후보 생성 단계 모호성으로 표시하며, 전역 경로의 확률/신뢰도로 해석하지 않는다.

연속성 수치(모델 native 단위, 정답 정확도 아님): 다리 몸통 상대 프레임 이동 평균은 기존후보0.26701/직전IK0.28228/이번0.25427, P95는0.66380/0.74294/0.66272, 최대는1.16107/1.16107/1.09086이다. 2차 차분 평균은0.43274/0.46483/0.40813이다. 실측 속도·가속도가 아닌 위치 변화 대리지표이며 부드러움 자체가 정확성을 보장하지 않는다. metrics.json에 저장했다.

시각 검토: sheet00~03 전체와61/78의native3D를 확인했다. 직전보다 위치 튐 대리지표는 줄었지만58~64/78~80 등의 무릎 방향·깊이가 여전히 부자연스러울 수 있다. 신발과 본 길이, 모델이 만든 앞뒤 참조만으로 옷에 가려진 무릎을 검증할 수 없다. 따라서 **자동 채택 보류**, 비교용으로만 저장한다. 기본 제품 v0.5.3와 기존 MVP는 유지한다.

다음: 같은 신발을 두 ID가 따라가거나 한쪽만 보이는 구간에서 좌우를 확정하지 말고, 신뢰 구간의 무릎/다리 방향을 실제 영상에서 별도 확인하는 입력이 필요하다. 독립 무릎 관측(구간별 수동 앵커 포함)과 다리 후보를 결합한 뒤 시간 구간 최적화를 재검증한다. 현재 후보가 모두 틀린 구간을 smoothing만으로 정상화했다고 선언하지 않는다. 이후 GUI와 애니메이션 회전값 연결은 검증 후 진행한다.

검증: 신규7+기존29=관련36PASS. 참조 양끝 보간/긴 공백 미확인/이름별 다리 점프 억제/관측 비용 우선/세계 rigid변환 불변/잘못된 입력을 시험했다. 두 영상 각각76프레임 전체 디코딩, 고정 관절2D/3D 정확 일치, 수정 다리 본 길이, 원본·기준 raw SHA 불변, 제품 주요 소스 MVP 일치 확인. 기존 제품 전체293PASS+권한1SKIP는 과거 기록이다. MD4개 업데이트/case33 SHA복사, 검증4차 증거ZIP 저장. 이전 모델·영상·출력·MVP·HOME ZIP 보존.


## 2026-10-19 / 수동 무릎 앵커 편집·계산 추가 / v0.5.3 유지

사용자 요청으로 검증용 무릎 앵커 편집창을 추가했다. 루트 KneeAnchor.cmd를 더블클릭하면 열린다. 일반 GUI의 기존 관절 지정(2D)과 별개이며, 현재 개선 중인 Norma 후보/신발 검증 데이터32~107프레임 전용이다. 임의 영상 전체 지원이나 기본 SAM3D 앱 연결을 완료했다고 해석하지 않는다. 제품 추론 경로와 버전 v0.5.3 유지, M2 미통과.

사용: 프레임 번호 또는 좌우 화살표로 이동 → 캐릭터 본인 기준 왼쪽 무릎11/오른쪽 무릎12 선택 → 원본 영상에서 보이는 무릎 클릭 → 필요시 현재 무릎 삭제 → 앵커 저장 또는 저장 후 비교 계산. 목록 선택으로 지정 프레임 이동, 기존 앵커 불러오기/재실행시 자동 로드 지원. 숨은 무릎을 정답처럼 추측 지정하지 않는다. 프레임 번호는0부터이며32~107만 지원한다. UI가720x1280원본을360x640으로 표시하고 클릭을원본픽셀로 환산한다. 표시된 프레임 번호에 저장해 편집 중 숫자 입력과 화면 불일치를 방지했다.

저장: validation/sam2/manual-knee-anchors.json은 원본 SHA256/schema/프레임/관절/원본2D좌표를 기록한다. 다른 원본·잘못된 프레임/관절·비유한/화면밖 좌표·중복 관절을 거부한다. 계산마다시간이름의입력복사본을만들어계산중편집이반영되지않도록했다. 계산은별도CPU자식프로세스로실행하고로그를저장한다. 결과는새 norma-knee-anchor-날짜_시간 폴더에 저장해 원본/직전결과를 보존한다. 창을 닫아도 이미 시작한 자식 계산은 끝날 수 있다.

알고리즘: 명시된 무릎2D지정점으로 IK무릎둘레48방향/가능발목깊이를탐색해 무릎재투영오차를비용에추가한다. 신발투영·본길이·고관절고정 조건을 유지한다. 무릎오차20px초과인수정가설은거부한다. 명시앵커가있으면이전참조가없어도초기모델사전값과함께시험하되,신발관측/도달가능해가없으면미해결이다. 같은무릎의두수동앵커사이16프레임이내에서는2D선형보간목표를만들어약한비용으로쓴다. 단일앵커는해당프레임과전체경로연결에영향을주며바깥구간에외삽하지않는다. 전체경로DP에수동/보간목표재투영비용을추가하고원본유지후보도남긴다. 앵커간2D보간은실제관측이아니며회전·가림에서는잘못될수있다.

결과표시: comparison.mp4의수동목표는자홍색십자,보간목표는청록색십자,가설다리는주황색. anchor-report.json은명시앵커별오차와 fitted_hypothesis / baseline_already_near / unresolved_conflict_or_no_feasible_hypothesis를기록한다. 마지막표시는신발·길이·관측부족또는경로선택을포함한미해결범주이며단일원인확정이아니다. UI완료상태에출력경로와미해결개수를표시한다.20px이내는제약수용일뿐실제3D정답보장이아니다.

검증: 신규10+기존36=관련46PASS. 원본바인딩/잘못된입력5종/중복/직접vs보간출처/긴공백/무릎지정에따른굽힘변화와정확한본길이를시험했다. Tk창을숨긴상태로초기화하고58프레임이미지를그리는초기화검사완료(사용자클릭전체UI자동화검증은아님). 합성입력으로76프레임파이프라인실행: 이전모델가설에서가져온58프레임무릎12목표는0.229px잔차가설,59프레임반대무릎을화면좌상단10,10에둔불가능목표는미해결보고를확인했다. 해당출력은 SMOKE_ONLY.json으로 표시했다. 사람이표시한무릎정답이나실제Norma개선검증이아니다.초기smoke의기대분기검사를한차례수정했다:변경되지않은무릎목표는baseline_already_near가정상이므로실제로수정된다리의무릎으로기능검사용목표를바꾸었다. 이전smoke출력도보존.

상체고정관절2D/3D정확일치,두영상각76프레임전체디코딩,원본SHA불변,제품주요소스MVP동일확인. 신규무릎목표API선택인자는미지정시이전기하경로를유지한다. 제품전체293PASS+권한1SKIP는과거검증이며이번재실행이아니다. 원본4MD업데이트/case34SHA동일복사,검증5차도구·증거ZIP저장.기존MVP/HOME ZIP보존.

다음: 사용자가실제원본에서보이는무릎앵커를지정하고비교계산한뒤영상과anchor-report를검토한다.실제앵커는아직제공되지않았으며자동으로정답을만들지않았다.무릎이옷에완전히가려진구간은미확인으로두거나전후가시프레임을지정한다.3D깊이/좌우/발회전오류와정상본회전파라미터변환은남아있다.검증후기본GUI와애니메이션출력통합을검토한다.


## 2026-10-19 / v0.5.4 기본 GUI 무릎·발목 앵커 연결 / M2 진행 중

사용자 요청으로 별도 검증용 앵커 도구에 머물던 기능을 기본 프로그램에 연결했다. StartPrototype.cmd로 재시작하면 v0.5.4다. SAM 결과 열기로 기존 sam3d.json을 선택하거나 새 SAM 추출을 완료한 뒤 무릎·발목 앵커를 누른다. 원본 프레임에서 인물 기준 무릎/발목을 클릭하고 적용 후 닫기를 누르면 CPU 보정 작업을 실행해 기본 창의 무릎 앵커 비교 미리보기로 연다. 독립 Norma32~107 전용 KneeAnchor.cmd와 달리 기본 경로는 완료된 SAM MHR70 전체 프레임을 처리한다. MediaPipe 관절 지정 기능은 기존 경로를 유지한다.

중요한 범위: 기본 추출에는 이전 실험의 신발 객체 마스크가 없으므로 **신발 마스크 관측을 자동 연결한 것은 아니다.** 발목 앵커가 있으면 그2D목표를 사용하고, 없으면 원시 모델 발목 투영을 제약으로 사용한다. 발목이 옷에 붙어 있으면 무릎과 발목을 함께 지정해야 한다. 기본 GUI는 raw SAM 결과를 입력으로 쓰며 검증용 다중 후보 선택 결과를 자동 적용하지 않는다. 이전 후보 비교에서 좋아진 회전이 기본 원시 SAM 자체에 전부 반영됐다는 뜻이 아니다.

구현: app/knee_job.py와core/pose3d/manual_leg_geometry.py,manual_leg_path.py를 추가했다. 제품 경로에서 validation 모듈을 import하지 않는다. 고관절/상체/팔/머리/손가락을 정확히 고정하고 무릎·발목 및 발끝오프셋만 수정한다. 초기26프레임 모델의 본길이 중앙값을 제약으로 쓰고, 모델 카메라 투영을 복원해 무릎둘레48방향/발목가능깊이를 탐색한다. 무릎오차20px초과나도달불가는수정가설에서거부한다. 기존원시후보와수정후보를함께두고몸통상대다리이동·무릎굽힘변화·수동/보간목표오차로구간경로를고른다. 같은다리명 연결은 모델 신원을 따른 것으로 좌우 정답 보장은 아니다.

동일관절의두앵커사이최대16프레임만2D목표보간하며,추적분실/장면전환/tracking_segment경계를넘지않는다. 단일앵커바깥외삽없음. 수동점은자홍색십자,보간점은청록색,수정본은주황색이다. 영상왼쪽원시/오른쪽보정가설을표시한다. 앵커불러오기는기존영상SHA바인딩형식을이용하며무릎·발목외입력은거부하고기존지정값은보존한다.

저장: 원시 sam3d.json과body_pose_params/global_rot는덮어쓰지않는다. 원래결과폴더아래knee_고유ID에 knee-overlay.mp4(원본2D비교),knee3d.mp4(native3D비교),knee-joints.json(joint-only),report.json을별도저장한다. report에원본SHA/지정점/미해결앵커/제약실패사유/프레임수/한계를기록한다. 취소또는실패시report에상태를남기고부분결과는완료로열지않는다. 기본창에서보정계산도기존worker/취소/미리보기경로를사용한다. 앵커재지정은원시값에서새결과를만들어보정누적을피한다.

원본검증: 새SAM추출sam-request.json에source_sha256를추가해이후앵커작업에서내용변경을거부한다. 기존추출은원본경로/프레임/해상도확인을하지만당시SHA가없으므로추출당시영상내용을암호학적으로확인할수없다고report에명시한다. 현재선택파일의SHA를기록하는것을과거원본검증과혼동하지않는다.

테스트: **345PASS + 권한 opt-in 1SKIP**. 비GUI341PASS/1SKIP와실제Tk GUI4개를각별도프로세스에서1PASS씩확인했다. 신규제품시험6개는3프레임합성영상의본보정/원시·상체보존/2종미리보기디코딩,변경원본거부,누락프레임앵커미해결,컷·분실보간차단,취소,GUI버튼→에디터콜백→worker→비교미리보기연결이다. 초기전체단일프로세스실행에서Tk두번째이후init.tcl오류가발생한QA-002현상이재현되어분리실행했다. 기본앱실행실패로확정하거나QA-002를해결했다고기록하지않는다. 새SHA계산으로기존취소단위시험의가짜영상이실재하지않아실패한부분은시험fixture에가짜바이트파일을생성하도록수정했다. app/core compileall PASS.

실제저장데이터연결재생: Norma안정화ROI전체218프레임raw를재사용해제품run_knee_correction을실행했다. 이전가설의무릎·발목을합성입력으로제공하고반대무릎을10,10에두는충돌입력도추가했다. 두비교영상각218프레임전체디코딩/원시SHA불변/불가능앵커미해결보고확인. 이는실제저장파일을통한배관검증이며사람이검수한무릎정답이나실제품질개선평가가아니다. 새GPU추론/모델다운로드없음. 증거validation/sam2/knee-v054/verification.json에출력경로와report를기록했다.

남은한계: 무릎방향/깊이/발회전미검증,본길이사전값도모델추정이다.발목수동입력이없으면잘못된모델발목을기준으로할수있다.신발마스크/다중후보자동선택은기본경로에미연결이다.joint-only결과에서MHR회전파라미터를재계산하지않았으므로애니메이션에셋출력완료가아니다.사용자가가시무릎/발목을지정해전후비교를확인해야한다.M2미통과및기존관절오추정이슈유지.

원본4MD업데이트→case35SHA동일복사, v0.5.4 MVP 별도저장. 이전MVP/검증ZIP/HOME ZIP보존. 거대SAM3D환경·가중치는기존설치재사용으로새MVP에중복하지않는다.


## 2026-10-19 / v0.5.4 사용자 앵커 비교 후 튐 진단

사용자 실제 결과 outputs/Norma_sam3d_20261019_160738_9d557f01/knee_aba52a85를 확인했다. 앵커는0프레임의양쪽무릎/발목뿐이며 수정프레임도0뿐이다. 왼무릎/발목은제약불충족으로미해결,오른다리는수정가설이다.32~107구간은앵커전후좌표완전동일,상체전체최대차0이다. 따라서해당구간튐을이번무릎수정의회귀로확정할수없다.

이전좋아졌다고검토한후보선택경로와기본GUI의원시SAM경로가서로다르다.동일32~107구간에서어깨축90도초과는GUI원시13/후보선택7,몸통상대70관절평균이동은0.37292/0.29575이다.정답정확도수치가아닌연속성대리지표다.현재/직전GUI원시값도거의같은수치를보였다. v0.5.4는앵커연결만완료했고후보선택/신발검증까지연결하지않았음이사용자기대와다른핵심차이다.0프레임단일앵커는현재정책상영상전체교정기준으로전파하지않는다.

다음우선순위: 사용자검토가좋았던다중후보선택경로를기본앱에서별도선택가능하게연결하고그선택결과를앵커보정의입력으로유지한다.원시MHR파라미터와joint-only후보를혼합하지않는다.새모델추론/추적/강한smoothing을추가해회귀원인을가리지않는다.현재진단에서는제품코드/추정값을변경하지않았다.M2미통과유지.직전진단스크립트diagnose_v054_jumps.py와v054-jump-diagnosis/diagnosis.json은보존한다.4MD업데이트및case36복사,MVP추가생성없음.


## 2026-10-19 / 사용자 지정 Norma 두 출력 직접 비교

132855_d05f2eb4와161500_20aae947를직접비교했다. SAM2추적계획frames/매프레임ROI완전동일.32~107어깨축90도초과둘다같은13프레임,70관절몸통상대이동평균0.372919/0.372927로유사하다. 전체218프레임2D관절차평균0.02666px/P950.00870px/최대31.419px(143프레임left-thumb-tip). native좌표최대차0.01초과는143프레임이며최대0.13945다. 원시추정이완전동일하다고단정할수없으나광범위한추적회귀를뒷받침하지는않는다.추적일치가관절정확도보장은아니다. GPU비결정성등구체적차이원인은이자료만으로확정하지않는다.

앵커는새출력knee_0713d40d/report.json에실제로저장되었다.0프레임양무릎만지정했고왼무릎은16.46px잔차수정,오른무릎은61.13px잔차미해결이다.수정프레임0뿐으로나머지영상이원시와같은것은저장손실이아니라현재수동편집적용범위때문이다.현재앵커는초기인물관절을전체추적의정체성기준으로사용하지않으며,미래프레임에외삽하지않는다.저장과보정적용버튼의차이및단일프레임한정적용을GUI에명확히안내할필요가있다.

증거validation/sam2/user-norma-132855-vs-161500/comparison.json,old-vs-new.mp4(218프레임전체디코딩),frame0/66/143이미지. 두원본출력과제품코드는수정하지않았다. 이전좋아졌던다중후보선택결과는여전히기본앱미연결로별도문제다.다음수정은개선후보경로통합과앵커적용범위/미해결명시를우선하며강한평활로원인을덮지않는다.4MD업데이트/case37복사,MVP추가없음.


## 2026-10-19 / v0.5.5 기본 앱 다중 후보 선택 연결 / M2 진행 중

사용자가 좋다고 확인한 검증용 다중 후보 선택을 기본 앱 제품 경로에 연결했다. StartPrototype.cmd로 재시작하면 v0.5.5다. 기존 SAM 결과 열기 후 후보 자동 선택 버튼으로 실행하거나, 새 SAM 추출에서 기본 체크된 SAM 출력 후 후보 선택을 사용한다. 원시 overlay/sam3d.json은 보존하고 완료 후 후보 선택 비교를 자동 표시한다. 체크를 해제하면 기존 단일 원시 추론만 실행한다.

처리: 원래 SAM 추론에 더해 같은 대상의 observed(현재인물bbox여백25%/15%),tight(5%),stable-flip(기존ROI수평반전)의3개 후보를 새로 추론한다. 원시 stable과 합쳐4개다. 반전 후보의2D x/3D x와좌우관절이름을복원한다. 첫26프레임 모델본길이/몸통크기 사전값을 사용하고 길이비용0.4/영상후보중앙합의0.2/몸통상대시간변화0.4/후보전환0.03으로전체연속구간DP선택한다. 추적분실/장면/tracking_segment 경계를넘지않고후보가없으면원시값을유지한다. 원본추적계획/대상ID를새로바꾸지않는다. 후보합의와부드러움은정답/신뢰확률이아니며모두틀린경우옷오추정이남는다.

제품구성: app/candidate_worker.py는설치된SAM CUDA환경/가중치를재사용하며core/pose3d/candidate_geometry.py,candidate_ranking.py와app/candidate_job.py는validation의실험데이터를런타임의존하지않는다. 후보3개추가로GPU시간이늘어난다. 부모GUI는작업을백그라운드에서진행하고취소시자신이띄운자식프로세스트리만종료한다. 새결과는원래출력아래candidates_고유ID에candidates.json/selected-joints.json/ranking.json/candidate-overlay.mp4/report.json/log를별도저장한다. 실패/취소결과는완료후보로불러오지않는다.

앵커연결: 무릎·발목 보정의selection입력에선택결과경로를전달하고sourceSHA/rawSHA/schema/프레임을확인한다. 복사한관절입력만교체하고원시MHR body_pose_params/global_rot와혼합하지않는다. 무릎비교왼쪽도후보선택기준이라고표시한다. 기존결과를다시열면현재원본/rawSHA와맞는완료후보를찾아자동복원한다. 무릎앵커의단일프레임적용정책은그대로이며전체추적초기화기능으로확대하지않는다. 앵커버튼의파일로저장/적용하고계산을구분했다.

검증1: 이전검증의캐시된4후보를제품choose/save_selection에전달했다. Norma32~107의76프레임에서선택이름/3D좌표가이전에사용자가검토했던selected-joints와전부정확일치했다. 이재생은새모델추론이아니다. 앞뒤미검증프레임은원시로남긴별도재생출력을보관했다.

검증2: 사용자최신 outputs/Norma_sam3d_20261019_161500_20aae947의전체218프레임을제품run_candidates로처리했다. 새GPU추론654개(218x3)와원시218개를함께사용했다. 전체218프레임비교영상디코딩과원시SHA불변확인. 실제출력 outputs\Norma_sam3d_20261019_161500_20aae947\candidates_1c9056fa. 후보선택수 {'raw': 0, 'observed': 19, 'stable': 73, 'tight': 82, 'stable-flip': 44}.32~107구간몸통상대70관절평균이동 0.372927→0.295754,어깨축90도초과 13→7다. 지표는정확도보장이아니다. 전체구간DP와새후보ROI를사용하므로이전76프레임독립선택과이번실제전체선택이완전히같다고보장하지않는다. metrics/review이미지와실제비교영상을보관한다. 시각평가는별도검토기록을참고한다.

시험: 비GUI347PASS/권한opt-in1SKIP, 실제Tk GUI6개를별도프로세스로각1PASS, 합계353PASS/1SKIP. 이번추가8개는후보출력raw보존·완전타임라인,선택결과를무릎입력으로사용,잘못된rawSHA거부,후보없음원시유지,분실·장면경계분리,완료된동일원본후보재로드,후보버튼GUI연결,새SAM출력뒤자동선택연결을검사했다. GUI추론시험은모델호출만대체하며GUIworker/미리보기흐름을실제실행했다. 실제GPU218프레임실행은별도검증이다. 기존Tk같은프로세스다중생성QA-002문제는해결했다고하지않는다.

한계/다음: 신발·무릎독립관측자동복원은아직미연결. 선택결과는joint-only이며MHR회전값을변환하지않아애니메이션에셋출력완료가아니다. 기존원시추적/모델의의류오추정을모두해결했다고하지않는다. 사용자확인후다리검사와구간재추정연결을진행한다. M2미통과유지.4MD업데이트/case38동일복사,v0.5.5 MVP저장,이전MVP/HOME ZIP보존.거대SAM3D환경/가중치는공유설치재사용으로중복하지않는다.


## 2026-10-19 / 옷에 붙는 다리 별도 추정1차 / 제품 v0.5.5 유지

사용자 요청으로 다리 별도 추정 시험을 진행했다. 제품의 후보선택 결과를 기준으로 하체입력2종을새로추론하고,독립신발관측으로발목을검사한뒤상체를고정해다리만결합했다. 실행/결과는validation/sam2/norma-leg-estimation-v1에분리하며기본프로그램에자동적용하지않았다. M2미통과유지.

입력: 사용자Norma출력161500_20aae947/candidates_1c9056fa/selected-joints.json을사용했다. 기존신발마스크0~107프레임은첫프레임신발상자를사람이지정한이전SAM2실험자료를재사용했으므로새자동신발검출기능이아니다. 두신발ID중복은IoU0.4초과시합치고좌우신원은확정하지않는다. 원본32~107중문제18프레임과비교8프레임의총26프레임을선택했다. 전체원본/4개영상검증이아니다.

새GPU추론52개: body-shoe입력은어깨·고관절·관측신발영역의가로범위와기존인물박스머리위치를포함한다. leg-focus는고관절~신발범위를중심으로위35%/가로25%여백을준다. 두입력에서SAM3D전체모델을실행해관절후보를얻었다. 별도로학습된하체전용모델이아니므로잘린상체를추측하거나좌우를틀릴수있다. 새관절의무릎좌표도모델가설이며독립정답관측이아니다.

결합: 기존신발불일치프레임에만대체다리를시도했다. 대체모델발목자체가신발영역25px이내인경우에만수정후보로삼았다. 모델무릎2D와신발내추정발목위치를목표로,기존고관절/상체고정및초기26프레임모델본길이중앙값을제약으로광선깊이·무릎둘레IK를탐색했다. 무릎투영20px초과/신발까지도달불가인경우거부했다. 관측신발이하나면한쪽다리만시도하고다른다리는그대로미확인으로둔다. 두마스크는좌우대응가설을비교한다. 후보전체구간DP는몸통상대다리변화/굽힘과신발합의를고려하고원본유지후보도포함한다. 발끝은발목오프셋만이동하며발회전은재추정하지않았다.

수치: 10개의기하조건수용가설중4프레임59/67/78/87이선택됐고,32~107의신발불일치는18→14다. 실제다리정답4개복원성공이아니다. 나머지프레임은원래후보를보존했고,신규모델추론을하지않은프레임도포함되므로76프레임전체하체재추론완료라고하지않는다. 다리몸통상대이동지표 {'baseline': {'body_local_leg_step_mean_native': 0.26702049895808555, 'p95_native': 0.6637995252666962}, 'leg_hypotheses': {'body_local_leg_step_mean_native': 0.2703748068373389, 'p95_native': 0.6793722609787184}} 는native단위대리지표이며속도/정확도정답이아니다.

새로확인한원인:44프레임leg-focus이미지에서는옷에서보이는다리쪽으로모델발목이이동했지만,기존고관절3D위치와초기본길이를고정하면신발광선까지도달할수없어결합이거부됐다. 따라서무릎후보가좋아져도기존골반/카메라·깊이/본길이사전값의조합이잘못되면다리만고치는접근으로복원이불가능하다. 이조건불충족이곧골반만이정답오류원인이라는증명은아니며,측정깊이·관절라벨이없어어느사전값이틀렸는지는추가검증이필요하다. 실패는대체발목신발밖57가설/고정고관절·길이에서도달불가5가설이었다. 이는가설수이며서로다른오류프레임수와다르다.

시각검토: 하체집중후보가44/67/78의발목을실제다리쪽으로옮기는경우를확인했다. 전체상체후보는오히려틀릴수있어서상체는절대교체하지않았다. 최종4수정도숨은다리/좌우/무릎깊이오류가남으며각각고립프레임이라진입·복귀시튐우려가있다. 따라서자동채택보류. analysis초판은변경되지않은다리도주황색으로그리는표시오류가있어보존한채analysis-v2에서실제로변경된관절에만주황색을표시하고실패사유도구분했다. 최신비교는analysis-v2/comparison.mp4다.

검증: 신규4PASS+관련기하/시간19PASS(19는신규4+기하8+시간7). 관측없음미확인/대체발목신발밖거부/상체및미관측다리보존·정확한본길이/도달불가시본길이강제늘림금지를시험했다. 원본SHA확인/상체2D·3D전프레임정확일치/제품주요소스v0.5.5MVP동일/비교영상76프레임전체디코딩완료. 제품353PASS/권한1SKIP는직전기록이며이번전체재실행수가아니다.

다음: 어깨·팔은보존하되고관절/골반위치도독립후보로검토하는범위를비교한다. 2D하체후보와신발관측이맞는구간을연속창으로확장해골반·깊이·본길이사전값의충돌을진단하고시간축연결을평가한다. 길이제약을무조건풀어신발에맞추거나4개수정을정답으로기본앱에넣지않는다. 신발만으로숨은무릎과좌우를확정하지않는다. 이후성공조건을확인한범위에서만제품에연결한다.

원본4MD업데이트/case39SHA동일복사/v0.5.5검증1차증거ZIP저장. 기존제품MVP/원시출력/과거실험/HOME ZIP보존. 새모델다운로드없음.최신trial스크립트run_leg_candidates.py,leg_candidate_worker.py,leg_estimation.py,analyze_leg_candidates.py.


## 2026-10-19 / v0.5.6 다리 추정 시험 비교 GUI 연결

사용자가 프로그램에서 직접 확인하길 요청해, 방금 만든 Norma 다리 추정 시험 비교를 기본 프로그램 미리보기에 연결했다. **저장된 시험 영상 재생 연결이며 임의 영상의 다리 자동 재추정 실행 기능이 아니다.** 이 범위를 사용자에게 작업 전/후 명확히 안내했다. 알고리즘 자동 채택 보류와 M2 미통과는 유지한다.

사용: StartPrototype.cmd로 재시작 → Norma 원본 영상을 열거나 기존 Norma SAM 결과 열기 → 재생 제어 아래 다리 추정 시험 비교 클릭. 모델 재추론 없이 원본32~107의76프레임 시험 영상을 연다. 왼쪽은v0.5.5후보선택,오른쪽은시험다리가설이며주황색만수정이다. 미리보기시간/seek는76프레임클립기준이고원본구간은상태문구에표시한다. 원본/후보선택/앵커비교는기존미리보기선택목록에서다시볼수있다.

구현: app/leg_trial.py는outputs/leg_trial_*아래완료된precomputed_leg_trial_v1 manifest를찾아현재영상SHA256·프레임범위·비교영상SHA를확인한다. 다른영상/손상영상/불완전자료에는시험을보여주지않는다. 기존완료결과폴더와후보선택기준은바꾸지않고GUI worker에서자료확인후별도미리보기만연다. app/gui.py에버튼/상태/전용미리보기경로를추가하고새원본열기시경로초기화한다. 기본추적·SAM추론·후보선택·무릎보정계산은변경하지않았다.

자료: outputs/leg_trial_norma_v1/comparison.mp4와report.json에직전analysis-v2/comparison.mp4의동일복사본/원본SHA/영상SHA/원본프레임범위/수정내역을보관한다. 원본실험과출력은보존한다. 제품모듈이validation코드를런타임import하지않는다. 이번MVP에이작은시험자료도포함한다. 현재사용자가열어둔출력을재계산한것이아니며과거Norma시험을재생한다는설명을GUI완료상태에표시한다.

검증: 신규4PASS(원본일치탐색/다른원본거부/비교영상변경거부/실제Tk GUI버튼→worker→미리보기재생·현재출력폴더보존). GUI는별도프로세스실행. 실제Norma파일로제품find_leg_trial을실행해SHA일치를확인하고비교영상76프레임전체디코딩했다. 새로운모델추론/다운로드없음. 직전제품353PASS/권한1SKIP와다리실험관련19PASS는과거기록이며이번전체재실행횟수로합치지않는다.

한계: 숨은다리/좌우/무릎깊이/고립수정튐과44프레임고정골반제약문제는미해결이다. 시험결과를애니메이션출력이나기본자세로자동대체하지않는다. 다음은사용자시각확인후골반/고관절까지포함한후보와연속창결합을검토한다.4MD원본갱신/case40SHA복사,v0.5.6 MVP별도저장.이전MVP/실험/HOME ZIP보존.


## 2026-10-19 / v0.5.7 현재 영상 다리 재추정 연결 / M2 진행 중

사용자가Norma시험을시각확인하고재추정을요청해현재영상입력으로새SAM2신발추적과새SAM3D하체후보추론을실행하는제품경로를추가했다. 저장된Norma시험재생버튼은별도로남겼다. StartPrototype.cmd재시작 → SAM결과열기(또는새SAM출력·후보선택완료) → 현재 영상 다리 재추정. 완료하면다리재추정비교를자동재생한다. 초기발이보이고완료된후보선택결과가있는영상에사용한다.

자동초기화: 현재선택결과의첫프레임발목/발끝/종아리일부로신발시작상자를계산한다. 사용자수동앵커저장이나기존Norma상자를재사용하지않는다. 발목화면밖/두발20px미만중첩/불명확하게큰상자는오류로중단한다. 이는학습된신발검출기가아니라모델발추정으로만든씨앗이므로첫추정이틀리면의류를추적할위험이있다. 신발ID정답확인으로표시하지않고shoes/boots-preview.mp4를함께저장한다.

새추적/추론: 앱자식shoe_worker가SAM2사람+신발2객체를현재영상전체에전파한다. object score/연결성분/면적비/마스크안정성검사와중복영역합치기를사용하며이내부검사가실제신발정답보장은아니다. 장면/추적segment가초기와달라지면신발증거를계속신뢰하지않고그구간을기존후보로남긴다. 다음장면자동재초기화는아직없다. 관측구간에서body-shoe/leg-focus입력을동적으로만들어app/leg_candidate_worker.py로현재영상프레임을새SAM3D추론한다.

결합: core/pose3d/shoe_evidence.py,leg_estimation.py와app/leg_reestimate_job.py로제품모듈을분리했다. validation코드런타임의존없음. 기존후보의신발불일치구간에서만대체모델발목도신발25px안에있는가설을검사한다. 고관절/상체고정·초기모델길이사전값·무릎투영20px조건으로다리를결합한다. 한신발관측이면다른다리는미확인으로보존한다. 원본유지후보를포함한연속구간DP로위치·굽힘변화/신발합의를평가하고분실/장면경계를넘지않는다. 기존옷오추정을모두해결하는것은아니고고정골반제약충돌도여전히거부한다.

결과보존: 기존결과폴더아래leg_reestimate_고유ID에shoes(신발요청/기록/마스크/프리뷰),inference(새하체요청/후보/로그),leg-joints.json,leg-overlay.mp4,report.json을저장한다. 현재선택결과/sourceSHA/rawSHA를검증하고입력변경을거부한다. 원시sam3d와후보선택을덮어쓰지않는다. 원본고관절/어깨/팔/머리/손은그대로이며다리/발끝오프셋만수정한다. 원시MHR회전파라미터는결합하지않고joint-only가설로명시한다. 처리실패/취소는report상태로남기며자신의GPU자식만중단한다. 교체가0개면새추론은완료했지만조건을만족하는가설이없어기존자세를유지한다고GUI에표시한다.

GUI: 현재영상다리재추정버튼은SAM출력과후보선택이있을때활성화된다. 신발추적→하체후보추론→결합·저장단계를worker상태로표시하며취소가능하다. SAM결과를다시열면현재source/selection SHA와맞는완료재추정비교를자동복원한다. 후보선택을새로바꾸면이전다리비교를현재결과로표시하지않는다. 저장된Norma다리시험재생은기존버튼으로명확히분리되어있다.

실제실행: 사용자의Norma161500_20aae947/선택candidates_1c9056fa에서전체218프레임을새신발추적했다. 신발이관측된214프레임에하체후보2종총428개를새추론했다. 제품출력 outputs\Norma_sam3d_20261019_161500_20aae947\leg_reestimate_88406cc3. 수정프레임 [59, 87],신발불일치 18→16. 이는관측일치변화이며정확한3D복원정답수가아니다. 신발내부기준통과좌/우213/206은정확도수치가아니다.0/44/67/78/143/217의신발프리뷰에서실제신발영역추적을확인했고교차시동일신발중복도확인했다. 최종수정영상의시각검토는별도manual-review기록을참고한다. 기존원시SHA불변/상체2D·3D정확일치/영상218프레임전체디코딩/다시열기연결검증완료. 실제첫실행은보고서부가필드를추가하기전에시작했으므로selectionSHA/새추론수/디코딩수를종료후원래MVP의입력SHA와대조하여report에보충했다. 추정좌표를사후변경한것은아니다.

검증: **368PASS/권한opt-in1SKIP**. 비GUI360PASS/1SKIP,실제Tk GUI8개별도프로세스각1PASS. 신규7개는자동시작상자/겹침거부/화면밖발거부/관측없음ROI없음/잘못된입력선택거부/선취소/새2GPU단계와전체타임라인·원시보존/GUI실행·비교재생을검사한다(첫상자생성과겹침거부는같은시험). 기존하체가설4시험도제품core모듈을검사하도록변경했다. 합성파이프라인시험은GPU단계만대체하며I/O/결합/영상인코딩을실행한다. 실제모델검증은위Norma전체실행이다. Tk다중생성의기존QA-002해결을의미하지않고분리실행정책유지.

남은문제: 옷오추정/고정골반/가려진다리/좌우/발회전/고립수정진입튀는문제는아직가능하다. 다른영상의정확도를이번Norma실행만으로보장하지않는다. 초기발이잘리지않고보이는첫프레임이필요하다. 현재3D관절가설을MHR회전이나게임애니메이션으로변환완료한것이아니다. M2미통과.4MD업데이트/case41SHA복사/v0.5.7MVP저장.이전MVP·시험·HOME ZIP보존.모델다운로드없음/설치된GPU환경·가중치재사용.


## 2026-10-19 / v0.5.7 사용자 초반·2초 회전 오류 진단

사용자가0초초반과2초대뒤돌기에서망토에다리본이겹친다고시각보고했다. 최신Norma재추정의원본0/6/12/18/24와58/62/66/70/74프레임을원래후보/재추정/신발프리뷰로비교했다. 코드와기록의확인된빈틈: core결합의재추정시도조건이shoe_support.disagrees뿐이다. 초반표본의발목은두신발마스크안에있어error0/불일치false가되므로무릎형태가틀려도교체검사를시작하지않는다. 따라서발목영역일치가다리전체정상판정처럼쓰이는사각지대가있다. 70프레임도두신발error0,74프레임은한신발error12로원본유지다. 실제무릎이정상이라는뜻은아니다.

2초대58~62의body-shoe/leg-focus는대부분대체발목이관측신발밖으로나와거부됐다.66의leg-focus는기하가설1개가있지만전체경로에서선택되지않았고67에서는모든대체발목이관측영역밖으로거부됐다. 최종변경은기존59/87두프레임뿐이다. 즉상당구간은새다리추정이망토문제를고쳤다가다시망친것이아니라,교체실패후기존오추정을그대로남긴것이다. 다만가림구간신발ID중복/부분영역도보여관측마스크자체를실제신발정답으로단정하지않는다.모델후보문제와신발관측오류가능성을구분해야한다.

다음우선수정: 발목검사와무릎/골반검사를분리하고,발목이맞아도대체하체후보의무릎불일치·관절방향/길이이탈을검토한다. 가림·좌우모호·교체실패를정상추적으로취급하지않도록출처/검토표시를남긴다. 무조건제약을풀거나모든모델합의를정답으로쓰지않고,회전전후연속구간의골반/다리가설을검토해야한다. 초기0프레임앵커를전체영상에강제로외삽하거나보정강도를올리는것으로대체하지않는다.

증거validation/sam2/early-turn-v057/{diagnosis.json,user-early-turn-review.jpg,user-early-turn-shoes.jpg}. 진단만진행했고제품코드/추정값은변경하지않았다. 원본4MD업데이트/case42동일복사.제품v0.5.7/MVP유지,M2미통과.새추론·새테스트실행없음.


## 2026-10-19 / v0.5.8 수동·시험 UI 정리 및 SAM 자동 처리

사용자가관절지정등미사용기능을정리하고다리추정을자동으로바꾸길요청했다. 기본GUI에서관절지정/무릎·발목앵커/고정Norma시험재생/수동후보선택/수동다리재추정/후보선택체크박스를제거했다. 별도KneeAnchor.cmd도삭제했다. 수동3D누락보완/다음검토버튼도현재자동결과와입력경로가달라화면에서제거했다. 원시보완이새다리결과를덮어쓴것처럼보이지않도록,구형원시completion을자동으로후속실행하지는않는다. 기존보완엔진·실험·사용자지정파일·출력·과거MVP는보존했다. CLI/과거검증에서사용하는기하·guidance/backend코드를무조건삭제하지않았다.

현재사용: StartPrototype.cmd재시작 → 영상선택또는드롭 → 필요시대상확인 → 출력. 기본모드는SAM3D+SAM2마스크다. SAM추출완료뒤후보선택→현재영상신발추적/하체재추론/다리결합이자동으로이어지고,완료시다리재추정비교를자동표시한다. 원시뼈대/후보비교/원본은미리보기목록으로계속확인가능하다. MediaPipe/2D비교모드는유지하며해당모드에SAM후처리를잘못실행하지않는다. 기존1인옵션은MediaPipe모드에서만사용한다.

기존결과: SAM결과열기로완료된sam3d.json을선택하면현재source/raw/selection과일치하는완료단계를찾는다. 후보와다리결과가이미있으면재추론없이재사용하고,없는단계만자동실행한다. 기존SAM2결과를열때마스크모드도보존한다. 최신유효다리결과가있으면바로비교를연다. GPU추가단계가실행될수있으므로상태·진행률·취소를동일worker흐름으로표시한다.

실패구분: app/automatic_postprocess.py가단계상태·오류·결과경로를automatic-report.json에기록한다. 후보추론실패시다리재추정을실행하지않고기본추출결과를보존한다. 다리초기화실패(예:첫발화면밖)/다리추론실패시완료된후보결과를보존하고GUI에자동후처리일부실패와원인을표시한다. 취소는failed로삼키지않고cancelled로전파하며본인의자식종료정책을유지한다. raw/report와결과폴더들을덮어쓰지않고automatic-report만현재실행상태로갱신한다. 자동처리완료는추정정확도통과가아니다.

삭제범위: app/gui.py의수동편집·개별시험·별도후보/다리버튼메서드와이벤트분기·상태를정리했다. 폐기한UI를호출하는시험9개는제거하고자동흐름시험7개로교체했다. 제거된화면의이력은이전MVP에남아있다. 기존앵커데이터나출력폴더를삭제하지않았다. 공유read/digest/load_context를제공하는app/knee_job.py등은현재추론입력검증에도필요하므로보존한다.

검증: **366PASS/권한opt-in1SKIP**. 비GUI362PASS/1SKIP,실제Tk GUI4개를각별도프로세스로1PASS. 새시험7개는자동후처리순서,완료단계재사용,다리실패시후보보존,후보실패시다리중단,단계사이취소,출력버튼→자동처리→최종비교및수동컨트롤부재,기존SAM열기→자동재개→최종비교다. 기존GUI입력/재생/잘못된입력초기화/취소종료도통과했다. Tk다중생성QA-002해결이아닌분리검증이다. app compileall PASS.

실제Norma자동재개를제품함수로실행해기존후보candidates_1c9056fa와다리leg_reestimate_88406cc3이모두reused로연결되고원시SHA불변임을확인했다. 새GPU추론은불필요하여실행하지않았다. 각GPU단계의실제Norma전체실행은직전v0.5.5/v0.5.7기록이며이번에다시추론한것으로합치지않는다. 증거validation/sam2/automatic-v058/verification.json,현재출력의automatic-report.json.

남은일: 이번은사용흐름자동화이며추정알고리즘을강하게바꾼것이아니다. case42에서확인한발목일치만으로무릎검사를건너뛰는사각지대,초반·2초대회전의망토오추정,골반/가림/좌우문제는남는다. 다음은사용자가제안한전신관절별시간추적·검사와부위별재추정을검토한다. M2미통과유지.4MD원본갱신/case43SHA복사/v0.5.8MVP저장.이전MVP/원시출력/과거실험/HOME ZIP보존.
