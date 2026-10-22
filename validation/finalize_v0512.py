from pathlib import Path
import json,hashlib,shutil,zipfile,re
root=Path(__file__).resolve().parents[1]
evidence=root/'validation/sam2/person-track-v0512'
results=json.loads((evidence/'confirmed/comparison.json').read_text(encoding='utf-8'))
assert len(results)==4 and all(r['predictions_passed_as_pose_roi']==0 for r in results)
cases=root/'진행상황';number=max(int(p.name[4:]) for p in cases.iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=cases/f'case{number}';case.mkdir()
counts='; '.join(f"{r['video']} {r['frames']}프레임/관측누락{r['missing_frames']}/최장{r['max_gap_seconds']:.3f}초/박스점프검토{r['box_jump_events']}건" for r in results)
note=f'''## 2026-10-19 / v0.5.12 5단계 계획 중 1번 사람 추적 1차 보강

Milestone M2 IN_PROGRESS. Task: 사람 추적으로 선택 대상과 위치 유지. Goal: 관절 오추정이 대상 연결을 바꾸지 않도록 마스크 관측과 위치 예측·재연결 상태를 분리한다. Scope: core/pose2d/mask_tracking.py, app/sam2_worker.py, GUI 버전 표기, 관련 tests/validation. Acceptance: 2D 관절 없이 마스크 중심 Kalman 예측, 짧은 누락 상태 보존, 위치 이탈 마스크 거부, 연속 관측 재연결, 예측값을 실제 SAM3D ROI로 전달하지 않음. 이번 범위 구현·검증 완료. 2~5번의 전신 후보/관절별 검사/팔다리 주변 프레임 재추정/관절 관측 재연결은 후속 작업이다.

기존 경로는 첫 프레임 YOLOX 대상 선택 → SAM2 영상 메모리 마스크 추적 → SAM3D 자세 추정으로 이미 분리되어 있었다. 매 프레임 사람 detector나 관절 similarity를 새로 추가하지 않았다. 기존 BodyMotion의 constant-velocity Kalman을 재사용하되 실제 입력은 전체 사람 마스크의 가시 영역 중심이고 골반/척추/root 관측이라는 뜻은 아니다. 마스크가 옷·머리카락까지 포함할 수 있으며 관절 정답을 검증하지 않는다.

변경: 기본 SAM2 사람 추적에 motion_guard를 켠다. 마지막 박스와의 이동거리만이 아니라 예측 중심에 대한 잔차(직전 크기 대각선 0.65 이내)를 검사한다. 거부한 마스크는 예측기를 갱신하지 않는다. 최대0.5초 짧은 누락의 예상 중심/박스를 sidecar motion 필드 및 마스크 프리뷰 주황 박스로 표시한다. roi/person_bbox는 실제 유효 관측이 없으면 None이라 SAM3D가 예상 영역을 실제 관측으로 오인하지 않는다. 두 프레임 이상 누락 후 재연결은 2회 연속 위치 관측을 확인한다. 단순히 bbox IoU가 낮다는 이유로 회전 후보를 버리지 않는다. 장기 분실은 requires_reselection으로 남겨 다른 사람으로 자동 갈아타지 않는다. 중간 프레임 수동 재선택 UI/장기 재검출은 미구현이다.

전환 검사에서 발견한 원인·해결: 최초안은 hard cut에서 영구 잠금해 vivian265프레임 뒤229프레임, 뒤차기104프레임 뒤209프레임을 추가로 누락시켰다. 실제 vivian264~266 영상은 동일 캐릭터의 편집 시점 전환이었다. 이를 그대로 채택하지 않고, 전환 전 운동 예측을 폐기한 뒤 마스크 내부 HSV 히스토그램 reference bank(최대12개, 초기값 보존)와의 Bhattacharyya 거리0.55 이내 및 2연속 관측으로 새 위치 필터를 시작하도록 수정했다. 전환 확인 시간도0.5초로 제한하고 근거가 없으면 재선택 필요로 남긴다. HSV 색상은 학습된 ReID embedding/신원 증명이 아니며 같은 복장·다른 인물/거울·조명 변화의 한계가 남는다. track_id=1은 고정 선택 ID이지 신원 정답률 지표가 아니다. 별도 SAM2 신발3객체 경로는 기존 정책으로 유지한다.

실제 검증(수정 후 4영상 전체 새 SAM2 GPU 추적, 새 SAM3D 자세 추론 없음): {counts}. 신규 ROI 예측 오인 전달0건. Norma와 뒤차기만 같은 첫 상자·프레임 수의 기존 outputs 기준이 있어 직접 비교했고 vivian/LongSword는 동일 조건 기존 outputs 기준이 없어 개선률을 주장하지 않는다. 박스 점프는 자세 확장/회전에 의해서도 발생하므로 오류 확정 수가 아니다. 신원/관절 정답 라벨이 없으므로 자동 대상 변경0건이나 관절 오추정 해결을 확정하지 않는다. 증거 validation/sam2/person-track-v0512/confirmed/{{comparison.json,각영상/sam2-plan.json,mask-tracking.mp4}}. 최초 실패안도 상위 폴더에 진단 증거로 보존한다.

테스트: 최종 코드의 비GUI376항목 및 GUI5항목을 분리 실행하여 총381 PASS/권한 opt-in1 SKIP. 새 사람 추적 검사11개(짧은 누락·잘못된 먼 마스크·재연결 연속성·컷·장기 분실·웅크림·프레임 순서·외형 확인·전환 속도 폐기), 기존 mask 검사14개 모두25 PASS/exit0. GUI5는 각 별도 프로세스 PASS. compileall PASS. QA-002 재관측: 초기 통합373 PASS 요약 후 exit -1073741816(0xC0000008), 재실행도 같은 비정상 종료. 원인 미확정, 테스트 assertion 실패는 없었다. 34파일 분리 중 test_video도15 PASS 요약 후 같은 종료가1회 있었으나 단독 재검15 PASS/exit0. 나머지 파일별 검사 exit0. 원인 해결 선언 없이 QA-002 VERIFYING을 유지한다. 분리 로그 test-split/summary.json 및 각 로그, 마지막25/15 재검은 도구 출력 참조.

사용: StartPrototype.cmd 재시작 → SAM3D+SAM2 모드에서 새 출력. 기존 생성 결과는 재계산하지 않는다. 사람 영역 추적과 뼈대 오추정은 별개이며 Norma 망토·옷에 다리 관절이 붙는 문제는 3~4번 관절 검사·부위 재추정에서 이어간다. 원본4MD 및 case{number} 해시 일치 보관, v0.5.12 MVP 저장. 기존 사용자 출력·MVP·HOME ZIP 보존.

'''
for name in ('CURRENT_TASK.md','PROGRESS.md','ISSUES.md','PROJECT.md'):
    p=root/'md'/name;p.write_text(note+'---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8');shutil.copyfile(p,case/name)
    assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((case/name).read_bytes()).digest()
p=root/'README.md';p.write_text(p.read_text(encoding='utf-8').replace('현재 작업 버전은 v0.5.11','현재 작업 버전은 v0.5.12')+'\nSAM2 사람 추적: 마스크 중심 Kalman 예측/위치 검사/연속 관측 재연결을 적용합니다. 예상 위치는 실제 자세 관측으로 쓰지 않습니다. 편집 전환은 색상 근거와 연속 관측으로 새 운동 구간을 시작하며 신원 검증을 보장하지 않습니다.\n',encoding='utf-8')
p=root/'HOME_TRANSFER.md';p.write_text('# 최신 버전 v0.5.12\n\n5단계 중 사람 추적 1차 보강: SAM2 마스크 중심 이동 예측·관측 검사·전환 후 시각 확인. 새 출력에 적용. 관절별 검사는 후속. 최신4MD 및 v0.5.12 MVP 참조.\n\n---\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
verification={'version':'0.5.12','tests_passed':381,'permission_opt_in_skipped':1,'fresh_sam2_videos':4,'fresh_sam3d_inference':False,'qa002':'VERIFYING','results':results,'md_archive':case.name,'m2_pass':False}
(evidence/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
folder=root/'snapshots/v0.5.12 MVP';folder.mkdir();target=folder/'m2-person-tracking-v0.5.12.zip'
extra=[Path(__file__),root/'tests/test_mask_position_guard.py',root/'validation/person_track_v0512.py',root/'validation/person_track_diagnosis_v0512.py',root/'validation/person_track_overview_v0512.py',root/'validation/test_split_v0512.py',evidence/'verification.json',evidence/'vivian-cut.jpg',evidence/'test-split/summary.json',*case.glob('*.md')]
extra.extend((evidence/'test-split').glob('*.log'))
extra.extend(p for p in (evidence/'confirmed').rglob('*') if p.is_file())
with zipfile.ZipFile(root/'snapshots/v0.5.11 MVP/m2-dark-panel-v0.5.11.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as out:
    names=set()
    for info in old.infolist():
        name=info.filename
        if '__pycache__' in name or name.endswith('.pyc'):continue
        p=root/name;out.writestr(name,p.read_bytes() if p.is_file() else old.read(info));names.add(name)
    for p in extra:
        name=p.relative_to(root).as_posix()
        if name not in names:out.write(p,name)
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    for name in ('app/gui.py','app/sam2_worker.py','core/pose2d/mask_tracking.py','tests/test_mask_position_guard.py'):assert z.read(name)==(root/name).read_bytes()
    count=len(z.infolist())
data={'version':'0.5.12','files':count,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'tests_passed':381,'qa002':'VERIFYING','md_archive':case.name,'m2_pass':False}
(folder/'snapshot.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(data))
