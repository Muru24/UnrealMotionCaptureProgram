# MVP3 v0.6.0 구현 요약

사용자 승인 M3: Blender제작 참조본을 Unreal/Unity 양쪽 임포트 대상으로 제공하고 영상 옆에 동기화된 표준스켈레톤을 표시한다. v0.6.0, 원시MHR70·회전·MVP2결과 보존. 본회전/메쉬모션/Bake/엔진직접임포트는 미구현·미검증으로 구분한다. 새모델/의존성/다운로드/GPU재추론 없음.

## 사용

프로그램 재실행 후 새SAM출력은자동변환. 기존결과는목록에서영상을연뒤3D패널의변환을누른다. 영상옆3D를재생/seek하며드래그회전·휠확대·정면/측면확인. 기존LongSword/프로미스나인/유니3D결과는CPU변환을미리실행했다.

## 산출물

- [Blender 원본](../assets/skeletons/MotionHumanoid22.blend)
- [Unity FBX](../assets/skeletons/MotionHumanoid22_Unity.fbx)
- [Unreal FBX](../assets/skeletons/MotionHumanoid22_Unreal.fbx)
- [자산 사용·임포트 검증 범위](../assets/skeletons/README.md)
- [Motion JSON 규격](../md/MOTION_FORMAT.md)
- 결과별 motion/motion.json과motion/report.json

## 검증

66PASS/권한opt-in1SKIP, compileallPASS. 새시험12개. Blender원본/FBX2개22본·부모·스킨·미터좌표재임포트검사. 기존3영상6051프레임원시불변CPU변환. 입력모델의가용프레임을그대로유지했으며가림정답복원아님. 처리시간은재사용/파일읽기를포함한CPU변환시간이지GPU추론속도아님.

## 남은 일

- Unreal/Unity 실제임포트·Humanoid Avatar판정 미검증.
- 현재는제자리·고정체형관절위치, 본회전/스킨메쉬애니메이션/Root Motion/접지는후속단계.
- Norma 의상오추정과기존M2후보초기26프레임기준제약, QA-002는남음.
- 다음M4에서Quaternion로컬본회전과참조리그동작을연결한다.
