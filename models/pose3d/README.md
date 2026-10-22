# M2 MediaPipe Pose Landmarker Full

기본 모델은 공식 Full float16 v1 task이며 CPU에서 로컬로 실행한다.
코드 및 지정 Full 가중치에 Apache 2.0을 적용한다는 공식 근거를 확인했다.

- SDK: MediaPipe 1.1.1. 설치 wheel에 포함된 LICENSE/NOTICE를 이 폴더에 복사해 보존한다.
- 모델 파일: `pose_landmarker_full.task` (9,398,198 bytes).
- SHA256: `5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1`.
- URL: https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task
- Full 모델 라이선스 개발팀 답변: https://github.com/google-ai-edge/mediapipe/issues/6306 (2026-06-10).
- 사양: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker
- SDK 코드: https://github.com/google-ai-edge/mediapipe

이 모델의 상업적 제작 활용을 위해 비상업 전용 VideoPose3D는 설치하지 않는다.
M2 경로는 M1의 RTMPose/YOLOX 가중치를 로드하지 않으며, 공통 TargetTracker 로직만 재사용한다.
M1 모델의 사용 조건까지 이번 모델 선정으로 검증된 것은 아니다.
배포 시 SDK와 가중치에 적용되는 LICENSE 및 NOTICE 등 고지 조건을 유지한다.
입력 영상·캐릭터·원본 동작의 권리는 별개다.

## 복원

M2 스냅샷에서 가중치와 manifest, LICENSE, NOTICE를 함께 복원한다.
직접 준비한다면 위 정확한 URL에서 이 파일명으로 다운로드하고 SHA256을 대조한다.
코드의 승인 해시와 manifest 및 실제 bytes가 모두 일치해야 실행된다.
프로그램 실행 중 모델 다운로드를 수행하지 않는다.
한국어 경로의 Windows native 로더 문제를 피하기 위해 검증된 로컬 bytes를 SDK에 전달한다.

## 입력과 출력

RGB 전체 프레임 → MediaPipe VIDEO 모드 → 33 image/world landmarks.
전체 프레임 좌표를 유지하므로 움직이는 crop의 역변환이나 스케일 변동을 추가하지 않는다.
v0.3.2부터 동일 Full 모델의 segmentation으로 관절 가시성과 분리된 인물 박스를 만들고 M1 TargetTracker로 지정 인물만 연결한다.
mask는 긴 변 최대 256 크기의 최대 연결 영역으로 분석한다. 비유한/형태 오류/작거나 과도한 영역은 관절 박스로 fallback한다.
중복 영역은 높은 포함 관계·크기 비율 및 이전 관찰 하나에만 공통 대응하는 근거가 있을 때 통합한다. 과거 분리된 두 영역에 모두 대응하면 합치지 않는다.
관절이 매우 가까운 후보도 이전 관찰의 충돌 여부를 확인한다. 겹치는 두 사람의 식별을 보장하는 기술은 아니다.
mask나 평균 관절로 원시 위치를 대체하지 않는다. 선택한 native pose 한 건의 관절·valid를 그대로 보존하며 전체 mask는 파일에 저장하지 않는다.
후보 통합 구간과 박스 출처는 tracking.json의 observation과 report 집계/경고에서 확인한다.
`--list-targets --pose3d`의 번호를 사용한다. M1 검출기의 번호와 같다고 가정하지 않는다.
기본 후보 수는 최대 4명이다. 4명 이상·실제 군중·긴 가림은 초기 지원 범위를 벗어난다.
`--max-people 1`은 입력에 오직 한 명이 있음을 사용자가 명시하는 모드이다.
여러 인물이나 거울 반사가 있는 영상에서 이 모드를 쓰지 않는다.

33관절의 world 좌표는 엉덩이 중점을 원점으로 한 추정 미터 값이다.
전역 이동, 카메라 궤적, 절대 신장을 측정한 결과가 아니다.
image_z_normalized는 미터 값이 아니며 원시 SDK normalized depth를 별도로 보존한다.
원시 좌표·visibility/presence·valid/reason을 보존하고 결측은 null/invalid로 출력한다.
COCO17 대응은 `core/pose3d/interface.py`의 명시적 인덱스 매핑이며 visibility/presence는 RTMPose confidence와 의미가 다르다.
Motion Skeleton, UE 좌표 변환, Root Motion과 보정은 후속 단계이다.

## v0.3.3 짧은 검출 누락 재시도

동일하게 해시 검증한 Full bytes를 IMAGE 모드 보조 추론에 사용합니다. 새 가중치/네트워크/의존성은 없습니다.
이전 대상 박스의 20%/최소32px 여유 crop을 사용하고, 원본 후보가 없으며 장기 분실 전일 때만 재시도합니다.
재검출 후보 최대2개로 모호성을 노출합니다. image x/y와 image_z_normalized는 원본 기준으로 역변환하고 world meters는 그대로 저장합니다.
crop 밖 관절은 원본 안으로 변환돼도 invalid를 유지합니다. 재검출/높은 confidence는 관절 정확도의 보장이 아닙니다.
