# Video-to-Unreal Animation Tool — Development Harness

## 0. 문서 목적

이 문서는 AI Coding Agent가 프로젝트를 장기간 개발할 때 따라야 할 최상위 개발 규칙이다.

AI의 역할은 무작정 많은 코드를 생성하는 것이 아니다.

목표는 다음과 같다.

**작은 범위 구현 → 실행 → 검증 → 수정 → 재검증 → MVP 고정 → 다음 단계 진행**

항상 동작하는 상태를 유지하면서 프로젝트를 점진적으로 확장한다.

---

# 1. Product Goal

일반 RGB 인물 영상을 입력받아 로컬 PC에서 인체 동작을 추정하고, 이를 3D Motion으로 복원한 뒤 사용자가 선택한 Humanoid Skeleton에 적용 가능한 Animation 데이터를 생성한다.

최종적으로:

Video  
→ 2D Pose  
→ 3D Pose  
→ Motion Skeleton  
→ Bone Rotation  
→ Root / Foot / Ground Correction  
→ Target Skeleton Retarget  
→ Unreal Animation Sequence

파이프라인을 완성한다.

---

# 2. 절대 제품 원칙

다음 조건은 기능보다 우선한다.

## 2.1 Desktop Application Only

본 프로그램은 웹 서비스가 아니다.

필수:

- PC에서 실행되는 Desktop Application
- Browser 기반 서비스 금지
- 웹 서버를 필수 구성요소로 사용하지 않는다.
- 프로그램 실행을 위해 인터넷 연결을 요구하지 않는다.
- 로컬 파일을 직접 선택하여 입력한다.
- 결과 역시 사용자의 PC에 저장한다.

로컬 통신이 필요한 경우 `localhost` 내부 프로세스 통신만 허용할 수 있다.

외부 서버는 기본 동작에 포함하지 않는다.

---

# 2.2 Local First

기본 기능은 네트워크 없이 동작해야 한다.

기본적으로 다음 데이터는 외부로 전송하지 않는다.

- 입력 영상
- 추출 프레임
- Skeleton
- Motion 데이터
- 사용자 프로젝트
- 로그
- 파일 경로
- 컴퓨터 정보

AI/VLM 등 외부 서비스를 후속 기능으로 추가할 경우:

1. 기본 OFF
2. 사용자 명시적 실행
3. 전송되는 데이터 사전 표시
4. 최소 데이터만 전송
5. Core 기능과 완전히 분리

원칙을 지킨다.

---

# 2.3 No Account

다음 기능을 구현하지 않는다.

- 회원가입
- 로그인
- 사용자 계정
- 클라우드 계정
- 라이선스 서버 종속
- 계정 기반 프로젝트 저장

사용자 설정은 로컬 설정 파일로 관리한다.

---

# 2.4 Local Storage

프로젝트 데이터와 설정은 사용자의 PC에 저장한다.

예:

```text
UserData/
├─ Settings/
├─ Cache/
├─ Projects/
├─ Logs/
└─ Profiles/
```

가능하면 OS 표준 AppData/UserData 디렉터리를 사용한다.

프로그램 설치 폴더에 사용자 데이터를 무분별하게 저장하지 않는다.

---

# 2.5 Simple UX

사용자가 내부 AI/ML 구조를 몰라도 사용할 수 있어야 한다.

기본 UI에서는 최소한의 옵션만 제공한다.

기본 흐름:

```text
1. 영상 선택
2. 영상 속 캡처 인물 1명 선택
3. Unreal Target Model 선택
4. Quality 선택
5. Analyze
6. Preview
7. Generate Animation
8. 필요 시 생성 후 본 디테일 편집
```

기본 설정:

- Fast
- Balanced
- Quality

고급 파라미터는 `Advanced` 영역으로 분리한다.

---

# 3. Security First

보안은 기능 구현 후 추가하는 작업이 아니다.

모든 단계에서 기본 요구사항으로 취급한다.

## 3.1 Network Policy

기본 프로그램은 outbound network connection을 만들지 않는다.

예외가 필요한 기능은 반드시 별도 모듈로 격리한다.

코드 추가 시 다음을 검사한다.

- HTTP 요청
- WebSocket
- Telemetry
- Analytics
- Crash Upload
- 자동 데이터 업로드
- 원격 로그 수집

사용자 동의 없는 네트워크 전송을 추가하지 않는다.

---

# 3.2 File Security

사용자가 선택한 파일만 읽는다.

입력 파일은 반드시 검증한다.

검사 항목:

- extension
- MIME / signature
- 파일 크기
- 경로 유효성
- 지원 codec
- 비정상 파일
- symbolic link
- path traversal

출력 파일은 허용된 경로에만 생성한다.

사용자 파일을 자동 삭제하지 않는다.

---

# 3.3 Process Security

FFmpeg, Python worker 등 외부 프로세스를 실행할 경우:

- shell string 연결 최소화
- argument array 방식 사용
- 사용자 입력을 command에 직접 삽입 금지
- 실행 파일 경로 검증
- timeout 적용
- exit code 확인
- stdout/stderr 크기 제한

`eval`, 임의 shell execution 등은 사용하지 않는다.

---

# 3.4 Dependency Security

라이브러리는 가능한 한 버전을 고정한다.

예:

```text
requirements.lock
uv.lock
package-lock
```

새 dependency 추가 전에 확인:

1. 정말 필요한가?
2. 기존 dependency로 해결 가능한가?
3. 유지보수 중인가?
4. 라이선스 문제가 없는가?
5. 알려진 보안 문제가 없는가?

불필요한 dependency 추가를 피한다.

---

# 3.5 Logging Security

로그에 다음 정보를 기록하지 않는다.

- 사용자 개인정보
- 전체 개인 파일 경로가 불필요한 경우
- API Key
- Token
- Password
- 영상 내용
- 원본 프레임

필요한 경우 경로 일부를 마스킹한다.

---

# 3.6 Secret Policy

소스 코드에 다음을 직접 작성하지 않는다.

```text
API_KEY
TOKEN
PASSWORD
PRIVATE_KEY
```

외부 API 기능이 추가되더라도 OS Credential Store 또는 환경 변수 등을 사용한다.

---

# 4. Architecture Rule

Core와 UI를 강하게 분리한다.

권장 구조:

```text
App
│
├─ UI Layer
│
├─ Application Layer
│
├─ Motion Core
│   ├─ Video
│   ├─ Pose2D
│   ├─ Pose3D
│   ├─ Motion
│   ├─ Solver
│   └─ Export
│
├─ Unreal Adapter
│
└─ Optional AI
```

원칙:

```text
UI → Application → Core
```

Core가 UI를 참조하면 안 된다.

Core가 Unreal을 직접 참조하지 않도록 가능한 한 분리한다.

---

# 5. Stable Boundary

Python Motion Processor와 Unreal Plugin 사이에는 명확한 데이터 경계를 둔다.

초기 표준:

```text
Motion JSON
```

필요 시:

```text
BVH
```

를 추가한다.

Core 내부 구조를 Unreal API에 직접 종속시키지 않는다.

---

# 6. Development Strategy

개발은 반드시 순차적으로 진행한다.

여러 Milestone을 동시에 구현하지 않는다.

기본 흐름:

```text
M0
↓
검증
↓
M0 MVP
↓
M1
↓
검증
↓
M1 MVP
↓
M2
...
```

현재 단계가 안정적으로 완료되기 전에는 다음 단계 핵심 구현을 시작하지 않는다.

---

# 7. Milestone Rule

각 단계는 반드시 독립적으로 실행 가능한 결과물을 가진다.

## M0

Project Skeleton / CLI

MVP:

```text
영상 선택
→ 파일 검증
→ FPS / 해상도 / 길이 출력
```

## M1

2D Pose

MVP:

```text
Video
→ 초기 대상 지정 / 동일 인물 추적
→ Pose2D
→ Stick Figure Video
```

기본 M1 MVP는 보존하고, M2 진입 전 다음 보완을 작은 Task로 순차 구현한다.

- UI 없는 초기 박스 / 후보 지정 입력을 먼저 제공한다. 클릭·드래그 UI는 M9에서 연결한다.
- 매 프레임 가장 큰 박스로 바꾸지 않고 동일 인물을 연결한다.
- Tracked / Uncertain / Lost를 구분하며 분실·교차 구간에서 다른 사람으로 임의 전환하지 않는다.
- 대상 박스 미검출, 추적 연결 실패와 관절별 저신뢰 / 화면 이탈 / 결측을 구분한다.
- 가림 여부는 자동 추정이며 확정 판정으로 취급하지 않는다.
- 현재 관절 표시가 사라지는 조건과 원시 관측·valid 상태를 구분해 기록한다.
- 빠른 동작은 원본 프레임을 보존하여 검증한다. 처리 지연과 동작 추정 실패를 구분한다.

추적 알고리즘과 상태 저장 방식은 기존 구현 조사 후 정한다. 이 계획 변경으로 Motion JSON 규격을 바꾸지 않는다.

## M2

3D Pose

MVP:

```text
전체 RGB 프레임 + M1 TargetTracker 로직 / MediaPipe 대상 후보
→ MediaPipe Pose Landmarker Full (33 image/world landmarks)
→ 3D Stickman Viewer / 시간축·결측 진단
```

M2 모델은 상업적 제작용 MediaPipe Pose Landmarker Full로 선정한다. 코드·지정 Full 가중치의 Apache 2.0 근거는 PROJECT.md에 기록한다. v0.3.0 preview에서 설치·연결·프리뷰를 구현했으며 사용자 검증과 ISSUES.md의 잔여 한계 확인 후 최종 통과를 판단한다. 동일 인물의 RGB 시퀀스를 사용하고 회전·의상 가림·빠른 동작의 영향을 평가한다. VIDEO 모드 추적을 전후 프레임 Lifter로 표현하지 않는다.
관절 33개, 엉덩이 중점 원점·미터 단위, confidence 의미 차이, 전체 프레임 좌표 유지와 분실 경계 초기화를 검증한다. M2는 RTMPose/YOLOX 가중치를 로드하지 않는다. pose2d.json만으로 재추론할 수 없으며 모델·런타임의 오프라인 실행을 확인한다. M1 가중치의 상업 사용 조건도 별도 검토한다.
선택 모델의 입력 규격과 결측 처리를 확인한다. 대상 전환·긴 분실 구간을 그대로 연결하거나 완전 복원을 보장하지 않는다.

M2 초반 평가 항목:

- 머리카락·헐렁한 의상·장식품에 관절이 붙는 영상을 기준 테스트에 포함한다.
- 대상 추적 성공과 해부학적 관절 위치의 정확도를 구분한다. 높은 confidence도 올바른 위치를 보장하지 않는다.
- 지속 오추정과 순간적인 튐 / 결측을 나누고, 전후 문맥으로 줄어드는 오류와 남는 오류를 기록한다.
- 지속 오추정이 후속 본 변환을 방해하면 2D 모델 또는 인물 crop 개선 필요성을 먼저 판단한다. 새 모델·주요 dependency 교체는 사용자 결정 후 진행한다.

## M3

Motion Skeleton

MVP:

```text
Pose3D
→ Standard Motion Skeleton
→ Motion JSON
```

본 길이와 관절 계층을 일관되게 정의해 구조적 오류를 검사한다. 가려진 실제 관절 위치를 정확히 복구했다고 단정하지 않는다.

## M4

Bone Solver

MVP:

```text
Motion Skeleton
→ Local Bone Quaternion
```

3D 본 길이·관절 계층과 회전 제약을 활용해 비정상적인 자세를 억제한다. 원근·회전에 따른 2D 투영 길이 변화는 정상일 수 있으므로 2D 길이를 무조건 고정하지 않는다.

## M5

UE Preview

MVP:

```text
Motion JSON
→ Unreal
→ Motion Skeleton Playback
```

## M5.5

Target Skeleton Analyzer

MVP:

```text
Target Skeleton
→ hierarchy
→ reference transform
→ visualization
```

## M5.6

Auto Bone Mapping

MVP:

```text
Target Skeleton
→ Human Bone Role
→ Mapping Confidence
```

## M5.7

Retarget Profile

MVP:

```text
Auto Mapping
→ Manual Correction
→ Save
→ Reload
```

## M6

Retarget

MVP:

서로 다른 Humanoid Skeleton 2종 이상에 동일 Motion 적용.

## M7

Animation Bake

MVP:

Animation Sequence 자동 생성.

## M8

Motion Cleanup

MVP:

- Smoothing
- Root Motion
- Foot Contact
- Foot Lock
- Ground Correction

비교 가능.

추가 검증:

- 짧은 관절 결측만 조건부 보간하고, 긴 가림과 대상 추적 분실 경계를 가로질러 보간하지 않는다.
- 대기 자세의 jitter와 빠른 동작의 피크 감쇠 / 시간 지연을 함께 측정한다.
- 위치 평활화와 Quaternion 평활화를 구분하며 원시 결과와 비교한다.
- 머리카락·의상·장식품에 지속적으로 붙은 잘못된 관절 위치는 smoothing만으로 해결하지 않는다. 순간적인 튐 / 짧은 누락 보정과 구분해 평가한다.
- 원근·회전에 따라 달라지는 2D 투영 길이를 무조건 고정하지 않는다. M3/M4의 3D 본 길이·계층·회전 제약과 연결한다.

## M9

Desktop Tool UI

MVP:

```text
Video Select
Capture Person Select / Reselect
Unreal Target Select
Analyze
Preview
Generate
```

한 화면 흐름 완성.

- 영상 클릭·드래그로 캡처 인물을 선택하고 분실 구간에서 재선택한다.
- 추적 분실과 관절 누락 구간을 타임라인에서 구분해 탐색한다.
- 생성 후 Advanced 디테일 작업으로 특정 프레임과 본을 선택해 로컬 회전 및 허용된 위치 채널의 값을 수정한다.
- 키 추가·수정, 주변 구간 보간·연속성 프리뷰, Undo/Redo, 수정본 저장·재열기를 검증한다.
- M7에서 생성한 결과는 보존한다. 본 편집과 Skeleton 역할 매핑 / Retarget Profile 수정을 구분한다.
- Root Motion / Foot Lock / 계층 제약에 미치는 영향을 확인하고, 편집 API와 저장 형식은 이 단계에서 검증·확정한다.
- M1에서 영상 속 팔·다리를 직접 지정하는 편집 UI는 추가하지 않는다.
- 머리카락·의상·장식품 관련 자동 추정 / 구조 보정 이후에도 남은 오류 구간을 프레임별 본 편집 대상으로 표시한다.

## M10

Optional AI Assist

Core 기능과 완전히 분리한다.

## M11

Packaging

일반 PC에서 설치 후 독립 실행 가능 상태.

---

# 8. 작업 단위 제한

Agent는 가능한 한 한 번에 하나의 문제만 해결한다.

좋음:

```text
M1 Pose Backend Interface 구현
```

나쁨:

```text
Pose + UI + Retarget + Packaging 구현
```

큰 작업은 반드시 작은 Task로 분리한다.

---

# 9. Change Budget

한 작업에서 필요 이상으로 많은 파일을 수정하지 않는다.

원칙:

```text
Small Diff
Small Scope
Easy Review
Easy Rollback
```

관련 없는 refactoring을 동시에 하지 않는다.

---

# 10. Agent Development Loop

각 Task는 다음 순서를 따른다.

```text
OBSERVE
↓
PLAN
↓
IMPLEMENT
↓
CHECK 1
↓
FIX
↓
CHECK 2
↓
FIX
↓
CHECK 3
↓
TEST
↓
MVP VERIFY
↓
REPORT
```

---

# 11. Pre-Code Inspection

코드를 수정하기 전에 반드시:

1. 관련 파일 확인
2. 관련 호출 구조 확인
3. 기존 구현 확인
4. 테스트 확인
5. 데이터 흐름 확인
6. 변경 영향 범위 확인

을 수행한다.

바로 코드를 작성하지 않는다.

---

# 12. Three-Pass Code Review

M2 관절 지정 선택 경로(사용자 승인2026-10-15): 원시 pose3d/pose2d를 덮어쓰지 않고 guidance2d.json에 manual/observed/predicted/reacquired/uncertain을 저장한다. 예측≤0.2초, 예측/거부값의 관측 history 갱신 금지, 몸통 분실 시 예측 중단, 재연결 연속2회, 다른 영상 지정 파일 거부, 취소/실패 sidecar 종료를 검증한다. 모델 confidence와 정확도는 계속 분리한다.

코드 작성 후 바로 완료 처리하지 않는다.

최소 2회, 권장 3회 자체 검토한다.

## PASS 1 — Correctness

확인:

- compile error
- syntax
- type
- null
- lifetime
- exception
- API usage
- boundary condition

---

## PASS 2 — Architecture

확인:

- 책임 분리
- 중복
- 강한 결합
- 불필요한 dependency
- 기존 architecture 침범
- 확장 가능성

---

## PASS 3 — Security & Regression

확인:

- 입력 검증
- path
- subprocess
- network
- resource exhaustion
- destructive operation
- 이전 기능 손상

---

# 13. Verification Gate

Agent는 다음 조건 없이 Task 완료를 선언하지 않는다.

```text
[ ] Build 성공
[ ] 관련 Test 성공
[ ] 기존 Test 실패 없음
[ ] MVP 수동 테스트 성공
[ ] 예상 출력 확인
[ ] 오류 로그 확인
```

가능한 경우 자동화한다.

---

# 14. Regression Principle

새 기능보다 기존 기능 보존을 우선한다.

기준 영상 세트를 유지한다.

예:

```text
A_front_walk
B_side_walk
C_run
D_arm_swing
E_squat
F_occlusion
G_camera_move
H_people_cross_and_reappear
I_rotation_clothing_hair_accessories
J_fast_sword_and_arm_motion
K_idle_stance
```

Solver 또는 Filter를 변경하면 이전 결과와 비교한다.

추적 대상 전환 횟수, 분실·재연결 결과, 관절 누락 길이, 정지 jitter와 빠른 동작 지연을 함께 기록한다.
의상·장식·머리카락 오추정은 사람이 확인한 프레임을 회귀 기준으로 사용한다. Confidence 평균은 정확도 백분율이 아니다.

---

# 15. Measurable Development

가능한 기능에는 숫자로 비교 가능한 지표를 만든다.

예:

- Pose Confidence
- Bone Length Variation
- Joint Jitter
- Foot Sliding Distance
- Ground Penetration Count
- Root Velocity Spike
- Mapping Confidence

Agent는 느낌으로 개선 여부를 판단하지 않는다.

---

# 16. Keep / Revert Loop

실험성 변경에는 다음 규칙을 사용한다.

```text
Baseline
↓
One Change
↓
Test
↓
Measure
```

개선:

```text
KEEP
```

악화:

```text
REVERT
```

판단 불가능:

```text
INVESTIGATE
```

여러 실험을 한 번에 섞지 않는다.

---

# 17. Git Rule

각 Milestone MVP는 반드시 복구 가능한 상태로 만든다.

예:

```text
m1-pose2d-mvp
m2-pose3d-mvp
m3-motion-skeleton-mvp
```

큰 변경 전에는 restore point를 확보한다.

Agent는 사용자의 승인 없이:

```text
git reset --hard
git clean -fd
force push
branch delete
```

등의 파괴적인 명령을 사용하지 않는다.

---

# 18. UI Principle

2026-10-15 사용자 승인에 따른 임시 v0.3.1 Desktop prototype은 M2 품질 개선 전에 제공한다.
Tkinter + tkinterdnd2 파일 드롭, 출력, 진행률/취소, 로컬 결과 재생으로 범위를 제한한다.
기존 처리 함수를 worker thread에서 호출하고 Tk widget은 main thread에서만 갱신한다.
종료 시 처리 worker에 취소를 전달해 부분 결과 상태와 backend.close를 보장한다.
M9 전체 작업 흐름과 본 편집, 패키징 완료로 간주하지 않는다.

UI 목표:

**사용자가 무엇을 해야 하는지 고민하지 않는 것**

기본 화면에서 보여줄 것:

```text
Input Video
Target Model
Quality
Analyze
Preview
Generate
```

상태:

```text
Ready
Analyzing
Processing
Completed
Warning
Failed
```

오류 메시지는 기술 스택 트레이스를 그대로 보여주지 않는다.

예:

나쁨:

```text
RuntimeError CUDA...
```

좋음:

```text
GPU 메모리가 부족합니다.
Fast 모드로 다시 시도해보세요.

[Fast로 재시도]
[자세히 보기]
```

---

# 19. Failure Handling

M2부터 오류 분석과 해결 결과는 `ISSUES.md` 한 파일에 유지한다.
증상 / 재현 / 확인된 원인 / 미확정 가설 / 조치 / 검증 / 남은 한계를 구분해 갱신하고, CURRENT_TASK.md에서 해당 ID를 참조한다.
완료된 Milestone 요약은 PROGRESS.md에 유지하며 상세 오류 내용을 중복 기록하지 않는다.

한 단계 실패가 전체 프로그램 종료로 이어지지 않도록 한다.

가능하면:

```text
Detect
→ Explain
→ Recover
→ Retry
```

구조를 사용한다.

---

# 20. Performance Rule

성능 최적화는 측정 후 한다.

추측으로 최적화하지 않는다.

프로파일:

```text
Fast
Balanced
Quality
```

각 모드는 처리시간과 품질을 측정 가능해야 한다.

---

# 21. Resource Safety

영상 처리와 AI inference는 무거운 작업이므로 다음을 고려한다.

- RAM 제한
- VRAM 부족
- 긴 영상
- 지나치게 높은 해상도
- Worker timeout
- Cancel
- Progress
- Cache 제한

사용자가 언제든 작업을 취소할 수 있어야 한다.

---

# 22. AI Usage Policy

외부 AI는 Core dependency가 아니다.

Core:

```text
0 Token
```

Optional AI:

```text
사용자 요청
→ 요약 데이터 생성
→ 전송 대상 표시
→ 사용자 실행
```

AI 서비스 장애가 Motion 변환 기능을 막으면 안 된다.

---

# 23. Documentation Rule

각 Milestone 종료 시 최소한 다음을 기록한다.

```text
Goal
Implemented
Changed Files
Test
Known Issues
Next Step
```

긴 개발 일기를 작성하지 않는다.

---

# 24. Agent Output Rule

AI 답변은 짧게 유지한다.

기본 형식:

```text
[현재 단계]
M3 Motion Skeleton

[작업]
Joint 표준 구조 구현

[검증]
- Build OK
- Unit Test OK
- Sample A OK

[수정]
2차 검토에서 axis 변환 오류 수정

[결과]
M3 MVP 완료

[다음]
Bone Solver
```

불필요한 장문 설명을 하지 않는다.

---

# 25. Stop Conditions

다음 상황에서는 억지로 진행하지 않는다.

- 요구사항 충돌
- 데이터 손상 가능성
- 사용자 파일 삭제 가능성
- 보안 위험
- 기존 구조 대규모 변경 필요
- 핵심 architecture 변경 필요
- 검증 없이 다음 단계로 넘어가야 하는 상황

이 경우 현재 상태를 보존하고 문제를 보고한다.

---

# 26. Definition of Done

Task 완료:

```text
Implementation
+
Review × 2~3
+
Build
+
Test
+
Regression
```

Milestone 완료:

```text
All Tasks Done
+
MVP 실행 가능
+
Regression Pass
+
Known Issues 기록
+
Restore Point
```

Project MVP 완료:

사용자가 Desktop App에서

```text
Video
→ Analyze
→ Target Skeleton
→ Preview
→ Generate Animation
```

을 로그인이나 외부 서버 없이 완료할 수 있다.

---

# 27. Core Philosophy

Agent는 코드를 많이 작성하는 것이 목표가 아니다.

목표는 매 단계마다:

**동작하고, 검증되고, 복구 가능한 소프트웨어를 남기는 것**

이다.

항상:

```text
Understand
→ Small Change
→ Run
→ Measure
→ Review
→ Fix
→ Verify
→ Preserve
```

순서를 따른다.
