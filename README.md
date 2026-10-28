# Motion Studio

로컬 영상에서 사람의 동작을 추출하고 사람형 3D 모델에 적용하는 Windows 프로그램입니다.

## 사용

1. StartPrototype.cmd를 실행합니다.
2. 모델 적용 패널에서 모델을 추가하거나 등록된 모델을 선택합니다.
3. MP4 영상을 넣고 전체 추출을 실행합니다. 여러 사람이 나오면 대상 선택을 사용할 수 있습니다.
4. 원본/추적, 원본/본, 원본/모델 결과를 각 패널에서 확인합니다.
5. 필요하면 4번 패널에서 본을 편집하고, 5번에서 최종 MP4·Blender·FBX를 내보냅니다.

추출 과정에는 손 재추정 후보 선택, 떨림 보정, 자동 생성 리그의 무릎·발목 축 보정, 발바닥·높이 보정, 모델 검수가 포함됩니다. 무기 쥐기 보정은 기본 경로에 포함하지 않습니다.

## 입력과 한계

- 영상: 로컬 MP4, 최대 5분·2GiB·가로/세로 1920px, 짝수 해상도, 최대 18,000프레임.
- 모델: FBX, GLB, GLTF, OBJ, BLEND. 단일 사람형 모델을 대상으로 합니다.
- 본 없는 모델: 정면 T/A 포즈에서 본과 웨이트를 추정합니다. 해석 가능한 기존 리그는 보존합니다.
- 기존 본의 자동 매핑은 지원하는 이름·구성에 한정됩니다. 비인간형이나 임의 자세의 자동 리깅을 보장하지 않습니다.
- 가림·의상·머리카락 오추정, 손·관절 위치와 지면은 단안 영상 기반 추정입니다. 검수 경고가 있는 결과는 직접 확인해야 합니다.
- 얼굴 표정·의상 물리·메시 충돌은 기본 추출 범위에 포함하지 않습니다.

## 실행 환경

Windows, Python 3.11, Blender 5.1 및 로컬 SAM 3D Body/SAM 2 실행 환경이 필요합니다. Unreal Manny 경로는 Unreal Engine 5.8과 UnrealProjects/MotionCheckUE58 프로젝트를 사용합니다. 사용자 모델 경로는 Blender로 처리합니다.

기존 PC에서는 준비된 환경을 그대로 사용합니다. 새 PC의 기본 Python 환경은 다음 명령으로 준비할 수 있습니다.

    py -3.11 -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.lock

이 명령만으로 GPU 추론 환경과 모델 가중치가 설치되지는 않습니다. 다음 로컬 데이터는 Git에서 제외하며 별도로 준비해야 합니다.

| 경로 | 역할 |
| --- | --- |
| .venv/ | GUI·CPU 처리용 Python 환경 |
| .validation/sam3d/env/ | GPU 추론용 Python 환경 |
| models/ | RTMPose·SAM 2·SAM 3D Body·손 추정 가중치와 각 안내 파일 |
| assets/builtin_models/ | 로컬에서 준비한 기본 모델 |
| assets/user_models/ | 사용자가 추가한 모델과 선택 정보 |
| outputs/ | 추출 결과·애니메이션·편집 캐시 |

.validation 아래 Git에 포함된 vendor 소스와 LICENSE, assets/skeletons의 기준 리그는 실행에 필요합니다. 옛 실험 자료를 정리하더라도 이 소스와 실행용 GPU 환경은 유지합니다.

## 처리와 저장

- 같은 추출 결과에 다른 모델을 적용할 때 본·손가락 애니메이션을 재사용합니다. 입력·처리 코드·Blender 실행 파일 정보·출력 해시를 검사하고, 변경·손상이 있으면 재계산합니다.
- 모델별 리타게팅과 검수는 다시 수행합니다. 새 영상의 최초 GPU 추론까지 생략하는 캐시는 아닙니다.
- 전체 모델 미리보기의 임시 이미지는 JPEG 95 품질로 생성합니다. 최종 MP4 프레임 수 검증 후 번호가 붙은 임시 이미지만 정리합니다. FBX·BLEND·편집 원본은 보존합니다.
- 오류 단계는 제한적으로 재시도하며, 근거가 부족한 보정은 유지하거나 확인 필요 상태로 표시합니다.
- 새 결과는 별도 폴더에 저장합니다. 기존 편집 결과를 덮어쓰지 않습니다.

## 개발과 검증

주요 코드: app/의 작업 흐름과 GUI, core/의 추적·동작 처리, tools/의 Blender·Unreal 처리, tests/의 자동 테스트입니다. validation/sam2에는 일부 회귀 테스트가 사용하는 작은 보조 소스만 Git에 포함합니다.

    .venv\Scripts\python.exe -m pytest --collect-only -q
    .venv\Scripts\python.exe -m pytest tests/test_export_cache.py tests/test_automatic_model_checks.py -q

Tk GUI 테스트는 별도 프로세스로 실행하는 편이 안정적입니다. 처리 성능은 다음 도구로 측정할 수 있습니다.

    .venv\Scripts\python.exe -m tools.benchmark_model_exports outputs/<결과폴더> <측정결과.json> --model <등록모델ID>

과거 작업 기록·MVP·검증 산출물은 프로젝트 외부의 별도 보관 폴더와 검증된 ZIP에 보관합니다. 보관 manifest에는 원래 상대 경로와 파일별 SHA-256이 들어 있습니다. 저장소에는 실행 코드·테스트·필수 설정을 중심으로 유지합니다.
