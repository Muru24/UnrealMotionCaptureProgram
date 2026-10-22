# SAM 3D Body ViT-H 비교 준비 (아직 미설치/미채택)

사용자 2026-10-15 요청에 따른 다른 3D 추론 모델 비교 후보입니다.
현재 프로그램은 MediaPipe Full v0.3.3 그대로이며 이 폴더를 로드하지 않습니다.

공식 모델: https://huggingface.co/facebook/sam-3d-body-vith
공식 설치: https://github.com/facebookresearch/sam-3d-body/blob/main/INSTALL.md
공식 라이선스: https://github.com/facebookresearch/sam-3d-body/blob/main/LICENSE

2026-10-15 공개 API의 gated=manual, model.ckpt 익명 HEAD는 HTTP401/GatedRepo입니다.
모델 페이지에서 사용자가 직접 접근 조건/연락처 공유 내용을 확인하고 접근 승인을 받아야 합니다.
이메일/계정/토큰을 대신 제출하거나 접근 제한을 우회하지 않습니다. 채팅에 토큰을 보낼 필요 없습니다.

승인 후 같은 공식 저장소 revision의 파일을 다음 위치에 보관하면 비교 준비를 이어갈 수 있습니다.

```text
models/sam3d_body_vith/model.ckpt
models/sam3d_body_vith/model_config.yaml
models/sam3d_body_vith/assets/mhr_model.pt
models/sam3d_body_vith/LICENSE
```

확인한 repo revision: f7f4ba4f67739e297f291639afb7c59041745367.
가중치 파일 자체의 SHA256은 다운로드 후 검증·기록합니다. 현재는 LICENSE만 검증 다운로드했고 가중치는 없습니다.
SAM 코드/가중치의 SAM License 및 MHR Apache2.0의 상업 사용 가능 조건은 공식 자료로 확인했습니다.
실제 설치 구성의 의존 코드/가중치 추가 조건, Windows·RTX4060 8GB 실행 가능성, Norma/Vivian 실제 관절 개선은 아직 검증 전입니다.
새 runtime은 별도 환경에서 검증하고, 기본 .venv/출력 규격/모델은 검증 전 변경하지 않습니다.

## 다운로드 진행 상태 (2026-10-15)

사용자가 접근 승인 완료를 알리고 다운로드를 요청했습니다. 별도 .validation/hf_download_env에 공식 huggingface_hub 2.2.0을 설치했습니다.
공식 브라우저 기기 인증은 두 번째 시도에서 성공했고 인증 정보는 snapshot/Git 제외 .validation에 보관합니다. 토큰을 채팅이나 Git 자격증명에 저장하지 않습니다.
로그인 계정으로 ViT-H와 DINOv3 설정 파일을 확인했으나 둘 다 HTTP403, 승인 목록에 없다는 응답입니다.
사이트 로그인 후 모델별 접근 승인이 필요합니다. 정확한 대상 페이지: https://huggingface.co/facebook/sam-3d-body-vith .
현재 LICENSE(8,204bytes)만 다운로드·Git blob 해시 검증 완료. model_config.yaml/assets/mhr_model.pt/model.ckpt는 미다운로드.
예상 전체 크기 약2.39GB. 공식 저장소 revision 및 LFS SHA256/Git blob 해시로 파일을 검증하는 .validation/download_sam3d.py를 준비했습니다.

## 2026-10-15 승인/다운로드 갱신

기존403 기록 이후 접근 승인 확인. 필수4개 전부 다운로드 및 공식 LFS SHA256/Git blob 검증 완료. 상세 download-manifest.json(status complete). 실제프로그램은 Full v0.3.6 유지하며 SAM 미채택. 별도 Windows 추론 환경/소스는 .validation/sam3d, 검증 결과는 validation/m2/sam3d 예정. CPU호환 변경은 별도사본/diff로 분리한다.

## 실행 결과 갱신

CPU별도환경에서실제16프레임body+4full추론완료. validation/m2/sam3d/README.md 참조. Vivian285부분개선/Norma87·128실패지속. 현재앱Full v0.3.6 유지. CUDA는디스크공간위험으로미설치, CPU한국어경로/장치변경사본diff보존. 모델파일내용불변.

## 2026-10-16 GPU 실행 갱신
CUDA 별도환경 설치/pip check 및 RTX4060 body16/full4 실행 성공. 상세 validation/m2/sam3d/README.md. Norma 오추정 잔존, 기본 앱 SAM 미적용. 이전 CUDA 미설치 상태는 해소됨.

## v0.3.9 프로그램 연결
현재 SAM 선택 모드는 YOLOX/TargetTracker 프레임별ROI를 별도CUDA환경에 전달하며 native70/version2 결과를 저장한다. 대상분실은 추론·발보완하지 않으며 기존고정ROI/version1 출력도 발보완에서 지원한다. Norma모호성/관절오추정은미해결. 주 README와 md/CURRENT_TASK.md가 현재 상태 기준이다.

## v0.4.0 복합 연관
SAM최종3D에 앞서 RTMPose2D를 대상연관보조로 재사용. IoU/예측중심/관절/HSV외형 점수 사용, 학습된ReID임베딩은미적용. 모델가중치와별도CUDA환경은변경없음. Norma잔여실패와검증은md/CURRENT_TASK.md 및 tracking-v040 참조.
