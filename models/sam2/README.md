# SAM 2.1 Small / 대상 마스크 추적 시험

이 모델은 영상 속 선택 영역을 추적한다. SAM 3D Body의 3D 관절 추정 모델과 다르다.

- 공식 소스: https://github.com/facebookresearch/sam2
- 소스 commit: `2b90b9f5ceec907a1c18123530e92e794ad901a4`
- 가중치: `sam2.1_hiera_small.pt`, 184,416,285 bytes.
- SHA256: `6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38`.
- URL: https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt
- 공식 README는 모델 가중치와 소스에 Apache 2.0을 명시한다. LICENSE를 보존했다. 선택 CUDA connected components의 BSD 고지도 LICENSE_cctorch로 보존했으며 이 시험에서는 해당 확장을 사용하지 않는다.

## 로컬 실행 구조

데스크톱 Python에 Torch를 설치하지 않는다. `.validation/sam3d/env/Scripts/python.exe`의 기존 CUDA Torch 2.8.0/torchvision 0.23.0을 읽기 전용으로 공유하며, SAM 2 소스는 `.validation/sam2/source`, 추가 의존성은 `.validation/sam2/deps`에 분리했다. 기존 SAM3D 패키지는 업그레이드하지 않았다.

추가 의존성: hydra-core==1.3.2, iopath==0.1.10, portalocker==3.2.0, termcolor==3.2.0. 공식 소스와 가중치를 준비하는 명시적 스크립트는 `validation/sam2/setup_runtime.py`다. 이 스크립트는 신규 설치용이며 기존 source를 덮어쓰지 않는다. 소스 hash는 `.validation/sam2/source-manifest.json`에 기록했다. 앱 실행 중 네트워크 다운로드는 하지 않는다.

공식 Windows 안내는 WSL을 권장하지만, 이번 시험은 native Windows에서 선택 CUDA 확장을 끄고 실행한다. 별도 프로세스에 공식 모델 소스를 import하고, OpenCV로 추출한 JPEG를 최대2프레임 캐시하는 로더를 연결했다. 전체 영상을 1024 정사각 텐서로 한 번에 메모리에 적재하지 않는다. 마스크 구멍 메우기 후처리는 비활성화했다. 공식 모델 파라미터와 소스 파일은 변경하지 않았다.

## 제한

2D 관절은 프레임 연결에 사용하지 않는다. 첫 프레임 YOLOX 박스로 사용자 지정 대상을 초기화하고 이후 SAM 2 영상 메모리를 따른다. 머리카락·의류도 사람 영역에 포함될 수 있으며 3D 관절의 오추정을 교정하는 기능은 아니다. 마스크 신뢰도/안정성은 인물 신원을 증명하지 않는다. 가림·교차·편집 컷에서 다른 대상 연결 가능성이 있다. 장면 전환 처리 및 중간 프레임 재지정은 아직 없다.

ROI는 마스크 외접박스에 여유 영역을 더해 만들고 SAM3D에는 그 위치의 원본 RGB 영상을 전달한다. 마스크 밖을 검게 지우지 않는다. 빈/불안정/분할/급변 마스크는 불확실로 보고 ROI를 전달하지 않는다. 불확실 구간 뒤 재관측은 새 segment로 분리해 기존 보완이 경계를 건너지 않게 한다.
