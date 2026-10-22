from pathlib import Path
import json,hashlib,shutil,zipfile,re
root=Path(__file__).resolve().parents[1];e=root/'validation/sam2/region-v0518';v=json.loads((e/'verification.json').read_text(encoding='utf-8'));assert v['input_hashes_unchanged'] and v['baseline_recomputed_exactly']
cases=root/'진행상황';n=max(int(p.name[4:]) for p in cases.iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1;case=cases/f'case{n}';case.mkdir()
title='## 2026-10-20 / v0.5.18 내부 마스크 일관성·후보 감점 비교\n\n'
common='''사용자 승인에 따라 사람 밖 내부 영역의 제한적 보존과 후보 soft cost 비교를 구현했다. M2 IN_PROGRESS. 망토/머리카락은 기존 작업자seed SAM2 결과를 재사용하며 자동 semantic 인식이 아니다. 기존 사람 추적/마스크/관절/회전/자동 결과는 바꾸지 않았다. 이번은 명시적 실험 CLI/별도 결과다.\n'''
texts={
'CURRENT_TASK.md':'''Goal/Acceptance: 부모 사람 mask에서 잘린 머리카락을 무조건 버리지 않고 붙어 있는 연결 성분만 제한 보존한다. 시계열 확인·가림/불일치 감량 후 의상 겹침을 후보의 낮은 가중치 감점으로 비교한다. hard exclusion 없음, 원본/기존 부위 결과 불변. Scope: core/pose2d/region_evidence.py, core/pose3d/part_reestimation.py 선택적 region_cost, app/region_compare_job.py, tests/test_region_evidence.py.\n사용: 프로그램 결과 패널에서 Norma_sam3d_20261019_165800_c118ce5d 선택 → region_compare_c172b82b/region-candidate-overlay.mp4. 왼쪽 기존 부위재추정/오른쪽 의상 감점 실험. 주황은 실제 A/B 좌표가 달라진 부위만 표시한다. 기존 재관측 연결/부위 비교/의상 진단 유지. 자동 마지막 미리보기와 기존 다른 영상에는 적용하지 않았다.\n다음: 심한2초대/66프레임의 전신 후보·고정 몸통 자체가 망토에 붙는 문제는 남는다. 후보 감점만 늘리지 말고 잘 보이는 앞뒤 기준 프레임의 신체 부착점/움직임을 이용해 새로운 가림 자세 후보를 생성·비교하는 방향이 필요하다.\n''',
'PROGRESS.md':'''reconcile은 raw 영역의 연결 성분이 현재 person과10%이상 겹치고16px이상/사람면적1.5배이하인 경우 유지한다. 사람 밖 픽셀도 유지하지만 person tracking이나 pose ROI를 합치지는 않는다. 유지 mask와 전프레임의 면적비0.25~4/IoU0.05로 시간 확인하며 첫 프레임/누락/급변은 weight0. 기본weight0.5, 부모와20%이상 불일치면0.5배, person65%이상 가리면0.3배다. 가림이 실제일 수 있으므로 이를 관절 오류 확정으로 보지 않는다. 부모와 완전히 떨어진 머리카락은 여전히 보류한다.\nsoft_cost는 중간/끝 joint의 영역 가중치를 평균하고0.2배(최대0.1)만 후보 unary에 더한다. 여러 영역이 겹쳐도 max로 중복감점하지 않는다. 기존 mask_support의 hard gate에 의상 점수를 합치지 않아 겹침만으로 후보를 거부하지 않는다. region_cost기본0이라 기존 제품 출력은 동일하다. 입력비용은 finite0~0.2 검증.\nrun_compare는 기존 plan/fresh212추론결과/전신4후보를 CPU 재결합해 저장된 부위 baseline과 모든 행이 정확히 같은지 먼저 검사한다. 그 후 감점만 추가해 같은 기하/몸통고정/시간경로 제약으로 비교한다. source/raw/selected/fullbody/review/part 및 새mask파일/부모mask/tracking SHA를 검증하고 처리 중 변경 시 실패. 다른result·scene·유실·잘못된 timeline을 거부한다. region_compare_UUID에 joints/region-evidence/input hashes/report/전218프레임 비교영상을 저장한다. 새GPU추론0. 첫 비교의 표시가 기존 부위교체 provenance까지 주황으로 칠하는 문제를 발견해 A/B의 실제 다른 joint 부위만 칠하도록 수정한 최종 비교를 별도로 저장했다. 이전 실험도 보존했다.\n재현: .venv/Scripts/python.exe -m app.region_compare_job [Norma결과폴더] [원본영상] [candidates_dff1f4ec폴더] [parts_99f676a1폴더] [internal_00e79bb5폴더]. 각 경로 따옴표 사용. 신규 모델/패키지 없음.\n''',
'ISSUES.md':'''M2-INTERNAL-002 / VERIFYING: strict person교집합은 hair를 잘랐고 넓은 cape를 오류로만 간주할 위험이 있었다. person에 붙어 있는 연결 성분은 밖 픽셀도 보존하고 불일치·넓은 가림은 낮은 weight로 처리하는 실험 경로를 추가했다. 이 보존은 personmask를 수정하거나 의상 의미 정확도를 보장하지 않는다. hair가 부모에 완전히 안 붙거나 객체 존재/시간 근거가 없으면 여전히 쓰지 않는다.\n결과: 후보감점으로7프레임 선택 변경은 발생했지만60/66의 망토 관절 문제는 남는다. 특히66은 A/B 좌표 동일이다. 보이는 위치가 달라졌다는 사실과 해부학적 정확도 개선은 다르다.59/60/73표본을 시각 확인했으며 현재 점수 변경만으로 해결했다고 보지 않고 자동 기본값으로 승격하지 않았다. 고정 어깨·골반 자체의 오추정과 후보 전부의 공통 오류가 있는 구간은 새로운 몸통/가림 후보 근거가 필요하다. QA-002 기존VERIFYING 유지, 이번 프로세스는 모두exit0.\n''',
'PROJECT.md':'''내부 영역 일관성 보강 및 후보 감점 실험을 추가했다. 사람 밖에 있는, 사람과 연결된 hair/cape 픽셀을 제한 보존하며 불일치/가림은 낮은 가중치로 반영한다. 기존 사람 tracking 및 자동 후보·관절 결과에는 적용하지 않는다. 사용자seed 의상 분리의 진단→부모 불일치 보강→soft penalty 비교까지 진행했다. 다음은 의상에 붙은 후보밖에 없는 구간에서 가림 자세/몸통 기준의 후보 생성 개선이다. 최종 UE애니메이션/회전 보정 단계가 아니며 camera-relative MHR70 sidecar다.\n'''}
checks='''실제Norma218프레임 CPU 비교(의상 근거45~90): baseline 저장본과 정확히 동일 재현 후 감점만 추가,58/59/60/72/73/76/77의7프레임 변경. 실험 구간 밖 변경0. 의상 weight활성 cape45/hair16프레임, person밖 픽셀 보존 cape37/hair18프레임(의미 정확도나 개선률 아님). 모든 입력 해시 보존/새GPU추론0. validation/sam2/region-v0518/verification.json 및 body-comparison.jpg 참조.\n검증61PASS(신규8+부위16+내부마스크17+재관측14=55,자동5,목록GUI1 독립), 모두exit0; compileall PASS. 신규 검사는 외부 붙은 hair 보존/시간확인,배경분리,넓은 cape감량,존재·시간누락 무감점,중복 비용상한/화면밖,잘못된 크기·NaN,기본0 비용 호환,무요청파일기반비교·목록·stale거부다.\n'''
for name,body in texts.items():
 p=root/'md'/name;p.write_text(title+body+common+checks+f'원본4MD 갱신/case{n} SHA 동일 복사/v0.5.18 MVP 저장. 기존 사용자 결과·MVP·HOME ZIP 보존.\n\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8');shutil.copyfile(p,case/name);assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((case/name).read_bytes()).digest()
p=root/'README.md';p.write_text(p.read_text(encoding='utf-8').replace('현재 작업 버전은 v0.5.17','현재 작업 버전은 v0.5.18')+'\n의상 후보 감점 비교: Norma의 region_compare_c172b82b/region-candidate-overlay.mp4. 왼쪽 기존 부위 추정/오른쪽 제한적 의상 점수 비교.7프레임 선택은 달라졌으나 심한2초대 망토 문제는 남아 자동 적용하지 않았습니다.\n',encoding='utf-8')
p=root/'HOME_TRANSFER.md';p.write_text('# 최신 v0.5.18 / 내부 영역 보강·후보 감점 비교\n\nNorma 기존SAM2영역/기존212부위추론 재사용 CPU 비교.7프레임 변경,2초대 심한 공통 오류는 미해결/자동미적용. 최신4MD/case'+str(n)+' 및 region-v0518 참조. 다음은 새로운 가림/몸통 자세 후보 생성 근거 개선.\n\n---\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
v['md_archive']=case.name;(e/'verification.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8');shutil.copytree(root/v['directory'],e/'export')
folder=root/'snapshots/v0.5.18 MVP';folder.mkdir();target=folder/'m2-accessory-cost-comparison-v0.5.18.zip'
extra=[root/'core/pose2d/region_evidence.py',root/'app/region_compare_job.py',root/'tests/test_region_evidence.py',Path(__file__),*case.glob('*.md'),*[p for p in e.rglob('*') if p.is_file()]]
with zipfile.ZipFile(root/'snapshots/v0.5.17 MVP/m2-internal-mask-diagnostic-v0.5.17.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as out:
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
 for name in ('app/gui.py','app/automatic_postprocess.py','app/region_compare_job.py','core/pose2d/region_evidence.py','core/pose3d/part_reestimation.py','tests/test_region_evidence.py'):assert z.read(name)==(root/name).read_bytes()
 count=len(z.infolist())
meta={'version':'0.5.18','files':count,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'md_archive':case.name,'m2_pass':False,'automatic_accessory_cost':False}
(folder/'snapshot.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(meta))
