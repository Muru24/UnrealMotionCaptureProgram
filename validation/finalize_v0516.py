from pathlib import Path
import json,hashlib,shutil,zipfile,re
root=Path(__file__).resolve().parents[1];evidence=root/'validation/sam2/reconnect-v0516';v=json.loads((evidence/'verification.json').read_text(encoding='utf-8'));assert v['inputs_unchanged']
cases=root/'진행상황';n=max(int(p.name[4:]) for p in cases.iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1;case=cases/f'case{n}';case.mkdir()
title='## 2026-10-20 / v0.5.16 5번 재관측 연결\n\n'
common='''5단계 중5번까지 구현·제품 연결. M2 IN_PROGRESS. 재추정 부위가 끝난 뒤 같은 target/segment/scene/pose track의 2~5연속 프레임을 검사한다. 검사 중인 부위, 누락 몸통, 위치0.45torso 초과, 길이비0.75~1.33 밖, 반대 방향, 화면 밖/마스크 이탈,20px 초과 투영 이동은 거부한다. 통과하면 고정 어깨/골반 아래의 두 본 방향을 정규화 혼합하며 현재 본 길이를 유지하고 마지막 프레임은 관측 모델값으로 정확히 돌아간다. 손/발·팔꿈치 보조점은 현재 wrist/ankle/elbow 상대 오프셋을 보존한다. Euler/native MHR회전은 변경하지 않는다. 사람 전체 누락을 채우거나 다른 장면/대상을 잇지 않는다. 모든 관측도 SAM3D 모델 추정이며 실제 관절 정답/가시성 보장이 아니다.\n'''
texts={
'CURRENT_TASK.md':'''Goal/Acceptance: 부위 추정에서 재관측 모델로 짧은 전환, 연속 검사와 경계 차단, 본 길이/몸통 보존, 원본 및 앞 단계 불변. Scope: core/pose3d/reconnection.py, app/reconnection_job.py, automatic_postprocess/GUI/result_library, tests/test_reconnection.py.\n사용: StartPrototype.cmd 재시작 → 새 SAM출력 또는 기존 SAM 결과 열기 → 기본 ‘재관측 연결 비교’. 왼쪽 부위 재추정/오른쪽 연결 후, 주황은 연결 부위. 부위/관절검사/기준축/기존 다리 비교 유지.\n''',
'PROGRESS.md':'''CPU 후처리 ensure_reconnection을 후보→전신→검사→부위재추정 다음에 추가했다. reconnect_UUID/reconnected-joints.json, reconnection-overlay.mp4, report.json에 판정·거부 이유를 기록한다. source/raw/selection/fullbody/review/part SHA/revision 및 결과 JSON/영상 SHA로 캐시를 확인한다. 처리 중 입력/마스크/tracking이 바뀌면 실패. 취소/실패 결과는 완료 캐시로 사용하지 않고 앞 단계 부위 결과는 보존한다. 시간 방향 정규화 혼합은 bone quaternion 출력이 아니며 이후 native 회전 처리 단계는 별도다.\n''',
'ISSUES.md':'''M2-RECONNECT-001 / HANDLED: 부위 교체가 끝나는 경계에서 곧바로 다른 모델 관측으로 전환하던 문제에 연속 검사·길이 보존 전환을 추가했다. 검사 실패 시 강제 연결하지 않고 기존 부위 출력과 거부 이유를 보존한다. Norma의44경계 중42곳은 관절 검토 지속,1곳은20px 이동 제약으로 거부됐고1곳만 연결됐다. 기준을 낮춰 실패 구간을 숨기지 않았다.\n남은 문제: 옷/망토의 공통 오추정, 검사에서 놓친 초반 프레임, 잘못된 몸통, 긴 가림, 유효 후보 부재는 이번 연결만으로 해결되지 않는다. 다음은 사용자 영상 검토 후 거부된 회전 부위와 초반 공통 오류의 영상 근거/추정 후보 개선이다. QA-002 VERIFYING 유지(이전 native 종료 원인 미확정; 이번 관련 프로세스 정상).\n''',
'PROJECT.md':'''현재 자동 경로: SAM2 사람추적 → SAM3D 전신후보 → 관절별 검사 → 선택적 팔·다리 재추정 → 검사 후 재관측 연결. 마지막 기본 미리보기는 ‘재관측 연결 비교’다. 원시 및 앞 단계 비교를 유지한다. 새 출력은 camera-relative MHR70 joint sidecar이며 Unreal world animation/최종 본 회전 출력이 아니다.\n'''}
evidence_text='''실제 Norma218프레임: 연결 후보44곳,1곳 수락/164~165프레임 전환,42곳 검토 지속/1곳 영상 이동 충돌 거부. 새 GPU추론0. source/sam3d/selected/fullbody/review/part SHA 불변. overview164~165에서 오른다리 전환 표시를 확인했으나 정확도 개선/의류 오류 해결은 판정하지 않았다.\n검증: 이번 관련73 PASS(새 연결14+자동 비GUI5+기존 부위/검사/전신/목록52+GUI2 독립 프로세스), 모두exit0. compileall PASS. 전체 과거 테스트 재실행 수치가 아니다. 신규 검사는 길이/몸통/마지막 관측 복귀,4종 경계,누락,검토 지속/마스크/위치/길이 충돌의 부분 적용 방지,순서/취소,캐시/출처,자동 단계 실패의 앞 결과 보존을 포함한다. 증거 validation/sam2/reconnect-v0516.\n'''
for name,body in texts.items():
 p=root/'md'/name;p.write_text(title+body+common+evidence_text+f'원본4MD 갱신/case{n} SHA 동일 복사/v0.5.16 MVP 저장. 이전 결과·MVP·HOME ZIP 보존.\n\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8');shutil.copyfile(p,case/name);assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((case/name).read_bytes()).digest()
p=root/'README.md';p.write_text(p.read_text(encoding='utf-8').replace('현재 작업 버전은 v0.5.15','현재 작업 버전은 v0.5.16')+'\n재관측 연결: 자동 마지막 단계의 ‘재관측 연결 비교’로 부위 추정에서 연속 검사된 모델 관측으로 짧게 전환합니다. 사람 전체 누락이나 장면 경계는 연결하지 않습니다.\n',encoding='utf-8')
p=root/'HOME_TRANSFER.md';p.write_text('# 최신 v0.5.16 / 5번 재관측 연결까지\n\nStartPrototype.cmd 재시작 → SAM출력/결과열기 → 재관측 연결 비교. 최신4MD/case'+str(n)+' 참조. M2 진행 중, 의류 오추정 미해결.\n\n---\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
v.update(tests_passed_this_change=73,md_archive=case.name,qa002='VERIFYING');(evidence/'verification.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
exports=evidence/'export';exports.mkdir(exist_ok=True)
for p in Path(v['directory']).iterdir():
 if p.is_file():shutil.copyfile(p,exports/p.name)
folder=root/'snapshots/v0.5.16 MVP';folder.mkdir();target=folder/'m2-reconnection-v0.5.16.zip'
extra=[root/'core/pose3d/reconnection.py',root/'app/reconnection_job.py',root/'tests/test_reconnection.py',root/'validation/reconnect_v0516.py',Path(__file__),*case.glob('*.md'),*[p for p in evidence.rglob('*') if p.is_file()]]
with zipfile.ZipFile(root/'snapshots/v0.5.15 MVP/m2-part-reestimation-v0.5.15.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as out:
 names=set()
 for info in old.infolist():
  name=info.filename
  if '__pycache__' in name or name.endswith('.pyc'):continue
  p=root/name;out.writestr(name,p.read_bytes() if not name.startswith('진행상황/') and p.is_file() else old.read(info));names.add(name)
 for p in extra:
  name=p.relative_to(root).as_posix()
  if name not in names:out.write(p,name);names.add(name)
with zipfile.ZipFile(target) as z:
 assert z.testzip() is None
 for name in ('app/gui.py','app/automatic_postprocess.py','app/reconnection_job.py','core/pose3d/reconnection.py'):assert z.read(name)==(root/name).read_bytes()
 count=len(z.infolist())
meta={'version':'0.5.16','files':count,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'md_archive':case.name,'m2_pass':False}
(folder/'snapshot.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(meta))
