# AGENTS.md

## Role

AI Agent는 현재 Task를 안전하고 최소한의 변경으로 완료한다.

목표:

- 빠른 코드 생성이 아니라 검증된 진행
- 기존 기능 보존
- 작은 변경
- 명확한 보고

---

## Read First

작업 시작 시 필요한 문서만 확인한다.

우선순위:

```text
PROJECT.md
HARNESS.md
CURRENT_TASK.md
PROGRESS.md
```

항상 전체 문서를 반복해서 읽지 않는다.

현재 작업에 필요한 부분만 확인한다.

---

## Current Task

작업 전 반드시 확인:

```text
Milestone
Task
Goal
Files in Scope
Acceptance Criteria
Test
```

현재 Task 범위를 벗어난 작업은 하지 않는다.

---

## Work Rule

기본 작업 흐름:

```text
Understand
→ Inspect
→ Minimal Plan
→ Implement
→ Verify
→ Fix
→ Report
```

- 먼저 기존 코드를 확인한다.
- 기존 구현을 재사용한다.
- 불필요한 새 구조를 만들지 않는다.
- 관련 없는 파일을 수정하지 않는다.
- 한 번에 하나의 문제를 해결한다.

---

## ALLOW

다음은 현재 Task 범위 안에서 자율적으로 수행할 수 있다.

- 작은 Bug Fix
- 입력 검증 추가
- Null / Error 처리
- 필요한 Test 추가
- 작은 중복 제거
- 명확한 Naming 개선
- 현재 기능에 필요한 작은 Refactor
- 안전한 Logging 개선
- Build / Test 오류 수정

---

## ASK

다음 변경은 사용자 결정 없이 진행하지 않는다.

- 주요 Architecture 변경
- Milestone 순서 변경
- Motion Skeleton 규격 변경
- 데이터 포맷 변경
- UI Framework 변경
- 핵심 ML Model 교체
- 주요 Dependency 교체
- 저장 구조 변경
- Network 기능 추가
- Cloud 기능 추가
- 기존 Public API 대규모 변경
- 프로젝트 지원 범위 변경

---

## NEVER

다음 행동은 금지한다.

- 테스트 실패를 숨기고 완료 선언
- 사용자 파일 임의 삭제
- 사용자 데이터 외부 업로드
- 로그인 / 계정 시스템 임의 추가
- Cloud 필수 구조 추가
- 비밀키를 Source에 저장
- 사용자 PC 전체 파일 탐색
- 검증 없는 대규모 Rewrite
- 문제 해결을 위해 관련 없는 시스템 수정
- 사용자 승인 없는 파괴적 Git 작업
- 실패 원인을 모른 채 수정 반복

---

## Minimal Change

항상 가장 작은 유효 변경을 우선한다.

좋음:

```text
문제 위치 확인
→ 관련 코드 수정
→ Test
```

피함:

```text
문제 발생
→ Module 전체 Rewrite
→ Architecture 변경
```

기존 구조로 해결할 수 있으면 새 구조를 만들지 않는다.

---

## Verify Before Guess

확인 가능한 것은 추측하지 않는다.

확인 순서:

```text
Existing Code
→ Test
→ Compiler / Runtime Error
→ Installed API
→ Official Documentation
```

특히 다음은 임의로 API를 만들어내지 않는다.

- Unreal Engine
- Python Library
- ML Framework
- FFmpeg
- GPU / CUDA 관련 API

---

## Failure Handling

같은 문제 해결을 반복 실패하면 `HARNESS.md`의 Failure Rule을 따른다.

중단 시 다음만 보고한다.

```text
Problem
Attempts
Observed Result
Likely Cause
Impact
Decision Needed
```

해결되지 않은 상태에서 다른 시스템까지 연쇄 수정하지 않는다.

---

## User Decision

사용자 판단이 필요한 경우 선택지를 짧게 제시한다.

형식:

```text
[결정 필요]

문제:
...

선택:
A. ...
B. ...

권장:
...
```

가능하면 2~3개 선택지만 제시한다.

---

## Code Comments

주석은 다음 경우에만 추가한다.

- 이유가 코드만 보고 명확하지 않을 때
- 수학 / 좌표계 / Retarget 규칙 설명
- 보안상 중요한 처리
- 비정상적인 Engine / Library 제약

코드가 하는 일을 그대로 설명하는 주석은 추가하지 않는다.

---

## Logging

로그는 디버깅에 필요한 정보만 기록한다.

기본 로그:

```text
Stage
Operation
Result
Error Code
Duration
```

다음은 기록하지 않는다.

- API Key
- Token
- Password
- 원본 영상 데이터
- 불필요한 사용자 개인정보

---

## New Files

새 파일 생성 전 기존 파일에 책임을 둘 수 있는지 확인한다.

새 파일은 명확한 책임이 있을 때만 생성한다.

유사한 역할의 파일을 여러 개 만들지 않는다.

---

## Dependencies

현재 Task 해결을 위해 새 Dependency가 필수인지 먼저 확인한다.

기존 Dependency로 가능하면 새 Dependency를 추가하지 않는다.

Dependency 변경은 `HARNESS.md` 규칙을 따른다.

---

## Progress Update

Task가 진행되면 `CURRENT_TASK.md`에는 현재 상태만 유지한다.

완료된 Milestone 결과는 `PROGRESS.md`로 이동한다.

M2부터 오류가 발생하면 `ISSUES.md` 한 파일에 증상, 확인된 원인, 조치, 검증 결과를 계속 갱신한다.
CURRENT_TASK.md에는 현재 오류 ID와 상태만 연결하고, 오류별 새 MD를 만들지 않는다.

중복된 긴 작업 기록을 남기지 않는다.

---

## Response Style

답변은 짧게 작성한다.

불필요한 사고 과정, 장황한 설명, 작업 로그 전체를 출력하지 않는다.

### 완료

```text
[M3 완료]

구현
- Motion Skeleton 변환

검증
- Build PASS
- Test PASS
- MVP PASS

다음
- M4 Bone Solver
```

### 미완료

```text
[M3 미완료]

문제
- 좌표 변환 Test 실패

상태
- 수정 3회 실패
- 추가 추측성 수정 중단

추정
- Pose Backend 축 정의 불일치
```

### 진행 중 보고

```text
[M3 진행]

완료
- Joint Mapping

남음
- Coordinate Normalize
```

---

## Completion

다음 조건을 만족할 때만 완료라고 보고한다.

```text
Implementation Complete
Test PASS
Required Review Complete
Regression 확인
Acceptance Criteria 만족
```

하나라도 만족하지 않으면 `완료`라고 쓰지 않는다.

---

## Final Rule

AI Agent의 기본 판단 기준:

```text
필요한 것만 수정
검증 가능한 것만 완료
모르면 확인
실패하면 원인부터 찾기
기존 동작을 우선 보존
```
## 사용자 보관 폴더

- 프로젝트의 진행상황 폴더는 사용자가 작업 이력을 보관하는 공간이다.
- 사용자가 별도로 요청하지 않는 한 읽거나 수정하지 않는다.
- 현재 작업 상태는 md/CURRENT_TASK.md와 md/PROGRESS.md에서 확인한다.
- MVP 스냅샷은 snapshots/<현재버전> MVP/ 폴더에 버전별로 보관한다.

### 작업 기록 복사 규칙 (사용자 요청 2026-10-16)

- 작업 진행 시 원본 md/CURRENT_TASK.md, PROGRESS.md, ISSUES.md, PROJECT.md를 필요한 내용으로 먼저 갱신한다.
- 작업 기록 갱신을 마무리한 뒤 위 4개 MD의 현재 복사본을 진행상황/caseN/에 함께 저장한다. 변경 사항이 없는 파일도 같은 시점의 복사본을 포함한다.
- 기존 case1~case7 이후 이번 보관은 case8부터 시작한다. 이후 실제 존재하는 case 번호의 최댓값에 1을 더해 새 폴더를 만들고, 기존 폴더나 파일을 덮어쓰지 않는다.
- 매 파일 수정마다 새 case를 만들지 않고, 한 작업의 기록 갱신이 끝난 시점에 한 번 보관한다.
- 진행상황은 보관본이며 현재 상태는 항상 md 원본을 기준으로 확인한다. 다음 번호 확인과 복사·무결성 확인은 허용되며, 과거 보관본 내용은 사용자가 요청하지 않는 한 읽거나 수정하지 않는다.
- 보관 후 원본과 복사본의 파일 해시가 일치하는지 확인한다. MD 보관은 기존 MVP 스냅샷 저장과 별도로 수행한다.

