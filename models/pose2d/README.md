# M1 로컬 모델

현재 모델 파일 두 개는 이 폴더에 준비되어 있습니다.
실행 시 manifest.json의 SHA256과 대조합니다. 해시는 이번에 공식 배포처에서 받은 ONNX 파일의 고정 식별값이며, 배포자의 전자서명을 대신하지 않습니다.

| 파일 | 모델 | 입력 크기 | 크기 |
|---|---|---|---|
| yolox-tiny.onnx | HumanArt YOLOX tiny 인물 검출 | 416 × 416 | 20,283,006 bytes |
| rtmpose-m.onnx | RTMPose m body7 COCO 17 관절 | 192 × 256 | 54,330,655 bytes |

파일이 없으면 manifest.json의 archive_url에서 해당 ZIP을 내려받고, 각 ZIP 안의 end2end.onnx만 꺼내 위 이름으로 보관하세요.
프로그램 실행 중에는 모델 다운로드를 시도하지 않습니다.

RTMLib 0.0.13의 전처리·후처리 API를 사용하며, YOLOX는 인물을 검출하고 RTMPose는 선택된 박스에서 관절을 추정합니다.
RTMPose confidence는 원시 모델 점수이며 보정된 확률이나 정확도 백분율로 해석하지 않습니다.
이 Pose2D JSON은 프레임별 2D 추론 결과이며, M3에서 정의할 Motion JSON과 별도입니다.

## 출처

- [OpenMMLab RTMPose](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose)
- [RTMLib 모델 목록과 사용법](https://github.com/Tau-J/rtmlib)
- [YOLOX](https://github.com/Megvii-BaseDetection/YOLOX)
- [RTMLib Apache 2.0 라이선스](https://github.com/Tau-J/rtmlib/blob/main/LICENSE)
- [MMPose Apache 2.0 라이선스](https://github.com/open-mmlab/mmpose/blob/main/LICENSE)

패키지 버전은 프로젝트 루트의 requirements.lock에 고정되어 있습니다.
