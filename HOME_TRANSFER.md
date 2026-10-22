# 최신 MVP5 v0.8.0 · 엔진용 FBX/기준 미리보기1차

사용: StartPrototype.cmd로 재시작 → 기존 결과 선택 → Unreal · Unity FBX 저장. Unreal에는 Motion_Unreal.fbx를 Skeletal Mesh+Animation으로 임포트한다. Unity 파일은 생성·Blender 왕복만 확인했으며 Unity 실제 임포트는 미검증이다.
별도 Unreal5.8.1 테스트 프로젝트: validation/m5-release/MotionPreview/MotionPreview.uproject. 열면 /Game/MotionPreview/Preview에 기준 리그·평면 지면·조명이 있다. Content Browser에서 ReferenceMotion_Anim을 열어 Play로 확인한다. live 영상 동기화/임의 프로젝트 자동 연결/캐릭터 리타깃은 미구현.
한계: FBX에는 관절별/전신 누락의 유효성 flag와 객체 숨김을 신뢰성 있게 전달하지 않는다. 누락 구간은 M4의 부모/rest fallback 또는 hold가 포함될 수 있으며 복원 동작이 아니다. export.json missing_spans/missing_pose_frames 및 원본 animation.json을 함께 확인해야 한다. M5 긴누락 클립 분리·엔진 표시 정책, 전체6영상 엔진 재생 시각확인, Unity 임포트, 엔진 화면 자동열기·영상 동기화는 남았다. 이번 UE 검증은 NullRHI commandlet이므로 화면의 조명/시점/재생 품질은 사용자 확인 대기다. 스킨은 기존 bone proxy이며 제작용 캐릭터가 아니다. M5 전체 완료 선언 없이 첫 체크포인트로 보관한다.

---

# 최신 MVP4 v0.7.9 · 축 비틀림·가림 처리

프로그램 연결: 재시작 → 기존 결과 선택 → Blender 애니메이션 저장. 새 animation-<id>로 출력하며 GPU 재추출 불필요. 축 roll은 Blender 메쉬/본 방향에서 확인한다. 관절점 위치가 같으므로 오른쪽 선 스켈레톤의 외형은 동일할 수 있다. 원시/M3/이전 .blend를 보존했다. root_motion_kind도 실제 보정본의 값을 animation.json에 전달하도록 맞췄다.
한계: 관절 위치만으로 팔뚝 회내/회외·피부 축 비틀림을 직접 관측할 수 없어 부모 기준의 보수적 prior다. 실제 독립적인 팔다리 비틀림을 일부 완화할 수 있으며 사용자 시각확인이 필요하다. 긴 가림 동작 복원은 미해결이고 재등장 자세 차이도 남을 수 있다. 부분 누락의 Blender proxy는 기존 부모/rest fallback을 표시하므로 관측/복원 결과로 해석하면 안 된다. 전신 누락은 숨김 유지. 옷·머리카락에 붙은 유효값 오추정은 이번 정책의 누락으로 간주하지 않으며 후순위3으로 남긴다. 손가락·얼굴/애니메이션FBX·게임엔진 리타깃도 아직 미구현이다.

---

# 최신 MVP4 v0.7.8 · 작은 잔떨림 추가 완화

기존 프로그램 경로에 연결했다. 프로그램 재시작 → 기존 결과 선택 → Blender 애니메이션 저장으로 새 animation-<id> 생성 및 오른쪽3D 보정본 갱신. GPU 재추출 불필요. 원시/M3/이전 .blend와 빠른 후보 추론·영상 루트/접지 경로를 보존했다.
한계: 작은 실제 빠른 손짓도 잔떨림과 비슷하면 일부 완만해질 수 있다. 팔·다리 축 비틀림, 지속적으로 잘못 잡힌 관절·머리카락/옷·긴 가림은 해결하지 않았다. 골격 자세 오류/큰 순간 회전은 잡음으로 단정해 지우지 않으며 다음5에서 별도 검사한다. 거리·깊이·접지는 계속 모델 추정이고 모든 떨림 해결/동작 정확도 개선을 보장하는 수치는 아니다. 사용자 새 보정본 시각확인 대기.

---

# 최신 MVP4 v0.7.7 · 이동·높이 추정

프로그램 경로 연결 완료. 재시작 후 기존 결과 선택 → Blender 애니메이션 저장. 기존 추론을 재사용하며 새 animation-<id>에 저장하고, 오른쪽 3D에도 보정본을 표시한다. 카메라 보조분석에는 원본영상이 필요하지만 GPU 재추출은 필요 없다. 원본이 없으면 접지 보정으로 대체한다. 원시/기존 M3 motion.json·이전 .blend·22본/모델/의존성과 빠른 후보 추론 옵션을 유지했다.
한계: 기준 스켈레톤/모델 크기와 기본 FOV를 사용한 추정이며 실제 인물 키·미터 이동거리·지면을 보정한 측량 결과가 아니다. 깊이는 모델 추정이라 자세·원근·카메라 pitch/3D parallax·움직이는 배경·반사에 오차가 남는다. 배경 특징 부족/가려진 발/프레임 밖 발은 새 근거가 제한된다. 작은 도약·긴 가림·모든 카메라 이동과 실제 월드궤적 복원은 미해결. 사용자 시각확인 대기, 다음은4잔떨림 보정.

---

# 최신 MVP4 v0.7.6 · 웅크림 접지

기존 프로그램 경로 연결 완료. 프로그램 재시작 → 결과목록에서 영상 선택 → Blender 애니메이션 저장. 기존 추출을 재사용하고 새 animation-<id>에 저장하므로 GPU 재추출 불필요. M3 motion.json/원시 결과/기존 .blend를 덮어쓰지 않는다. app.animation_job은 motion의 input_sha256과 정확히 일치하는 원본/후처리 packet만 읽고 프레임·좌표를 검증한다. 근거가 없으면 기존 3D 접지만 사용하며, 사용한 근거의 SHA와 생성후 무결성을 검사한다. M3 규격/22본·모델·의존성·GPU 경로는 그대로다.
한계: 2D 근거도 모델 투영값이며 실제 바닥/접지 라벨·카메라 보정값이 아니다. 평면에서 크게 벗어나는 이동·카메라 이동/줌·작은 도약·가림/오추정에는 한계가 있다. 전 구간 양발을 바닥에 강제 고정하지 않으며 실제 점프높이/월드궤적 복원은 아직 미완료. 사용자 새 .blend 시각확인 대기. 다음 작업2에서 실제 이동·높이 추정의 제한을 다룬다.

---

# 최신 MVP4 v0.7.4 · 저속 보정 강화

사용: 프로그램 재시작→완료된 SAM3D 결과 선택→Blender 애니메이션 저장 다시 실행. 기존 파일은 자동변경하지 않고 새 motion/animation-<id>/에 고유 저장한다. 새 오른쪽3D 보정 미리보기도 갱신. 확인파일 validation/m4-smooth/LongSword-example/animation.blend. 원시/M3 motion·22본·모델·이전 .blend/MVP 보존, GPU추론·의존성 추가 없음.
한계: 더 강한 저속필터는 작은 동작·급변을 더 완만하게 만들 수 있다. 단일프레임 실제 빠른 peak도 고립잡음과 혼동할 수 있다. 정답접지/실제월드이동/지속관절오추정·Norma·긴누락은 미해결. 사용자 전체영상·5분 bake 자원부하·엔진임포트 미검증. 새파일 사용자 시각확인 대기, M5 자동진입 없음.

---

# 최신 MVP4 v0.7.3 · 잔떨림 강화

사용: 프로그램 재시작→SAM3D 결과 선택→Blender 애니메이션 저장을 다시 실행. 새 motion/animation-<id>/에 저장, 오른쪽3D 보정 미리보기에도 표시. 기존 파일은 자동수정하지 않는다. 확인용 파일 validation/m4-jitter/LongSword-example/animation.blend.
남은 한계: 실제 빠른 단발 동작이 고립잡음과 비슷하면 약해질 수 있고 필터로 작은 동작도 감쇠될 수 있다. 원시 지속오추정/Norma 의상·긴누락·정답접지/월드이동·전관절 해부학적 제약은 해결하지 않는다. 전체 사용자 영상/5분 bake 자원부하/엔진임포트는 이번 검증 대상 아님. 연속재생·접지 기반 추정과 누락/컷 보호는 유지, 사용자 v0.7.3 시각확인 대기.

---

# 최신 MVP4 v0.7.2 · 연속 재생 수정

사용: 프로그램 재시작→결과 선택→Blender 애니메이션 저장을 다시 누른다. 이전 .blend는 바뀌지 않는다. 새 결과는 motion/animation-<id>/에 고유 저장되고 오른쪽 보정 미리보기도 갱신. 확인용 최신파일: validation/m4-continuity/LongSword-example/animation.blend.
남은 한계: 추정접지·접지기반 루트이고 영상의 실제 월드이동을 측정하지 않는다. 위치 연속성은 개선했으나 고속 원본/오추정/몸통 회전 급변·개별 누락 fallback은 여전히 튈 수 있다. 긴 누락/컷은 동작을 꾸며 연결하지 않는다. 전환 보정은 작은 시간 지연/발 미끄러짐을 유발할 수 있다. 사용자가 본 영상/구간은 이번에 새로 특정하지 않았고 실제 재검증은 LongSword 및 합성이다. 5분 대용량의 subframe 키4배 bake 속도·메모리 미측정, 엔진임포트 미검증. 사용자 새 결과 확인 대기.

---

# 최신 MVP4 v0.7.1 · 접지/SLERP 보정

사용: 프로그램 재시작→완료된 SAM3D 결과 선택→Blender 애니메이션 저장. 자동 보정 후 새 motion/animation-<id>/animation.blend, animation.json, corrected-motion.json, report.json 생성. 완료 시 오른쪽3D 패널도 보정 위치를 표시하고, 이후 결과 재선택 시 완료report·원본motion SHA·보정JSON SHA가 일치하는 최신 보정만 자동 표시한다. 기존 원시 영상의 선은 다시 렌더하지 않았으므로 오른쪽 보정 패널과 구분한다. Blender 파일을 열어 Space로 지면과 함께 재생. 이전 .blend에는 소급 반영되지 않으며 새로 저장해야 한다.
한계: 평평한 지면과 참조 신체 비율 가정이며 실제 신발 모양·바닥 검출·정답 접지 라벨은 없다. 추정접지가 틀리면 발 끌기/피벗/점프/웅크림을 과도하게 제한할 수 있고 발목 고정 중 발끝 yaw는 변할 수 있다. 루트XY는 접지 제약으로 만든 경로이며 영상과 동일한 전역 이동·카메라 움직임을 복원한 것이 아니다. 공중 이동·실제 골반높이 복원, 전 관절 해부학적 제한, 지속 오추정/Norma 망토 문제는 미해결. SLERP는 떨림을 줄이지만 일부 동작을 감쇠시킬 수 있다. 5분 Blender 속도/메모리 미측정, UE/Unity 임포트·애니메이션FBX·손가락/표정은 미구현/미검증. 사용자 실제 영상 시각확인 대기.

---

# 최신 MVP4 v0.7.0

사용: StartPrototype.cmd 재시작 → 결과목록에서 완료된 SAM3D 결과 선택 → 3D 패널 아래 Blender 애니메이션 저장. 필요하면 먼저 같은 M3 CPU 변환을 수행한다. motion/animation-<고유값>/animation.blend 및 animation.json/report.json 생성. Blender로 .blend를 열어 Space 재생. 새 영상 출력 때 애니메이션 저장은 버튼으로 명시적으로 실행한다.
한계: 제자리 root/참조 골반높이 유지, 실제 전역이동·골반높이·접지/Foot Lock 없음. 손가락/표정 본과 추적 연결, 애니메이션 FBX와 엔진 직접 임포트는 미구현/미검증. 관절점만으로 축 비틀림을 관측할 수 없어 몸 좌우 방향·팔다리 최소회전 운반 기준을 사용한다. 끝 본은 부모 회전을 상속한다. 개별 관절 누락은 JSON null/missing이며 .blend에서는 부모/기준 자세 fallback이라 복원된 동작이 아니다. 대상 전체 누락은 전신 숨김, 구간 경계/누락은 회전 이력 초기화. CONSTANT 샘플 키프레임으로 긴 누락/컷을 보간하지 않는다. 떨림/SLERP 필터는 기본 미적용. 5분18000프레임 Blender 속도·메모리는 미측정, 처리 제한30분. Norma 의상 오추정/M2 후보 첫26프레임 제약/QA-002 잔여는 해결 선언하지 않는다.

---

# 최신 MVP3 v0.6.0

사용자 승인 M3: Blender제작 참조본을 Unreal/Unity 양쪽 임포트 대상으로 제공하고 영상 옆에 동기화된 표준스켈레톤을 표시한다. v0.6.0, 원시MHR70·회전·MVP2결과 보존. 본회전/메쉬모션/Bake/엔진직접임포트는 미구현·미검증으로 구분한다. 새모델/의존성/다운로드/GPU재추론 없음.
assets/skeletons의Blender·두FBX·공통정의와core/motion·GUI패널을함께보존한다. 동작영상은기존outputs를사용하며새GPU환경설치불필요. case64와MVP3요약참조.

---
# 최신 v0.5.24 / 늦은 등장·시작 프레임 선택

기본 SAM3D+SAM2 경로에서 인물이 나중에 등장해도 최초검출/사용자선택 프레임으로 추적을 시작한다. 원본 전체 프레임번호·시간은 유지하고 시작 전에는 ROI/관절/예측을 만들지 않는다. 기존5분/18000프레임 제한·모델·회전·후처리 순서는 유지. M2 IN_PROGRESS. 일괄추출 재시작/실제GPU추론/사용자GUI 종료 없음.
116PASS/1skip. realYOLOX10등장/CPU대역worker20타임라인 확인, 실제GPU모델추론은미검증. 프로그램 재실행→SAM2모드→재생바 이동→대상확인→번호선택→출력. case61 참조.

---
# 최신 v0.5.23 / 최대 5분 입력

사용자 요청으로 입력·추출 지원을 최대5분(300초)/18000프레임으로 확장했다. 1920px 이하 짝수 해상도/2GiB 파일 제한은 유지한다. 5분60fps까지 프레임 한도에 들어가며 더 높은fps는 길이 이내라도 총프레임 한도에 걸릴 수 있다. 모델·대상선택·회전·추론횟수는 유지. Norma 의상가림은 알려진 한계로 보류, M2 IN_PROGRESS.
128PASS/1skip. 합성5분 CPU입출력 확인, 실제긴영상 GPU 전체검증 남음. 배치추출 사용자취소 유지, 사용자GUI 재시작 필요.

---
# 최신 v0.5.22 / 관측검사·native관절가이드

독립RTMPoseimage관측의조건통과점만SAM3D pointprompt재추정.12표본중10후검사통과/2초대다리관측보류. private API full_output=None호환은child어댑터로처리/모델원본유지. 최신4MD/case57 및 guidance-v0522 참조.

---
# 최신 v0.5.21 / 독립RTMPose·MotionBERT비교

공식가중치repoLICENSE(Apache2.0)확인후Lite64MB+최소소스설치,Norma218frame실행. H36M17별도비교/기본SAM3D유지. 최신4MD/case56 및 independent-v0521 참조. XYproxy를이미지정답투영으로해석하지않고shape비교도함께확인.

---
# 최신 v0.5.20 / SAM3D 직접mask조건비교

기존ROI만입력과native mask조건의차이를확인.12표본33새GPU추론,심한망토오류미해결/자동미적용. 최신4MD/case55 및 mask-prompt-v0520 참조. 시간모델은조건검토만하고추가하지않음.

---
# 최신 v0.5.19 / 양방향 시간 후보 비교

긴2.5초보간은영상상실패→0.6초/몸통·영상이동제약으로보류. 왼팔중심15프레임가설/다리핵심오류미해결,자동미적용. 최신4MD/case54 및 temporal-v0519 참조.

---
# 최신 v0.5.18 / 내부 영역 보강·후보 감점 비교

Norma 기존SAM2영역/기존212부위추론 재사용 CPU 비교.7프레임 변경,2초대 심한 공통 오류는 미해결/자동미적용. 최신4MD/case53 및 region-v0518 참조. 다음은 새로운 가림/몸통 자세 후보 생성 근거 개선.

---
# 최신 v0.5.17 / 내부 의상 마스크1단계

Norma45~90프레임/seed60에서 망토·머리카락 별도SAM2 추적. 진단만 추가, 기존 자동관절 처리 유지. 최신4MD/case52와 cloth-v0517 증거 참조. 다음은 부모mask 불일치·가림 보강 후 후보 감점.

---
# 최신 v0.5.16 / 5번 재관측 연결까지

StartPrototype.cmd 재시작 → SAM출력/결과열기 → 재관측 연결 비교. 최신4MD/case51 참조. M2 진행 중, 의류 오추정 미해결.

---
# 최신 버전 v0.5.15

4번 팔·다리 선택 재추정 연결. StartPrototype.cmd 재시작 → SAM출력/결과열기 → 부위 재추정 비교. 다음5번 재관측 연결. 최신4MD/case50 및 v0.5.15 MVP 참조. 이전HOME ZIP 유지.

---
# 최신 버전 v0.5.14

3번 관절별 궤적·검사와 부위별 재추정 요청 연결. StartPrototype.cmd 재시작 → SAM 출력/결과 열기 → 관절 검사. 다음4번 선택적 주변 프레임 부위 재추정. 최신4MD/case49 및 v0.5.14 MVP 참조. 이전HOME ZIP 유지.

---
# 최신 버전 v0.5.13

2번 전신 후보·몸통 기준축 전달 및 프리뷰 연결. StartPrototype.cmd 재시작 → SAM 출력 또는 SAM 결과 열기 → 전신 기준축. 다음3번 관절별 검사. 최신4MD/case48 및 v0.5.13 MVP 참고. 이전HOME ZIP 유지.

---
# 최신 버전 v0.5.12

5단계 중 사람 추적 1차 보강: SAM2 마스크 중심 이동 예측·관측 검사·전환 후 시각 확인. 새 출력에 적용. 관절별 검사는 후속. 최신4MD 및 v0.5.12 MVP 참조.

---
# 최신 버전 v0.5.11

결과 패널 목록·탭·스크롤·선택 색상을 기존 다크 테마로 통일. StartPrototype.cmd 재시작. 최신 MD 및 v0.5.11 MVP 참고.

---
# 최신 버전 v0.5.10

미리보기 오른쪽 상시 결과 패널 추가. 기존 결과 목록 버튼/별도 창 제거. 패널에서 조회·미리보기·삭제·복원. StartPrototype.cmd 재시작. 최신4MD와 case45 및 v0.5.10 MVP 참고.

---
# 최신 버전 v0.5.9

결과 목록·저장 영상 미리보기·프로그램 휴지통 삭제/복원 추가. StartPrototype.cmd 재시작. md/CURRENT_TASK.md 및 snapshots/v0.5.9 MVP 참고. 이전 HOME ZIP은 유지.

---
# 최신 버전 v0.5.8

수동/시험UI정리,SAM출력→후보선택→다리재추정자동연결.기존결과는완료단계재사용.최신md/CURRENT_TASK.md 및snapshots/v0.5.8 MVP참고.이전HOME ZIP갱신없음.

---
# 최신 버전 v0.5.7

현재영상다리새재추정제품연결.자동신발시작영역·새추적·새모델추론실행.최신md/CURRENT_TASK.md 및snapshots/v0.5.7 MVP 참고.이전HOME ZIP갱신없음.

---
# 최신 버전 v0.5.6

Norma 다리 추정 저장 시험을 기본앱에서재생가능.자동재추정아님.최신md/CURRENT_TASK.md 및snapshots/v0.5.6 MVP 참고.이전HOME ZIP은갱신하지않았다.

---
# 최신 버전 v0.5.5

기본앱에 다중후보선택과 무릎보정입력 연결 완료. md/CURRENT_TASK.md와 snapshots/v0.5.5 MVP 참고. 기존 HOME ZIP은갱신하지않았다.

---
# 최신 개발 버전 v0.5.4

기본 GUI에서 기존 SAM 결과 열기와 무릎·발목 앵커 보정 비교를 연결했다. 최신 md/CURRENT_TASK.md 및 snapshots/v0.5.4 MVP 참고. 기존 HOME ZIP은 갱신하지 않았다.

---
# 최신 개발 버전 v0.5.3

관절 시간축 검사·제한적 보간 시험을 추가했다. Norma 실제 자동수정0건으로 회전 오추정은 미해결이다. 최신 md/CURRENT_TASK.md와 snapshots/v0.5.3 MVP를 참고한다. 기존 HOME ZIP은 갱신하지 않았다.

---

# 최신 개발 버전 v0.5.2

SAM2 장면 전환 구간 분리를 추가했다. 최신 md/CURRENT_TASK.md와 snapshots/v0.5.2 MVP를 참고한다. 아래 20261016 HOME ZIP은 갱신하지 않았다.

---

# 최신 개발 버전 v0.5.1

SAM2 입력 ROI 안정화가 추가됐다. 최신 md/CURRENT_TASK.md와 snapshots/v0.5.1 MVP를 참고한다. 아래 20261016 HOME ZIP은 갱신하지 않았다.

---

# 2026-10-19 추가 개발 알림

현재 작업 버전은 v0.5.0이고 SAM 2 마스크 추적 시험 모드가 추가됐다. 최신 md/CURRENT_TASK.md와 models/sam2/README.md를 먼저 읽는다. 아래 이전 안내와 20261016의 HOME ZIP은 v0.4.10 이전 묶음이므로 SAM 2 추가분을 포함하지 않는다. 새 묶음을 만든 것은 아니다. SAM 2 모델/소스/추가 의존성도 함께 준비해야 한다.

---

# 집 PC에서 작업 이어가기

현재 제품 v0.4.10 / M2 진행 중. 다음 작업은 **SAM 2 마스크 추적**이며 아직 구현·설치되지 않았다.

## 먼저 읽기

`md/CURRENT_TASK.md`를 새 작업자에게 먼저 읽힌다. 코드·모델·검증 자료를 함께 압축했으며 이전 대화를 전부 읽을 필요는 없다. BoT-SORT가 아니라 SAM 2로 이어간다.

압축을 풀면 `UnrealMotionCaptureProgram` 폴더가 생긴다. 프로젝트 루트에서 실행한다. 이 묶음은 설치형 EXE가 아니다.

## 들어 있는 것

- 현재 코드, MD 원본·진행상황 보관본, 계획서, 테스트·검증 자료와 기존 outputs.
- YOLOX/RTMPose/MediaPipe/SAM3D 가중치 및 라이선스.
- `.validation/sam3d/source*`의 원본·포팅 코드, 환경 복원용 목록과 CUDA PyTorch 설치 wheel.
- `transfer/input-map.json`에 기존 회귀 영상 4개와 뒤차기 원본의 경로·존재 여부를 기록한다. 묶음 생성 시 다섯 원본 모두 기존 경로에 없어 원본 영상은 포함하지 못했다. 기존 outputs·검증용 비교/샘플 영상은 포함했다.
- `transfer/files-manifest.json`: 묶음의 파일별 크기·SHA256. ZIP 옆 SHA256 파일은 ZIP 전체 해시다.

환경 폴더 `.venv`, SAM GPU/CPU env, 로그인·인증정보, 모델 다운로드 캐시, 예전 MVP ZIP, 불필요한 로그·Python 캐시는 제외했다. SAM 2 가중치는 아직 없다. 모델은 이 사용자 개인 작업 이전용으로 포함했으며 공개 재배포용 묶음이 아니다.

## 데스크톱 환경 복원 (Windows / Python 3.11)

PowerShell을 압축 해제한 프로젝트 루트에서 연다.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m app.gui
```

이후 `StartPrototype.cmd`로 실행할 수 있다. `transfer/desktop-installed.lock`도 기존 설치 목록으로 보관했다. 복원용 pip 패키지를 모두 오프라인으로 묶은 것은 아니므로 설치에는 인터넷/사용 가능한 패키지 저장소가 필요하다. 이 PC에서 새 환경 복원을 실제 시험한 것은 아니다.

## 기존 SAM3D GPU 환경 복원

기존 작업 환경은 Windows x64 / Python 3.11 / torch 2.8.0+cu128 / torchvision 0.23.0+cu128이었다. 집 PC의 NVIDIA GPU·드라이버 호환성은 별도 확인한다. GPU가 없으면 SAM3D GPU 추출은 실행되지 않지만 코드·문서 작업은 가능하다.

```powershell
py -3.11 -m venv .validation\sam3d\env
.\.validation\sam3d\env\Scripts\python.exe -m pip install .validation\sam3d\wheels\torch-2.8.0+cu128-cp311-cp311-win_amd64.whl
.\.validation\sam3d\env\Scripts\python.exe -m pip install torchvision==0.23.0+cu128 --index-url https://download.pytorch.org/whl/cu128 --no-deps
.\.validation\sam3d\env\Scripts\python.exe -m pip install -r .validation\sam3d\gpu-support-requirements.lock
.\.validation\sam3d\env\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

`transfer/sam3d-installed.lock`는 GPU 환경의 전체 패키지 목록이다. 앱은 `.validation/sam3d/source_cuda`를 직접 import하므로 이 폴더를 유지한다. 다른 OS에서는 위 Windows wheel을 사용할 수 없고 해당 OS 환경을 따로 구성해야 한다. 인증정보는 옮기지 않았으므로 추가 gated 모델을 받으려면 본인 계정으로 새 PC에서 로그인한다. 기존 가중치는 들어 있으므로 그대로 다시 다운로드할 필요는 없다.

## 영상·경로

원본 5개는 현재 경로에 없어 포함되지 않았다. 집 PC에서 원본을 별도로 준비해 GUI에서 선택한다. 과거 출력 JSON과 검증 스크립트에는 예전 PC의 절대 경로가 남아 있다. 과거 기록을 덮어쓰지 말고 `transfer/input-map.json`을 참고해 새 비교 스크립트의 입력을 지정한다. 특히 `compare.py`의 기존 `final` 폴더는 이미 있으므로 새 실험 이름/폴더를 사용한다.

## 새 작업 요청 예시

“HOME_TRANSFER.md와 md/CURRENT_TASK.md를 먼저 읽어줘. 집 PC에서 필요한 환경과 영상 경로를 확인하고, v0.4.10을 보존하면서 SAM 2 마스크 추적을 비교용으로 구현·검증해줘. 작업 후 MD와 다음 case도 갱신해줘.”
