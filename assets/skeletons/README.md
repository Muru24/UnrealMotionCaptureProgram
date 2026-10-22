# MotionHumanoid22 — MVP3 참조 스켈레톤

Blender 5.1.1로 제작한 22본 T-pose 리그다. Unity Humanoid와 Unreal의 일반 휴머노이드 리타게팅 입력을 위한 참조 자산이며, 두 엔진의 실제 임포트 검증은 아직 수행하지 않았다.

## 파일

- `MotionHumanoid22.blend`: 본·간단한 스킨 메쉬가 포함된 Blender 원본.
- `MotionHumanoid22_Unity.fbx`: Forward -Z / Up Y로 내보낸 정지 리그.
- `MotionHumanoid22_Unreal.fbx`: Forward X / Up Z로 내보낸 정지 리그.
- `humanoid_v1.json`: 프로그램과 Blender가 공유하는 기준 계층·head/tail·Unity 인체 역할.
- `build-report.json`: 실제 생성한 Blender 버전과 본 수 등.
- `engine-role-map.json`: 이 참조 리그의 정적 역할표. 임의 캐릭터 자동 매핑 기능은 아님.

두 FBX는 Blender exporter의 FBX 7.4 파일이다. Blender 재임포트에서 22본·부모 계층·스킨 바인딩·본 위치를 확인했으며 최대 위치 오차는 0.000001m 미만이었다. 이 결과는 Unreal/Unity에서 직접 임포트한 결과가 아니다. 엔진 버전별 임포터 경고·축·스케일·Avatar 유효성은 이후 엔진 검증에서 확인한다.

## 기준

- Blender 기준: 미터, +Z 위, -Y 앞, 캐릭터의 해부학적 왼쪽 +X.
- 기준 높이: 약 1.8m의 고정 참조 체형. 영상 속 실제 사람의 신장을 측정한 값이 아니다.
- `root` → `pelvis` → 척추/목/머리와 양쪽 팔·다리 계층.
- root는 비변형 기준 본이며, 몸·팔·다리 21개 본에 단순 메쉬를 바인딩했다.
- 메쉬는 본을 보기 위한 낮은 폴리곤의 강체 스킨이다. 완성형 캐릭터 표면이나 사실적인 피부 변형용 메쉬가 아니다.
- 손가락·눈·표정·트위스트·IK 제어 본은 이번 참조 리그에 포함하지 않는다.
- 동작 키프레임·본 회전 애니메이션은 아직 없다. M3는 위치 변환이며 M4에서 로컬 본 회전을 생성한다.

## Unity에서 확인할 항목

FBX를 임포트하고 Humanoid Avatar의 역할을 `engine-role-map.json`과 대조한다. Hips는 `pelvis`, Spine/Chest는 `spine_01`/`spine_02`이며, 추가 `root`를 Hips로 잘못 매핑하지 않는다. T-pose와 좌우 역할, 스케일을 Configure 화면에서 확인해야 한다.

Humanoid 역할 대응과 T-pose 기준은 [Unity 공식 Avatar 설정 문서](https://docs.unity.com/en-us/engine/7000.0/manual/assets-and-media/asset-types/models/importing/configuringthe-avatar)를 참고했다. 현재 자산을 Unity에서 실행해 유효 Avatar로 판정받은 것은 아니다.

## Unreal에서 확인할 항목

FBX에는 스켈레톤뿐 아니라 스킨된 참조 메쉬도 들어 있다. 새로운 참조 Skeleton으로 임포트해 본 계층·방향·약 180cm 높이를 확인한다. UE Mannequin과 일부 이름이 같아도 계층·기준 자세 전체가 같은 Skeleton은 아니므로 기존 Mannequin Skeleton에 무조건 합치지 않는다. 임의 캐릭터 리타게팅과 Animation Sequence 생성은 후속 단계다.

[Unreal 공식 FBX Skeletal Mesh 문서](https://dev.epicgames.com/documentation/unreal-engine/fbx-skeletal-mesh-pipeline-in-unreal-engine?lang=en-US)는 FBX 2020.2 파이프라인을 명시한다. Blender 출력과 엔진 임포터 사이의 실제 호환성은 엔진에서 별도 검증해야 한다.

## 재생성

`tools/build_reference_rig.py`를 Blender background/factory-startup으로 실행한다. 기존 자산이 있으면 덮어쓰지 않고 중단하도록 되어 있다. 다른 Blender 작업 창의 장면을 조작하지 않는다. [Blender 공식 FBX export API](https://docs.blender.org/api/5.0/bpy.ops.export_scene.html)의 축·leaf bone·단위 옵션을 사용했다.

현재 JSON 본 계층은 새 버전으로 교체하기 전까지 보존한다. 이 계층을 바꾸면 변환기·참조 자산·매핑표·캐시 버전을 함께 검토해야 한다.
