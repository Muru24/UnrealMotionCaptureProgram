from pathlib import Path
import json,hashlib,shutil,zipfile,re
root=Path(__file__).resolve().parents[1];evidence=root/'validation/sam2/parts-v0515'
v=json.loads((evidence/'verification.json').read_text(encoding='utf-8'))
assert v['inference_count']==212 and v['body_attachments_unchanged'] and v['inputs_unchanged']
split=json.loads((evidence/'test-split/summary.json').read_text(encoding='utf-8'))
assert len(split)==37 and all(r['exit']==0 for r in split if r['file']!='test_video.py')
assert sum(int(re.search(r'(\d+) passed',r['summary'][0])[1]) for r in split)==424
cases=root/'진행상황';n=max(int(p.name[4:]) for p in cases.iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=cases/f'case{n}';case.mkdir()
title='## 2026-10-20 / v0.5.15 4번 팔·다리 선택 재추정\n\n'
current='''M2 IN_PROGRESS. 5단계 중 4번의 관절 검사 요청 기반 팔·다리 선택 재추정을 구현·연결했다. 다음은 5번 실제 재관측과 추정 구간의 연결이다. 이번 교체는 점수/기하/마스크 제약을 통과한 모델 추정이며 관절 정답 보장이 아니다.
Goal/Acceptance: 검사 요청된 부위·프레임만 새 문맥 crop을 SAM3D 추론하고, 같은 유효 대상/scene/pose track의 주변 프레임과 기존 후보·기존 자세를 비교한다. 몸통/어깨·골반·neck과 요청하지 않은 부위를 고정한다. 부착점·투영·본 길이·마스크 근거가 충돌하면 거부하고 전체 경로 점수가 충분히 나아질 때만 부위를 교체한다. 원시 MHR회전/Skeleton은 바꾸지 않는다. Scope: core/pose3d/part_reestimation.py, app/part_reestimate_job.py, automatic_postprocess/GUI/result_library 및 tests/validation.
사용: StartPrototype.cmd 재시작 → SAM 새 출력 또는 기존 SAM 결과 열기 → ‘부위 재추정 비교’. 왼쪽 선택 전신/오른쪽 부위 교체, 주황은 교체 모델 추정이다. 관절 검사·전신 기준·기존 다리 결과도 비교 가능하다. 원본/선택/검사 해시가 맞는 완료된 parts 결과는 재사용한다. 신규 전체 신발+다리 자동 추론 대신 검사 요청 기반 팔·다리 추론을 실행하며, 과거 완료된 다리 결과는 비교로 남긴다.
실제 Norma218프레임에서 요청128프레임/arm-context+leg-context212회 새 GPU추론.48프레임/64부위프레임 교체(오른팔22/왼팔14/오른다리13/왼다리15). fresh_arm11/fresh_leg13, 나머지40부위프레임은 기존 전신 후보를 부분 결합했다. source/sam3d/selected/fullbody/review SHA 보존 및 몸통 고정 확인.62/70/74표본과 요청 없는0/6/12는 교체 없음. 정확도 개선률은 미검증이며 옷 공통 오추정/잘못된 몸통 기준은 여전히 남을 수 있다.
검증:430고유 PASS/권한 opt-in1 SKIP.37파일 분리424요약 후 보조 팔꿈치1개 추가 검사, GUI5개 독립 PASS. 최종 부위16+자동처리5=21 PASS/exit0. test_video는15PASS요약 뒤0xC0000008 재관측, 단독 재검15PASS/exit0으로 확인했다. QA-002 VERIFYING 유지. compileall PASS. 증거 validation/sam2/parts-v0515/{verification.json,overview.jpg}, 실제 출력 parts_99f676a1.
'''
progress='''review의 repair_requests 중 left/right arm/leg만 계획하며 torso 요청은 자동으로 body를 바꾸지 않는다. 동일 target/scene/tracking_segment/pose_track_start 문맥 안에서 주변 관절을 현재 어깨/골반 중심에 맞춰 ROI를 만든다. 양팔·양다리의 공통 문맥 crop을 family별 공유해 같은 프레임에 최대2회 추론하며 실제 교체는 요청된 쪽에만 허용한다. 관절 추정으로 만든 crop이므로 모델의 공통 의류 오추정 한계가 있다. 별도 시간 신경망은 도입하지 않았다. SAM3D는 각 프레임을 full inference하고 주변 프레임은 crop 구성과 경로 선택 비용에 사용한다.
기존 CUDA ROI worker(leg_candidate_worker.py)를 일반 부위 ROI에 재사용했다. 새 패키지/가중치/모델 변경은 없다. 예상 밖 frame/variant/joint_names는 오류로 중단한다. 모델 child는 기존 취소/숨김 창/로그를 유지한다. GPU 단계 실패 메시지는 다리 전용에서 부위 재추정으로 변경했다.
후보는 새 family crop과 기존 전신 후보다. 고정 어깨/골반 root에 후보 방향을 옮기고 같은 연속 구간의 median 상·하체인 길이를 적용한다. 후보 길이 비0.6~1.6, root 픽셀 오차 및 고정 카메라 투영 오차를 검사한다. 손/발 child는 새 wrist/ankle 상대 오프셋을 보존하고 MHR70 팔꿈치 보조점63/65·64/66도 새 elbow 상대 위치로 이동한다. 어깨 acromion/몸통/반대쪽은 고정한다. 원본 전신과 편집되지 않은 모든 joint의2D/3D 배열이 정확히 같은지 assert한다. 부분별 모델 joint만 내보내며 native body_pose/global_rot는 교체하지 않는다.
마스크 distance 근거가 기존보다 나빠지면 후보를 거부한다. 길이/기존4후보의2D합의/앞뒤 위치 잔차/마스크 비용과 시간 경로 transition을 비교하고 기존 자세를 항상 후보0으로 넣는다. 전체 경로 비용이 교체부위프레임당0.03 이상 줄 때만 선택한 부위를 적용한다. 이는 proxy cost이며 잘못된 매끈한 포즈를 선호할 수도 있다. 마스크 안에 있는 옷 관절을 정상으로 확정하지 않는다. 표시되지 않은 초반 프레임에 새 추론을 억지로 넣지 않았다.
자동 흐름은 후보→전신→관절 검사→part_reestimation으로 바뀌었다. 기존 full shoe+leg 추론은 자동으로 다시 실행하지 않으며 완료된 옛 leg 결과가 있으면 비교 옵션으로 보존한다. 새 parts_UUID에 plan.json/inference/part-joints.json/part-overlay.mp4/report.json을 저장한다. source/raw/selected/review/fullbody SHA 및 revision1으로 재사용한다. 입력·마스크가 처리 중 바뀌면 실패시키고, 실패/취소 결과를 완료 캐시로 사용하지 않는다. 원시 추출과 기존 선택은 보존한다. GUI의 기본 결과는 부위 재추정 비교, 기존 검사/기준축/다리 비교는 유지한다. 결과 패널도 새 part-overlay를 우선 표시한다.
실제 Norma_sam3d_20261019_165800_c118ce5d/candidates_dff1f4ec를 입력으로212회 새 GPU추론을 수행했다.128요청 frame 중 팔·다리 family crop 공유.218전체 frame 출력 중48 frame/64부위frame 교체.새추론24부위frame(fresh_arm11/fresh_leg13),기존후보40(observed7/tight13/stable10/stable-flip10). 손가락·발끝 및 팔꿈치 보조점 정합 추가 후 같은212개 추론을 CPU 재결합했고 GPU를 중복 실행하지 않았다. 새 raw/선택/전신/검사 데이터 SHA 불변, 몸통·미요청 부위 고정 및 요청 구간 안에서만 변경 확인.59는오른팔,60은오른팔/왼다리,61은오른팔/왼다리,65는양다리,66은오른팔/오른다리 변경.62/70/74는 유지됐다. overview로59/60/66의 변경을 확인했으나 의류 문제가 전체 해결됐다고 판정하지 않는다.
신규16검사: 요청된 family/frame만 계획, 새 다리로 spike 교체/몸통·다른부위 보존, mask악화 거부, body부착 불일치 거부, 무요청 보존, scene/segment/target/pose_track4문맥 경계 거부,torso자동교체 차단,무요청GPU 미초기화/캐시,계획된frame/variant만child,stale선택거부,취소미게시,팔교체와양다리/어깨보존,팔꿈치보조점 정합. 최종16+자동5=21 PASS. 기존 GUI5는 새 부위 결과 기본 재생과 옛 다리 비교 보존 확인. 전체37파일424 +추가1 +GUI5 =430 PASS/권한1SKIP. QA-002는 test_video15PASS 후 비정상 native 종료가1회 재현됐고 단독15PASS/exit0 확인. 원인 수정 선언 없이VERIFYING 유지. compileall PASS.
'''
issues='''M2-PART-001 / HANDLED: 기존 자동 다리 재추정은 전체 첫 신발 관측 경로에 묶여 있고 팔·다리 검사 요청/주변 프레임을 선택적으로 쓰지 못했다. 요청 기반 family context crop과 고정 몸통의 부위 후보·시간 경로 선택을 추가했다. 새212회 추론으로48프레임64부위frame 교체가 있었으나 proxy 점수 개선과 관절 정답 개선은 다르다. 몸통 부착점/투영/길이/마스크 충돌은 거부하고 baseline을 보존한다. 원시와 미요청 부위 불변을 검사한다.
검토 중 MHR70 팔꿈치 보조점63/65·64/66이 기본 elbow와 함께 이동해야 함을 확인해 elbow 상대 오프셋도 보존했다. 같은 새 추론을 CPU 재결합했으며 GPU재추론은 없었다. 보조점 정합·팔/다리 보존을 포함해 신규16 및 최종관련21 PASS.
남은 한계: 본문맥도 기존 관절/몸통에 의존하고 SAM3D는 프레임별 모델이다. 후보가 공통으로 옷에 붙는 문제, 잘못된 고정 몸통, 화면 밖/가림의 실제 관측 부족은 남는다.62/70/74와초반무요청 프레임은 교체되지 않았다. 원본관절/기존다리/새부위를 구분해 비교해야 하며 M2 PASS/정확도 개선률로 보지 않는다. 다음5번에서 추정구간과 재관측을 연결한다.
QA-002 / VERIFYING 재관측:37파일 분리 중 test_video15PASS요약 후3221225480(0xC0000008), 단독 재검15PASS/exit0. 다른36파일/GUI5 및 최종관련21은exit0. 원인 미확정이며 테스트 실패를 해결했다고 숨기지 않는다.
'''
project='''5단계의4번 요청 기반 팔·다리 문맥 재추정을 제품에 연결했다. 같은 ROI worker와 SAM3D full 모델을 쓰고 주변 frame으로 공간 crop/시간 경로를 구성한다. 시간 신경망으로 바꾼 것이 아니다. 고정 어깨·골반 아래/이후의 요청 부위만 바꾸며 native MHR회전/Skeleton 규격을 유지한다. 팔의 보조 elbow·손/발 child 정합도 보존한다.
자동 제품 경로: SAM2사람추적→SAM3D후보→전신묶음→관절검사→선택적부위재추정. 기존 전체 신발+다리 자동실행은 새 단계로 대체하고, 기존 leg 데이터/엔진은 비교·CLI용으로 보존한다. 미리보기는 ‘부위 재추정 비교’를 기본으로 연다. 검사/기준축/옛다리 비교 옵션은 남는다. 새 part-joints는 MHR70 joint sidecar이며 final UE animation이 아니다. source/raw/selected/review/fullbody hashes/revision1으로 캐시를 검사한다.
검증430고유PASS/권한1SKIP, 실제Norma218frame/212새GPU추론/48변경frame64부위frame. 정확도 정답은 미검증, M2 IN_PROGRESS/QA-002 VERIFYING 유지. 다음5번 실제 재관측 연결이며 의류 공통오추정과 초반무요청 사각지대가 남는다.
'''
for name,text in [('CURRENT_TASK.md',current),('PROGRESS.md',progress),('ISSUES.md',issues),('PROJECT.md',project)]:
    p=root/'md'/name;end=f'원본4MD 갱신, case{n} SHA 동일 복사, snapshots/v0.5.15 MVP 저장. 이전 사용자 결과·MVP·HOME ZIP 보존.\n\n'
    p.write_text(title+text+end+'---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8');shutil.copyfile(p,case/name)
    assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((case/name).read_bytes()).digest()
p=root/'README.md';p.write_text(p.read_text(encoding='utf-8').replace('현재 작업 버전은 v0.5.14','현재 작업 버전은 v0.5.15')+'\n부위 재추정: 관절 검사 요청된 팔·다리만 주변 frame의 문맥 crop과 시간 경로로 비교합니다. 미리보기 ‘부위 재추정 비교’의 왼쪽은 기존 선택/오른쪽은 부분 교체이며 주황은 모델 추정입니다. 기존 다리 전체 추론은 자동 재실행하지 않고 완료본 비교는 보존합니다.\n',encoding='utf-8')
p=root/'HOME_TRANSFER.md';p.write_text('# 최신 버전 v0.5.15\n\n4번 팔·다리 선택 재추정 연결. StartPrototype.cmd 재시작 → SAM출력/결과열기 → 부위 재추정 비교. 다음5번 재관측 연결. 최신4MD/case'+str(n)+' 및 v0.5.15 MVP 참조. 이전HOME ZIP 유지.\n\n---\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
v.update(tests_passed=430,permission_opt_in_skipped=1,gui_separate_processes=5,qa002='VERIFYING',md_archive=case.name)
(evidence/'verification.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
source=root/'outputs'/v['folder']/v['part_directory'];exports=evidence/'export';exports.mkdir(exist_ok=True)
for name in ('plan.json','part-joints.json','part-overlay.mp4','report.json'):shutil.copyfile(source/name,exports/name)
infer=exports/'inference';infer.mkdir(exist_ok=True)
for p in (source/'inference').iterdir():
    if p.is_file():shutil.copyfile(p,infer/p.name)
folder=root/'snapshots/v0.5.15 MVP';folder.mkdir();target=folder/'m2-part-reestimation-v0.5.15.zip'
extra=[Path(__file__),root/'core/pose3d/part_reestimation.py',root/'app/part_reestimate_job.py',root/'tests/test_part_reestimation.py',root/'validation/parts_v0515.py',root/'validation/parts_preview_v0515.py',root/'validation/test_split_v0515.py',*case.glob('*.md')]
extra.extend(p for p in evidence.rglob('*') if p.is_file() and not any(part.startswith('test_') for part in p.relative_to(evidence).parts[:-1]))
with zipfile.ZipFile(root/'snapshots/v0.5.14 MVP/m2-joint-review-v0.5.14.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as out:
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
    for name in ('app/gui.py','app/automatic_postprocess.py','app/part_reestimate_job.py','core/pose3d/part_reestimation.py','tests/test_part_reestimation.py'):assert z.read(name)==(root/name).read_bytes()
    count=len(z.infolist())
data={'version':'0.5.15','files':count,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'tests_passed':430,'qa002':'VERIFYING','md_archive':case.name,'m2_pass':False}
(folder/'snapshot.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(data))
