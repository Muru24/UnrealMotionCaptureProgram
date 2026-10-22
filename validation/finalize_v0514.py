from pathlib import Path
import json,hashlib,shutil,zipfile,re
root=Path(__file__).resolve().parents[1];evidence=root/'validation/sam2/joint-review-v0514'
verification=json.loads((evidence/'verification.json').read_text(encoding='utf-8'))
assert len(verification['results'])==2 and all(r['inputs_unchanged'] for r in verification['results'])
split=json.loads((evidence/'test-split/summary.json').read_text(encoding='utf-8'))
assert len(split)==36 and all(r['exit']==0 for r in split)
passes=sum(int(re.search(r'(\d+) passed',r['summary'][0])[1]) for r in split);assert passes==409
cases=root/'진행상황';n=max(int(p.name[4:]) for p in cases.iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=cases/f'case{n}';case.mkdir()
title='## 2026-10-20 / v0.5.14 3번 관절별 궤적·검사\n\n'
current='''M2 IN_PROGRESS. 5단계 중 3번 관절별 궤적·검사 기반을 구현·검증했다. 다음은 4번 검사 근거와 주변 프레임을 이용한 팔·다리별 재추정, 그 뒤5번 재관측 연결이다. 이번 검사는 좌표를 고치는 기능이 아니며 정상/오류 정답 판정도 아니다.
Goal/Acceptance: 선택된 전신 후보의70관절을 대상/추적segment/scene/유효관측 연속구간별로 추적하고, 골반 중심을 뺀 카메라 상대좌표의 앞뒤 속도·양방향 시간 잔차, 본 길이 변화/좌우 비율·좌우 교환 의심·후보 불일치·화면/사람 마스크 근거를 기록한다. 추적 유실·다른ID·컷을 넘어 비교하거나 보간하지 않는다. 의심 부위별 요청과 같은 구간 안의 앞뒤 문맥 프레임을 다음 단계로 넘긴다. Scope: core/pose3d/joint_review.py, app/joint_review_job.py, automatic_postprocess.py, GUI, tests/validation.
사용: StartPrototype.cmd 재시작 → SAM 새 출력 또는 기존 SAM 결과 열기 → 미리보기 ‘관절 검사’. 결과 패널에서도 joint-review.mp4 선택 가능. 주황 선/점은 검사 표시이고 나머지도 정상 확정이 아닌 미검증 모델 추정이다. joint-review.json과 joint-repair-requests.json을 후보 폴더에 저장한다. 검사 입력은 기존 다리 재추정 이전의 선택된 전신 후보이며 기존 다리 최종 비교는 별도다.
검증: 414 PASS/권한 opt-in1 SKIP(36파일 분리409, GUI5 별도 프로세스). 신규19/자동처리5인 최종 관련24 PASS/exit0, compileall PASS. 실제 Norma2결과 각218프레임 검사, 마스크218개씩 사용, 원시/선택/전신 SHA 불변, 새GPU추론0. 각각149/151프레임에 검토 표시, 부위 요청63개씩이며 실제 오류 수/정확도 수치가 아니다.58~74 표본의 회전 다리는 표시되나0/6/12프레임은 표시되지 않는다. 후보 모두의 공통·매끈한 의류 오추정은 놓칠 수 있어 후속4번에 추가 영상 근거/부위 모델이 필요하다. QA-002 기존VERIFYING 유지.
'''
progress='''관절 궤적은 target_id/tracking_segment/scene_index/연속 관측 시작 frame/joint_index로 식별한다. root_relative_position과 앞뒤 속도를 저장하고 유실/컷 뒤 새 pose_track_start와 trajectory_id를 만든다. Kalman 관절 보정이나 native MHR회전 변환은 하지 않는다. 원래 이미지/3D 좌표를 보존하고 각 관절 상태를 model_estimate_unverified/review/outside_frame으로 구분한다. 포즈가 없으면 빈 관절 목록으로 남긴다.
검사 기준은 공개된 threshold dictionary와 함께 저장한다. 구간 내 모델 median을 본 길이/몸통 크기 기준으로 쓰고 본 길이0.65~1.55배, 좌우 길이 비1.8배, 약0.067초 앞뒤 프레임의 midpoint 잔차0.30몸통 크기, 후보 median 불일치0.35몸통 크기 또는0.08사람박스 대각선, 좌우 swapped 비용이 direct의0.55 미만인지 등을 검토한다. 기준 자체가 모델 추정이며 잘못된 중앙값일 수 있다. 카메라 평행 이동은 골반 중심을 빼서 제거하지만 빠른 실제 몸 회전/가속도는 표시될 수 있다. 한 augmentation의 실패로 전체를 거부하지 않도록 후보 차이는 median을 쓴다. 마스크 내부는 신체 부위 정답 근거가 아니다.
sam-tracking.json의 동일 frame/target 관측에 있는 mask만 영상 근거로 쓴다. 마스크 PNG의 배경 distanceTransform으로 관절과 사람 영역의 거리를 계산하며3~16픽셀 크기별 허용치를 둔다. 마스크 없거나 비정보성/틀린 크기는 unknown 등으로 기록하고 정상으로 간주하지 않는다. 외부 경로 마스크는 읽지 않고 timeline 불일치는 오류로 중단한다. 입력 영상·전신 packet·tracking·사용 마스크 내용 SHA로 캐시를 검사하고 export 도중 변경도 확인한다. preview partial 파일은 실패/취소 시 제거하고 이전 완료본을 보존한다.
자동 흐름: 후보 선택 → 전신 묶음 → joint_review → 기존 leg_reestimation. 새 검사는 joint-review.json(schema joint_review_mhr70_v1, review_revision2), joint-review.mp4, joint-repair-requests.json을 저장한다. 선택적 팔다리 재추정을 아직 실행하지 않으며 요청은 review_then_reestimate이다. 몸통 요청은 review_body_reference로 따로 남긴다. 요청 context는 약±0.15초이며 유효 연속 구간/scene/대상 경계를 넘지 않는다. 기존 자동 다리 처리의 동작과 입력은 그대로다. 새 단계 실패는 automatic-report에 stage=joint_review/failed로 남기고 완료된 원시·후보·전신 파일을 보존한다.
실제 Norma_sam3d_20261019_161500_20aae947/candidates_1c9056fa와165800_c118ce5d/candidates_dff1f4ec에 적용했다. 각각218프레임/사람 마스크218장, 검토149/151프레임, 요청63개씩. 왼팔94/오른팔107/왼다리87/오른다리77/몸통63프레임에 부위 표시가 있었다. 빠른 실제 동작/후보 차이를 포함할 수 있으므로149/151개 오류 검출로 해석하지 않는다.0/6/12표본은 표시 없음.58/60/62/66/70/74는 다리 temporal 및 일부 candidate disagreement 표시. source/sam3d/selected/fullbody SHA 불변. 새 추론 없이 CPU 검사만 실행했다. overview.jpg에서0/62/74의 표시를 확인했고 좌표 교정이라고 주장하지 않는다.
신규19테스트: 정지 궤적 불변/ID·속도, 관절 spike·길이, 좌우 교환 의심, 카메라 평행이동 제거, scene/segment/missing/target4경계, 단일 나쁜후보 무시·다수 불일치, mask 근거와 미검증 구분, 화면밖, 공통 systematic 오류의 한계, export/재사용/원시보존, 외부마스크 경로, timeline 오류, 취소/이전완료본보존, 실제 mask거리·내용변경 캐시, 검사 실패 후 기존다리 단계 중단을 검증했다. 최종 관련24 PASS. 전체36파일 분리409와 GUI5=414 PASS/권한1SKIP, 모두exit0. GUI는 새 출력과 기존 SAM 열기 양쪽 ‘관절 검사’ 항목 및 재생을 확인했다. compileall PASS. QA-002 원인 해결 선언은 하지 않았다.
'''
issues='''M2-JOINT-001 / HANDLED: 전신 선택 결과에 관절별 시간 궤적·검사 이유·부분 재추정 문맥 전달이 없었다. joint_review 단계로 관절별 ID/속도/시간 잔차/길이/좌우 교환·불일치/사람 마스크 및 화면 경계를 나눠 기록하고 부위별 요청을 생성했다. 관측 유실·scene/ID 경계 비교를 차단하고 원시 관절과 회전은 유지한다. 신규19 +자동처리5의 최종24 및 전체414 PASS/1 SKIP, 실제 Norma2개 전체검사·원시 SHA 보존 확인.
남은 한계: 의류 안으로 잘못 추정한 관절도 사람 마스크 안에 있을 수 있다. 후보4개가 함께 틀리거나 잘못된 자세가 매끈하면 길이/시간/후보 검사로 검출하지 못한다. 실제0/6/12표본은 표시되지 않았고, 이 결과로 정상이라고 판정하지 않는다. 빠른 실제 회전은 시간 잔차를 키워 검토 표시를 많이 낼 수 있다.149/151표시 프레임과63요청을 오류 정답/개선률로 쓰지 않는다. 다음4번에서 다리·팔 별 새 영상 근거와 주변 프레임 재추정을 결합해야 한다. M2 IN_PROGRESS 유지.
QA-002 / VERIFYING 유지: 이번36파일 분리 및 GUI5는 exit0이나 이전 통합 프로세스 종료 오류의 원인을 고친 것은 아니다. 신규 QA 실패나 새 GPU 오류는 없었다.
'''
project='''5단계의3번 관절 궤적·검사를 추가했다. SAM2 사람 추적과 SAM3D 전신 추정은 고정하고 선택된 전신 모델 관절을 구간별로 검사한다. 출력물 joint-review.json/영상 및 부위별 joint-repair-requests.json은 진단 자료이며 native MHR/Skeleton/관절 좌표를 바꾸지 않는다. 미리보기 ‘관절 검사’를 새 출력·기존 결과 양쪽에서 제공한다.
사람 마스크의 영상 근거·모델 후보 합의·시간/기하 기준은 각기 한계가 있다. 미표시 관절은 model_estimate_unverified이고 화면 안 또는 마스크 안이라는 이유로 가시성/관절 정확도를 확정하지 않는다. repair 요청에는 동일 구간 내 문맥과 이유·목표 부위를 넣고 torso는 별도 기준 검토 요청으로 구분한다. 이 요청을 실제 부위 재추정에 사용하는4번과 재관측 연결5번은 후속 작업이다. 기존 자동 다리 재추정은 별개로 유지한다.
검증 범위:414고유 테스트/권한1SKIP, 실제 Norma2개 각218프레임 검사·원본 SHA 보존. 새 GPU 추론0, 관절 좌표 교정0. M2 IN_PROGRESS 및 QA-002 VERIFYING 유지.
'''
for name,text in [('CURRENT_TASK.md',current),('PROGRESS.md',progress),('ISSUES.md',issues),('PROJECT.md',project)]:
    p=root/'md'/name;end=f'원본4MD 갱신, case{n} SHA 동일 복사, snapshots/v0.5.14 MVP 저장. 이전 사용자 결과·MVP·HOME ZIP 보존.\n\n'
    p.write_text(title+text+end+'---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8');shutil.copyfile(p,case/name)
    assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((case/name).read_bytes()).digest()
p=root/'README.md';p.write_text(p.read_text(encoding='utf-8').replace('현재 작업 버전은 v0.5.13','현재 작업 버전은 v0.5.14')+'\n관절 검사: SAM 자동 처리의 전신 후보 다음에 관절 궤적·본 길이·좌우·시간·마스크 근거를 검사합니다. 미리보기 ‘관절 검사’의 주황 표시는 의심 신호이며 교정 결과/오류 정답이 아닙니다. 미표시 관절도 미검증 모델 추정입니다.\n',encoding='utf-8')
p=root/'HOME_TRANSFER.md';p.write_text('# 최신 버전 v0.5.14\n\n3번 관절별 궤적·검사와 부위별 재추정 요청 연결. StartPrototype.cmd 재시작 → SAM 출력/결과 열기 → 관절 검사. 다음4번 선택적 주변 프레임 부위 재추정. 최신4MD/case'+str(n)+' 및 v0.5.14 MVP 참조. 이전HOME ZIP 유지.\n\n---\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
verification.update(tests_passed=414,permission_opt_in_skipped=1,gui_separate_processes=5,qa002='VERIFYING',md_archive=case.name)
(evidence/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
exports=evidence/'exports';exports.mkdir(exist_ok=True)
for row in verification['results']:
    source=root/'outputs'/row['folder']/row['selection'];dest=exports/row['folder'];dest.mkdir(exist_ok=True)
    for name in ('joint-review.json','joint-review.mp4','joint-repair-requests.json'):shutil.copyfile(source/name,dest/name)
folder=root/'snapshots/v0.5.14 MVP';folder.mkdir();target=folder/'m2-joint-review-v0.5.14.zip'
extra=[Path(__file__),root/'core/pose3d/joint_review.py',root/'app/joint_review_job.py',root/'tests/test_joint_review.py',root/'validation/joint_review_v0514.py',root/'validation/joint_review_preview_v0514.py',root/'validation/test_split_v0514.py',*case.glob('*.md')]
extra.extend(p for p in evidence.rglob('*') if p.is_file() and not any(part.startswith('test_') for part in p.relative_to(evidence).parts[:-1]))
with zipfile.ZipFile(root/'snapshots/v0.5.13 MVP/m2-fullbody-candidates-v0.5.13.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as out:
    names=set()
    for info in old.infolist():
        name=info.filename
        if '__pycache__' in name or name.endswith('.pyc'):continue
        p=root/name;data=p.read_bytes() if not name.startswith('진행상황/') and p.is_file() else old.read(info)
        out.writestr(name,data);names.add(name)
    for p in extra:
        name=p.relative_to(root).as_posix()
        if name not in names:out.write(p,name);names.add(name)
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    for name in ('app/gui.py','app/automatic_postprocess.py','app/joint_review_job.py','core/pose3d/joint_review.py','tests/test_joint_review.py'):assert z.read(name)==(root/name).read_bytes()
    count=len(z.infolist())
data={'version':'0.5.14','files':count,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'tests_passed':414,'qa002':'VERIFYING','md_archive':case.name,'m2_pass':False}
(folder/'snapshot.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(data))
