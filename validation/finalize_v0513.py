from pathlib import Path
import json,hashlib,shutil,zipfile,re
root=Path(__file__).resolve().parents[1];evidence=root/'validation/sam2/fullbody-v0513'
verification=json.loads((evidence/'verification.json').read_text(encoding='utf-8'))
assert len(verification['existing_full_sequences'])==2 and verification['new_candidate_gpu_inferences']==24
split=json.loads((evidence/'test-split/summary.json').read_text(encoding='utf-8'))
assert len(split)==35 and all(r['exit']==0 for r in split)
passes=sum(int(re.search(r'(\d+) passed',r['summary'][0])[1]) for r in split)
assert passes==388
cases=root/'진행상황';n=max(int(p.name[4:]) for p in cases.iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=cases/f'case{n}';case.mkdir()
title='## 2026-10-20 / v0.5.13 2번 전신 후보·몸통 기준 전달\n\n'
current='''M2 IN_PROGRESS. 5단계 중 1번 사람 추적 보강 후 2번 전신 후보 전달을 구현·검증했다. 다음은 3번 관절별 시간 추적·검사(본 길이/좌우 연결/앞뒤 움직임/영상 근거), 그 뒤 4번 팔다리 주변 프레임 재추정 및 5번 실제 관측 재연결이다. 이번 변경만으로 의류·머리카락 관절 오추정이 해결된 것은 아니다.
Goal/Acceptance: 사람 추적과 원시 MHR 회전을 바꾸지 않고 원본·관측·좁은 영역·반전 전신 후보4개 및 골반/어깨 중심·팔/다리 묶음을 다음 단계에 넘긴다. MHR70에는 척추 마디가 없으므로 골반–어깨 축은 spine_axis_proxy로 명시한다. 추적 보류/예측만 있는 프레임은 후보를 만들지 않는다. 화면 안 좌표를 실제 가시성/신뢰도로 간주하지 않는다. Scope: core/pose3d/fullbody_candidates.py, app/fullbody_job.py, candidate_job.py, automatic_postprocess.py, GUI 및 tests/validation.
사용: StartPrototype.cmd 재시작 → SAM 모드 새 출력 또는 기존 SAM 결과 열기 → 미리보기 ‘전신 기준축’. 결과 패널에서도 fullbody-reference.mp4를 선택할 수 있다. 후보 선택 뒤 전신 묶음·미리보기를 자동 생성하고 다음 다리 단계로 이어진다. 기존 완료 후보는 모델 재추론 없이 정리하고 입력 해시가 같으면 재사용한다. 수동 앵커 UI는 복구하지 않았다.
검증: 395 PASS/권한 opt-in1 SKIP(35파일 분리388항목 후 최종 보강2항목 추가, GUI5 별도 프로세스). 최종 관련19 PASS는 전신14/자동처리5로 중복 실행분은 합계에 더하지 않았다. 모든 이번 분리 프로세스 exit0, compileall PASS. QA-002 원인 해결 선언은 하지 않는다. 실제 Norma2결과 각218프레임/4후보=872자세를 CPU 정리했고 원시/선택 SHA 불변. Norma60~67의8프레임은 새 GPU 대체24회 + 기존 baseline8로4후보를 검증했다. 그 외 프레임은 새 추론이 아닌 baseline만이다. 증거 validation/sam2/fullbody-v0513/verification.json 및 overview.jpg.
'''
progress='''기존 SAM3D full 추정 및 observed/stable/tight/stable-flip4후보 추론을 재사용했다. 모델/가중치·MHR70규격·native MHR회전·대상 ID·SAM2 ROI를 변경하지 않았다. fullbody-candidates.json(schema fullbody_hypotheses_mhr70_v1, exporter_revision1)에 프레임/대상/scene/추적segment, 모든 가용 후보의70개2D/3D관절, 선택 후보와의 일치 여부, parts, 팔다리 길이, 골반 중심·어깨 중심·neck·골반–어깨 기준축을 보존한다. 실제 척추 본·UE root·골반 회전을 새로 복원한 것이 아니다. 계산 좌표는 원 영상 픽셀/카메라 상대3D다.
후보의 joint_inside_frame은 이미지 경계 검사이며 visibility/accuracy_confidence는 None이다. 반전 후보의 출력 관절은 원래 좌표로 복원되어 있고 input_roi는 반전 영상 좌표라는 변환 출처를 별도 표기했다. 누락/잘못된 배열은 unavailable_candidates로 기록하며 다른 후보로 몰래 복사하지 않는다. 선택된 좌표가 후보와 다르면 selected_pose_not_in_pool로 표시한다. 추적 유실/예측전용/다른 target_id의 프레임은 후보를 비워 시간 보간이나 ID 재연결을 수행하지 않는다.
automatic_postprocess의 candidate_selection → fullbody_candidates → leg_reestimation 순서로 연결했다. 기존 candidates.json이 없는 경우에는 가용 baseline만 보존하고 실제4후보 생성 수를 명시한다. 직접 save_selection을 호출하는 경로도 입력 후보를 버리지 않도록 candidates.json을 저장한다. 재사용은 source/raw/selected/candidates SHA와 exporter revision을 확인한다. 내보내기 중 변경도 재검사한다. preview는 partial MP4로 작성 후 게시하고 중간 취소/실패 시 이전 완료본을 보존한다. 새 중간 단계 실패는 자동 보고서에 명시하고 완료된 원시/선택 결과를 유지한다.
GUI에 ‘전신 기준축’ 선택 항목을 새 출력/기존 SAM 열기 양쪽에 연결했다. 초록 팔다리/몸통 선, 노랑 골반–어깨 기준축, 파랑 중심점을 표시한다. 기존 다리 최종 비교와 수동 UI 제거 상태는 유지한다. 실제 Norma60/74 및 fresh62 확대 이미지를 시각 확인했고 의류에 잘못 붙은 관절은 여전히 보여 후속3~4단계의 검사 대상으로 남겼다.
실제 입력: Norma_sam3d_20261019_161500_20aae947/candidates_1c9056fa 및 Norma_sam3d_20261019_165800_c118ce5d/candidates_dff1f4ec 각각218프레임/872후보를 정리했다. source/sam3d/selected/candidates 파일 SHA 불변 확인. validation/sam2/fullbody-v0513/fresh-window에서60~67까지 observed/tight/stable-flip24개를 새 SAM3D GPU 추론했고 existing stable8과 합쳐32개 후보를 확인했다. 검증 패킷의 나머지210프레임은 baseline만이므로 전체218프레임을 새 추론했다고 주장하지 않는다. SAM2를 다시 실행하지 않았다.
검증: 신규 전신14항목, 자동처리5, 기존35파일 분리 및 GUI5 각각 통과. 전체 고유395 PASS/1 opt-in SKIP. 마지막 관련19 PASS/exit0. 기존 자동 단계 재사용 테스트는 새 전신 단계까지 완료된 상태를 먼저 준비하도록 조정했다. 최초 기본 sandbox temp에서는 파일 replace 권한 거부로 해당 자동단계가 partial이 되었고 workspace basetemp에서 실제 게시/재사용/취소·이전 결과 보존을 검증했다. 실제 검증 스크립트의 불완전 출력 폴더 발견은 필수 파일 없는 결과를 건너뛰도록 보완했다. 이번35파일 분리는 모두 exit0이며 QA-002 VERIFYING 유지. 테스트 로그 test-split/와 도구 출력, 실제 모델 checkpoint-audit.json 및 overview.jpg를 보존한다.
'''
issues='''M2-FB-001 / HANDLED: 전신 후보의 관절별 검사 전달 자료 부족. 기존 candidates.json은 후보 관절을 갖지만 후속 처리는 선택된 배열 중심이었고 몸통 기준·부위 묶음·출처·누락 이유의 공통 전달이 없었다. fullbody-candidates.json 및 기준축 프리뷰를 추가해 원본/대체후보와 출처를 함께 전달한다. 골반/어깨 중심과 spine_axis_proxy는 모델 관절의 파생값이며 실제 spine 본이나 영상의 정답 관측으로 표시하지 않는다.
검증·해결:14신규 사례로 원본 보존/4후보/추적유실·예측전용·다른ID 배제/화면밖 표시/누락·NaN 후보 분리/편집된 선택값 오표기 방지/해시 재사용·변경 감지/중간 취소·완료본 보존/중복 timeline 거부/단계 실패 전파를 확인했다. 반전 입력 ROI와 원좌표 출력 관절의 좌표계를 별도 표기했다. 최종 관련19 PASS/exit0 및 실제 Norma2개 전체 패킷·8프레임 새 GPU24추론 통과.
QA-002 / VERIFYING 유지: 이번35파일 분리와 GUI5는 모두 정상 종료했다. 이전 통합 pytest 종료 상태0xC0000008의 원인을 고친 것은 아니므로 전역 해결 선언은 하지 않는다.
남은 기존 문제: 옷·망토/머리카락에 잘못 붙는 관절은 모델4후보가 함께 틀릴 수 있다. 척추 proxy도 그 영향을 받는다. inside_frame만으로 가림/정상 관절을 판정하지 않는다. 다음3번에서 관절별 앞뒤 시간 움직임·길이·좌우 연결·영상 근거 검사를 구현하고4번에서 문제 팔다리만 재추정한다. 관절 정확도 개선률/M2 PASS를 주장하지 않는다.
'''
project='''승인된5단계의 2번을 보강: 사람 추적 결과를 고정한 상태에서 SAM3D 전신4후보와 몸통 기준을 공통 sidecar로 넘긴다. 신규 모델·의존성·기본 Skeleton/회전 포맷 변경 없음. native70관절/원시 MHR회전은 보존한다. spine_axis_proxy는 골반–어깨 파생 기준축이며 native 척추 체인과 다르다. 이미지 경계 여부와 가시성/정답 신뢰도를 구분한다.
자동 제품 경로: SAM2 사람 추적 → SAM3D full/전신 후보 선택 → fullbody-candidates.json 및 fullbody-reference.mp4 → 기존 다리 재추정. 새 전신 패킷에는4후보/부위별 관절/골반·어깨 중심/neck/길이/추적segment/원본 해시/입력 반전 출처가 포함된다. 관절별 시간 추적·검사(3번), 주변 프레임 부위 재추정(4번), 실제 관측 재연결(5번)은 후속이다. 현재 M2 IN_PROGRESS.
검증된 범위는395고유 테스트, 실제 기존Norma2결과 각218프레임 패킷, 회전8프레임 대체24회 새 GPU추론이다. 전체 새 영상의 관절 정확도가 개선됐다는 의미는 아니다. QA-002 기존VERIFYING 유지.
'''
for name,text in [('CURRENT_TASK.md',current),('PROGRESS.md',progress),('ISSUES.md',issues),('PROJECT.md',project)]:
    p=root/'md'/name;end=f'원본4MD 갱신 및 case{n} SHA 동일 복사, snapshots/v0.5.13 MVP 저장. 이전 사용자 출력·MVP·HOME ZIP 보존.\n\n'
    p.write_text(title+text+end+'---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8');shutil.copyfile(p,case/name)
    assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((case/name).read_bytes()).digest()
p=root/'README.md';p.write_text(p.read_text(encoding='utf-8').replace('현재 작업 버전은 v0.5.12','현재 작업 버전은 v0.5.13')+'\n전신 후보: SAM 후보 선택 후 fullbody-candidates.json을 자동 생성합니다. 미리보기 ‘전신 기준축’에서 골반·어깨 중심과 파생 몸통축을 확인할 수 있습니다. 척추 마디/관절 정확도 교정은 별도입니다.\n',encoding='utf-8')
p=root/'HOME_TRANSFER.md';p.write_text('# 최신 버전 v0.5.13\n\n2번 전신 후보·몸통 기준축 전달 및 프리뷰 연결. StartPrototype.cmd 재시작 → SAM 출력 또는 SAM 결과 열기 → 전신 기준축. 다음3번 관절별 검사. 최신4MD/case'+str(n)+' 및 v0.5.13 MVP 참고. 이전HOME ZIP 유지.\n\n---\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
verification.update(tests_passed=395,permission_opt_in_skipped=1,gui_separate_processes=5,qa002='VERIFYING',md_archive=case.name)
(evidence/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
exports=evidence/'exports';exports.mkdir(exist_ok=True)
for row in verification['existing_full_sequences']:
    source=root/'outputs'/row['folder']/row['selection'];dest=exports/row['folder'];dest.mkdir(exist_ok=True)
    for name in ('fullbody-candidates.json','fullbody-reference.mp4'):shutil.copyfile(source/name,dest/name)
folder=root/'snapshots/v0.5.13 MVP';folder.mkdir();target=folder/'m2-fullbody-candidates-v0.5.13.zip'
extra=[Path(__file__),root/'core/pose3d/fullbody_candidates.py',root/'app/fullbody_job.py',root/'tests/test_fullbody_candidates.py',root/'validation/fullbody_v0513.py',root/'validation/fullbody_preview_v0513.py',root/'validation/test_split_v0513.py',*case.glob('*.md')]
extra.extend(p for p in evidence.rglob('*') if p.is_file() and not any(part.startswith('test_') for part in p.relative_to(evidence).parts[:-1]))
with zipfile.ZipFile(root/'snapshots/v0.5.12 MVP/m2-person-tracking-v0.5.12.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as out:
    names=set()
    for info in old.infolist():
        name=info.filename
        if '__pycache__' in name or name.endswith('.pyc'):continue
        p=root/name
        data=p.read_bytes() if not name.startswith('진행상황/') and p.is_file() else old.read(info)
        out.writestr(name,data);names.add(name)
    for p in extra:
        name=p.relative_to(root).as_posix()
        if name not in names:out.write(p,name);names.add(name)
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    for name in ('app/gui.py','app/automatic_postprocess.py','app/fullbody_job.py','core/pose3d/fullbody_candidates.py','tests/test_fullbody_candidates.py'):assert z.read(name)==(root/name).read_bytes()
    count=len(z.infolist())
data={'version':'0.5.13','files':count,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'tests_passed':395,'qa002':'VERIFYING','md_archive':case.name,'m2_pass':False}
(folder/'snapshot.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(data))
