# MVP3 Motion JSON v1

본 문서는 새 `standard_motion_positions_v1` 경계를 정의한다. 기존 `sam3d_mhr70` 원시 파일, MHR native 회전과 MVP2 후처리 파일은 변경하지 않는다.

## 참조 스켈레톤

`assets/skeletons/humanoid_v1.json`을 기준으로 한다. `MotionHumanoid22`의 부모가 먼저 나오는 22본 계층과 T-pose head/tail, Unity 역할을 보존한다. Blender 원본과 두 엔진용 정지 FBX는 같은 정의로 제작했다.

## Motion 파일

결과 폴더 아래 `motion/motion.json`, 변환 상태·입력 해시는 `motion/report.json`에 저장한다.

| 필드 | 의미 |
|---|---|
| `schema` | `standard_motion_positions_v1` |
| `skeleton` | 기준 본 이름·부모·head/tail·인체 역할 |
| `video` | 원래 nominal fps·해상도 등 메타데이터 |
| `units` | 미터 단위의 고정 참조 체형. 실제 인물 신장 측정 아님 |
| `source_to_standard_matrix` | 카메라 `(x,y,z)` → Blender 기준 `(x,z,-y)` |
| `source_kind` | 재관측 연결 / 부위 추정 / 선택 후보 / 원시 SAM3D 중 실제 입력 |
| `root_motion` | 현재 `false`. 전역 이동 복원 없음 |
| `bone_rotations` | 현재 `null`. 로컬 본 회전은 M4 대상 |
| `source_sha256`, `raw_sha256`, `input_sha256`, `definition_sha256` | 원본 영상·원시·선택 입력·참조 정의의 무결성 |

## 프레임

- `frame_index`, `timestamp`: 원본의 전체 인덱스와 nominal fps 시간. 앞부분을 잘라내지 않는다.
- `tracking_state`, `tracking_segment`, `scene_index`: 원본 상태·경계를 유지한다.
- `positions`: 본 정의 순서의 22개 관절 위치. 부모 방향을 유지하며 참조 계층의 길이로 정규화한다.
- `mapped_positions`: 모델 관절에서 파생한 위치를 골반 상대·Blender 축으로 옮긴 비교용 데이터다. 정규화된 위치와 구분한다.
- `source_pelvis_camera_m`: 원래 카메라 상대 골반 위치를 보존한다. 이를 UE/Unity 월드 Root Motion으로 쓰지 않는다.
- `joint_status`: 모델 추정, 파생 기준, 가상 root, 누락·부모 누락·퇴화 방향 등을 구분한다.
- `source_changes`: 입력 부위 교체/재연결의 출처 기록을 유지한다.

대상 없는 프레임에는 관절을 생성하지 않는다. 개별 원본 관절이 비유한 값이거나 부모 연결이 없으면 해당 관절·자식 연결을 비운다. 긴 결측·장면 경계를 가로질러 보간하지 않는다.

## 이번 변환의 경계

Root는 제자리 기준이고 골반은 참조 높이에 고정한다. 이 미리보기의 지면선은 접지 정답이 아니다. 실제 골반 상하 이동·Root Motion·Foot Lock은 복원하지 않았다.

척추, 쇄골 연결점, 머리 중심과 발끝은 MHR70에서 직접 측정된 Blender 본이 아니라 관절의 중간점·파생값을 포함한다. 일정한 길이는 참조 리그에 맞춘 구조 조건이며, 잘못된 방향이나 의상에 붙은 관절의 정답 복원을 뜻하지 않는다.

현재 변환기는 기본 SAM3D MHR70 입력을 지원한다. MediaPipe33 또는 다른 표준 관절 순서를 자동으로 혼용하지 않는다.

## 미리보기

영상 패널 옆의 `표준 스켈레톤 · 3D`가 같은 프레임 번호를 재생한다. 드래그로 회전, 휠로 확대, 정면/측면으로 확인한다. 원본 타임라인과 길이가 다른 표본·구간 비교 영상은 잘못 동기화하지 않고 표시를 보류한다.

기존 결과는 모델 재추론 없이 패널의 `변환`으로 만들 수 있다. 기본 입력은 완료된 재관측 연결→부위 추정→선택 후보→원시 순서이며, 현재 결과에 존재하는 단계만 사용하고 파일 출처 해시를 검사한다. 새 추출과 `SAM 결과 열기`에서는 자동으로 변환한다.

본 회전과 스킨 메쉬 재생, 엔진에서의 리타게팅·애니메이션 Bake는 다음 단계다.


## MVP4 추가 경계 (v0.7.0)

위 MVP3 위치 스키마는 그대로 유지하며 bone_rotations=null도 변경하지 않는다. 별도 motion/animation-<id>/animation.json의 schema는 standard_bone_animation_v1. skeleton은 변경 없는22본 정의, bone_names는 같은 순서, fps는 원본 nominal fps, Blender 프레임은 frame_index+1. 각 프레임은 timestamp/segment/scene과 local_quaternions_wxyz, local_locations_m, bone_status를 포함한다. 회전은 Blender PoseBone.matrix_basis 기준 부모/rest 상대 단위 Quaternion(wxyz), 위치는 같은 basis의 미터 단위 위치. M3의 분리된 attachment 위치 보존을 위해 로컬 위치 채널이 포함되므로 회전만 재생하면 완전히 같은 head가 되지 않을 수 있다. JSON의 누락 quaternion/location은 null, .blend는 부모/rest fallback을 쓰므로 그 부분의 정확한 복원으로 보지 않는다. 전체 미검출은 mesh/armature 숨김 키로 구분. 유효구간 q/-q 부호연속·경계 초기화, CONSTANT 샘플 키프레임, SLERP 시간 필터 미적용. source/raw provenance는 기존 motion 파일 및 새 report의 motion/solver/rig SHA로 연결. report.status=completed와 해당 .blend/.json이 있어야 성공. 실패 로그/부분 파일은 완료 결과가 아니다. 해당 Blender22본 rest 규격용 로컬 회전이며 엔진별 회전/FBX 리타게팅 규격으로 동일시하지 않는다.


## v0.7.1 파생 보정 Motion

원본파일은 수정하지 않는다. 새 animation-<id>/corrected-motion.json은 기존 positions 스키마와22본 정의를 사용하며 root_motion=true, root_motion_kind=contact_constraint_estimate와 correction 메타데이터를 추가한다. correction.frames[i].feet는 좌/우 순서로 inferred_contact/swing/ground_collision/미해결·누락 상태, root_offset_m은 골반까지 적용한 추정오프셋(그 Z는 골반 높이 보정; 가상root 자체Z는0)을 기록한다. 원본 회전은 참조head방향 swing Quaternion→적응형 최단SLERP→고정길이 재구성→접지/충돌IK→Blender local Quaternion 순서다. 원본 JSON의 기존 필드 및 MHR회전은 덮어쓰지 않는다. 재생 JSON의 smoothing=true, root_motion은 bool 유지, root_motion_kind로 측정된월드이동과 구분. 보고서에 correction 코드SHA 및 corrected_motion_sha256 추가. CONSTANT 프레임 키는 유지하고 누락/컷을 메우지 않는다. 시간필터와 접지의 추정 한계는 MVP4 보정 요약 참조.


## v0.7.2 연속 재생

이전 CONSTANT 전체샘플 정책은 아래 방식으로 대체한다. JSON 정수프레임의 두 bone pose가 모두 유효하고 같은 segment/scene일 때 .blend에0.25/0.5/0.75프레임 SLERP 회전·선형 위치키를 추가하고 그 구간은 LINEAR. 미검출/컷/개별 관절누락 경계 및 가시성 채널은 CONSTANT를 유지한다. 추가키 사이 Quaternion 성분은 선형 근사다. correction.revision=2의 feet 전환상태(contact_transition/collision_transition/release_blend)는 완전히 고정된 접지가 아니므로 접지 정확도나 foot-lock 지표에 inferred_contact와 합산하지 않는다. 원래 swing 동작과 제약offset 감쇠를 구분한다.


## v0.7.3 잔떨림 파라미터

correction.revision=3. 기존 하한3Hz를1.5Hz로 낮추고 상한18Hz 유지, 이웃0.10초 각운동 일관성 가중을 추가한다. 이웃6도 이내/중앙12도 초과의 고립 impulse 억제와 IK 굴곡면0.07초(빠른변화0.025초) 안정화 포함. 추정/누락 상태와 유효span/컷 경계를 보존하며 원본 M3 motion을 바꾸지 않는다. 재생 보간 정책과 root_motion_kind는 v0.7.2 그대로다.


## v0.7.4 강한 저속 완화

correction.revision=4, cutoff_hz=[0.9,18], 속도 상승계수2, IK pole0.10초(큰방향변화0.025초). 새 스키마·본·보간키 추가가 아니라 같은 시간필터의 강도조정이다. 원본/누락/컷 및 접지전환·quarter-frame 재생 정책 유지.


## v0.7.6 영상근거 웅크림 지지

M3 standard_motion_positions_v1은 그대로 유지한다. export 시 동일 input SHA의 native MHR70 image_joints에서 발목13/14, 발끝15·16/18·19 평균, 골반9·10 평균을 보조 입력으로 읽는다. correction.revision=5, frames[].image_ground_support=[bool,bool], feet의 새 상태 inferred_ground_support는 수직 접지만 추정하고 XY잠금을 뜻하지 않는다. 원래 inferred_contact는 XY잠금을 유지한다. 부드러운 진입 중에는 기존 collision_transition 표기를 사용한다. metadata image_ground_evidence_used와 crouch_support, 내보내기 report ground_evidence_sha256을 포함한다. 유효연속구간 안의 양발접지 seed≥0.1초(최소3프레임), 영상5프레임 median, 발목/발끝 각각 seed median Y의 -0.03~+0.12×영상높이, 양무릎내각<150도, 발대비골반하강>0.035×영상높이, 연속0.1초(최소3프레임)에서만 새 지지. 화면밖/누락/컷 경계를 넘지 않는다. 접지높이0.07/0.03m, 본길이/SLERP 파라미터는 동일. 실측바닥·월드이동·신발형상·전체정답정확도 보장이 아니다.


## v0.7.7 영상·접지 루트

M3 schema는 유지한다. correction.revision=6, 새 파생 root_motion_kind=image_and_contact_estimate (새 근거가 없으면 contact_constraint_estimate). frames[]의 image_root_drive, image_moving_support[2], estimated_airborne은 근거 적용/예측 여부이며 정확도 confidence가 아니다. feet에 estimated_airborne 추가. 공중 루트Z는 가상 바닥 루트의 위 이동, pelvis는 전체 위치 보정으로 결정된다. 기존 root_xy_soft_speed_limit_mps=1.8는 접지 조정 prior, 영상 후보X/Y 조정은 각각2.5/1.2m/s, 공중Z는3m/s로 별도 제한하므로 합성 후 전체 동작의 hard speed cap이 아니다. camera 처리: 최대변480 grayscale, 배경 feature≤240, LK forward/back오차<0.8px, RANSAC inlier≥16·비율≥0.65·XY분포≥화면0.18, median잔차≤0.65px. 단계 scale0.95~1.05/회전3도/이동0.12화면 이내, 누적scale0.5~2/이동0.75화면 이내. 확실하지 않으면 epoch를 끊고 기존 접지를 사용한다. 기본focal=hypot(width,height)는 로컬 SAM prepare_batch의 기본 intrinsics와 동일. metric projection·깊이는 모델 단위의 추정이다. export report root_motion_analysis에 유효/거부/epoch 수, source/raw SHA, 모델·스케일 한계를 저장하고 root_solver_sha256/root_camera_job_sha256를 생성 후 다시 확인한다.


## v0.7.8 작은 곡률 완화

M3/animation schema 및22본 그대로, correction.revision=7. 기존 quaternion IIR 후 각 유효span에서 stride=max(1,round(fps/30))의 앞뒤 shortest SLERP midpoint를 구한다. 현재값과 차이가 상체2~8도/다리1~5도 사이에서 smoothstep으로 가중치0.5→0, 임계 이상 큰 차이는0이다. 일정각속도는 midpoint와 같아 유지한다. endpoint와 stride보다 짧은span은 그대로. 영상 루트 XY 후보도 같은 시간 간격의 midpoint 거리5~25mm에서0.5→0 가중치, Z는 그대로. 접지/IK 후 위치나 최종 local Quaternion을 다시 평균하지 않는다. 필터 파라미터는 small_rotation_curvature_degrees, leg_small_rotation_curvature_degrees, small_rotation_smoothing_seconds 및 root_solver_sha256으로 확인한다. 미세한 실제 움직임과 잡음 구분은 완전하지 않다.


## v0.7.9 축 방향·누락 정책

우선순위5의 첫 보정 적용. 기존 단순 평행이동 회전 전달은 몸통 회전과 무관한 축 방향을 오래 유지할 수 있었다. 상완·전완·허벅지·종아리8본에서 부모의 현재 회전과 rest 상대방향으로 축 사전값을 만들고, 관측된 본 방향으로 swing을 맞춘 뒤 기존 전달 방향에서 축 roll만 보정한다. Quaternion 사용, 시간상수0.18초·최대120도/초이며 관측된 빠른 swing 자체를 속도 제한하지 않는다. 접지 발의 바닥 기준 roll, 위치·본길이·루트·접지·점프 및 v0.7.8 잔떨림 보정은 그대로다.
동일 추적/장면 안의 부분 누락은 최대0.25초까지만 이전 roll을 기억한다. 긴 부분 누락 뒤에는 부모 사전값으로 재시작하고, 전신 분실/장면·추적 경계에서는 기억을 버린다. 누락 위치/Quaternion은 계속 null이며 보간하지 않는다. animation.json의 orientation_policy에 본별 short_missing/long_missing 구간, 재연결 수, 적용 최대roll, filled=false를 기록한다. 이는 가려진 동작을 생성하는 모델이 아니라 보수적인 방향 재연결 정책이다.
M3 및 standard_bone_animation_v1은 유지하며 animation.json에 orientation_policy 진단 metadata를 추가한다. revision=2, twist_prior, twist_bones, twist_time_constant_seconds, max_twist_correction_degrees_per_second, max_applied_twist_step_degrees, short_gap_roll_memory_seconds, short_roll_reconnections, long_roll_restarts, missing_spans, missing_positions_filled를 포함한다. 구간 start_frame/end_frame은0시작 양끝 포함, seconds=프레임수/fps, 같은 추적/장면별로 분리한다. long_roll_restarts는 긴 부분 누락 뒤 해당8본 재시작 횟수이며 전신 분실/컷은 캐시 자체를 버리므로 이 수에 포함하지 않는다. correction.revision=7은 그대로.


## v0.8.0 Engine FBX export

사용자가 Norma 제외6영상 결과를 긍정 확인하고 다음 작업 진행을 요청했다. M4 결과 검증을 정리하고 계획의 M5 Unreal Motion Preview 첫 단계에 진입했다. M5.5 분석/Mapping/Profile/임의 캐릭터 Retarget은 아직 시작하지 않았다.
새 app.engine_export_job + tools/export_engine_fbx는 저장된 M4 animation.blend/animation.json을 읽어 animation-<id>/engine-<id>/Motion_Unreal.fbx, Motion_Unity.fbx 및 export.json을 생성한다. 새 GUI 버튼 Unreal · Unity FBX 저장을 기존 worker/취소/busy 경로에 연결했다. 기존 Blender 버튼 유지, 원시/M3/보정/이전Blend 보존, 모델·GPU 재추론/의존성 추가 없음.
정수 샘플 경계의 엔진 호환성을 위해 초 단위 시간을 유지하면서30fps로 리샘플한다. 원본 길이와 FBX 길이 차이는 종료점 반올림의 최대1/60초이며 source_fps/source_duration/fbx_duration을 기록한다. 22본과 rigid BoneProxy 메쉬를 출력하며 별도 타깃 캐릭터에 맞춘 결과는 아니다.
한계: FBX에는 관절별/전신 누락의 유효성 flag와 객체 숨김을 신뢰성 있게 전달하지 않는다. 누락 구간은 M4의 부모/rest fallback 또는 hold가 포함될 수 있으며 복원 동작이 아니다. export.json missing_spans/missing_pose_frames 및 원본 animation.json을 함께 확인해야 한다. M5 긴누락 클립 분리·엔진 표시 정책, 전체6영상 엔진 재생 시각확인, Unity 임포트, 엔진 화면 자동열기·영상 동기화는 남았다. 이번 UE 검증은 NullRHI commandlet이므로 화면의 조명/시점/재생 품질은 사용자 확인 대기다. 스킨은 기존 bone proxy이며 제작용 캐릭터가 아니다. M5 전체 완료 선언 없이 첫 체크포인트로 보관한다.
Motion JSON/schema/22본은 변경하지 않는다. export.json은 FBX 파생 파일의 manifest이며 Core 경계를 대체하지 않는다.
