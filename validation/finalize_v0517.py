from pathlib import Path
import json,hashlib,shutil,zipfile,re
root=Path(__file__).resolve().parents[1];e=root/'validation/sam2/cloth-v0517';v=json.loads((e/'verification.json').read_text(encoding='utf-8'));assert v['upstream_inputs_unchanged'] and v['frames']==46 and v['tests_passed_this_change']==34
cases=root/'진행상황';n=max(int(p.name[4:]) for p in cases.iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1;case=cases/f'case{n}';case.mkdir()
title='## 2026-10-20 / v0.5.17 내부 의상 마스크 1단계 진단\n\n'
common='''사용자 승인 순서의1단계(사람 내부 망토·머리카락 별도 마스크 가능성 확인)를 구현·실제 검증했다. M2 IN_PROGRESS. 기존 SAM2 사람추적 및 5단계 관절 처리의 기본 알고리즘은 유지한다. SAM2는 의미 이름으로 의상을 자동 찾는 모델이 아니므로 이번 Norma 실험은 작업자가 영상60프레임에서 확인한 양성/음성 포인트를 seed로 준 것이다. 사용자 수동 앵커 UI를 복구하거나 모든 영상의 자동 의상 분리를 구현한 것으로 보지 않는다. 새 모델/패키지/다운로드 없음.\n'''
texts={
'CURRENT_TASK.md':'''Goal/Acceptance: Norma2초대에서 사람 마스크와 별도로 cape/hair를 추적하고 사람 내부 clip/크기/이탈/존재·면적 급변을 검사한다. 관절이 겹치는 곳은 review_only로 기록하고 실제 관절 오류/가시성 정답으로 확정하지 않는다. 원시 및 모든 기존 관절 결과를 보존한다. Scope: core/pose2d/internal_mask.py, app/internal_mask_job.py/internal_mask_worker.py, tests/test_internal_mask.py, validation/sam2/cloth-v0517.\n사용: 프로그램 결과 패널에서 Norma_sam3d_20261019_165800_c118ce5d 선택 → 내부 internal_00e79bb5/internal-mask-overlay.mp4. 45~90프레임(약1.51~3.02초), 왼쪽 원본/오른쪽 보라 망토·노랑 머리카락+관절 겹침 표시. 주황은 겹침 검사이고 초록도 정상 확정이 아니다. 기존 재관측 연결 미리보기 기본 순위는 유지. 이번 진단은 자동 SAM출력 단계에 연결하지 않았다.\n다음: 부모 사람마스크가 머리카락을 누락하는 경우의 합성/보류 기준과 망토의 실제 몸 가림을 구분한 뒤, 내부 영역을 후보 감점의 보조 근거로 시험한다. 겹친 관절 강제 삭제나 3D좌표 교체는 아직 금지.\n''',
'PROGRESS.md':'''기존 SAM2 Small 가중치를 쓰는 격리 child internal_mask_worker를 추가했다. 영상45~90/seed60에서 cape/hair2객체를 정·역방향 추적해46프레임×2객체=92개 raw mask를 저장했다. 92는 저장 객체프레임 수이며 SAM2 내부 신경망 호출 수가 아니다. CPU parent는 기존 사람 마스크와 교집합을 만들고 누출20%/사람면적65%/작은 영역16px/면적비0.25~4/객체 존재 logit을 검사한다. logit은 의미 정확도/관절 confidence가 아니다. 모든 inside/info는 semantic_label_verified=False/use_for_pose_exclusion=False다. 통과 상태도 prompted_region_unverified이며 실패 mask를 정확한 의상으로 쓰지 않는다.\n입력 interval/양성 point/대상·scene·tracking segment/ROI를 검사하고 한 구간 최대180프레임/최대4객체만 허용한다. 경로·영상·mask 크기·순서·객체 ID를 검증한다. 출력은 새 internal_UUID, request/regions/raw·clipped masks/internal-mask-review.json/비교영상/report다. source/raw/tracking/person mask manifest와 종료 시 해시를 확인한다. 실패/취소시 완성 미리보기는 게시하지 않고 source/기존 joints를 바꾸지 않는다. 이번 단계는 캐시·자동 적용이 없는 명시적 진단 CLI다. 기존 결과 목록의3단계 mp4 탐색으로 볼 수 있어 새 수동 GUI는 없다.\n재현: .venv/Scripts/python.exe -m app.internal_mask_job outputs/Norma_sam3d_20261019_165800_c118ce5d 원본Norma경로 validation/sam2/cloth-v0517/prompts.json. 파일 경로는 PowerShell에서 따옴표로 감싼다. 새 GPU 실험이므로 기존 raw 추론을 다시 돌리지 않는다.\n''',
'ISSUES.md':'''M2-INTERNAL-001 / VERIFYING: 사람 전체 mask 안에 있는 망토 관절이 기존 근거 검사에서 통과한다. 별도 prompted cape/hair 마스크로 겹침을 진단했다.60프레임에서 어깨/팔꿈치/골반/무릎/발목 모델 관절이 cape와 겹친다는 근거를 얻었으나 가려진 실제 관절도 겹칠 수 있어 이를 오류 확정/삭제로 처리하지 않았다.\n실제 발견: hair raw mask의66/75프레임은 눈에 보이는 머리카락을 포함하지만 기존 사람 마스크는 머리카락의 상당 부분을 제외한다(hair-parent-review.jpg). 따라서 사람 교집합만 고집하면 유효 머리카락 단서까지 사라진다. 머리카락 검토30프레임은 내부 추적 실패만을 뜻하지 않고 부모 mask 불일치가 섞여 있다. cape66프레임은 실제 몸 대부분을 가리는 형태로 person65% 제약에 걸려 review다. 넓은 mask가 항상 오분할이라는 뜻은 아니다. 현 상태로 강제 제외를 적용하면 가려진 정상 팔다리/몸까지 버릴 수 있어 자동 후보 감점·관절 교체 연결을 보류했다.\n다음은 부모/내부 영역 일관성 및 가림 상태를 보강하고 soft penalty 비교. SAM2 포인트 초기화의 일반 영상 자동화는 미구현. M2미통과/QA-002 기존VERIFYING 유지.\n''',
'PROJECT.md':'''사람 내부의 의상/머리카락 보조 마스크를 별도 진단 경로로 추가했다. 기존 제품 자동 경로(SAM2사람→SAM3D전신→검사→부위재추정→재관측연결)에는 아직 편입하지 않았다. Norma 한 구간의 작업자 seed 실험이며 자동 semantic parsing이 아니다. 원본 영상의 색/픽셀을 제거하지 않고 model joint/본/native회전/Skeleton도 바꾸지 않는다. 후보 검사에 사용할 근거가 되는지 먼저 확인한다.\n단계: ①별도 영역 추적·품질 진단(이번) → ②부모mask/내부mask 불일치·가림 보강 → ③후보 감점 비교 → ④가려진 팔다리의 앞뒤 문맥 재추정 비교. 겹침만으로 팔다리 삭제/정상 확정하지 않는다.\n'''}
checks='''실제Norma46프레임: cape37프레임 기본검사통과(정확도 아님)/9검토, hair16통과/30검토,35프레임 관절 겹침 검토. 사람영역 과다9, hair 밖누출30/작음10/면적급변9는 중복 가능. source/raw/selected/fullbody/review/part SHA는 기존v0.5.16 완료본과 동일. 새SAM2 영역 추적만 수행/새SAM3D추론0. body-crops/overview/hair-parent-review를 시각 확인했다. 옷 관절 오류 해결 또는 정확도 개선은 주장하지 않는다.\n검증34PASS(신규17+관련기존16+GUI목록1 독립), 모두exit0; compileall PASS. 새 테스트는 prompt조건/경계, clip와미수정원칙,영역크기·존재·급변,겹침review,경로·크기,scene/누락/취소/범위GPU차단,실패결과미게시,실제파일기반진단·목록연결 포함.\n'''
for name,body in texts.items():
 p=root/'md'/name;p.write_text(title+body+common+checks+f'원본4MD 갱신/case{n} SHA 동일 복사/v0.5.17 MVP 저장. 기존 사용자 결과·MVP·HOME ZIP 보존.\n\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8');shutil.copyfile(p,case/name);assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((case/name).read_bytes()).digest()
p=root/'README.md';p.write_text(p.read_text(encoding='utf-8').replace('현재 작업 버전은 v0.5.16','현재 작업 버전은 v0.5.17')+'\n내부 의상 마스크1단계: Norma의 internal_00e79bb5/internal-mask-overlay.mp4에서 prompted 망토·머리카락과 모델 관절의 겹침을 봅니다. 작업자 seed 기반 진단이며 자동 의상분류/관절 보정에는 미연결입니다. 기존 사람 mask가 머리카락을 놓치는 문제도 확인되어 후보 제외 전에 영역 일관성 보강이 필요합니다.\n',encoding='utf-8')
p=root/'HOME_TRANSFER.md';p.write_text('# 최신 v0.5.17 / 내부 의상 마스크1단계\n\nNorma45~90프레임/seed60에서 망토·머리카락 별도SAM2 추적. 진단만 추가, 기존 자동관절 처리 유지. 최신4MD/case'+str(n)+'와 cloth-v0517 증거 참조. 다음은 부모mask 불일치·가림 보강 후 후보 감점.\n\n---\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
v['md_archive']=case.name;(e/'verification.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
exports=e/'export';shutil.copytree(root/v['directory'],exports)
folder=root/'snapshots/v0.5.17 MVP';folder.mkdir();target=folder/'m2-internal-mask-diagnostic-v0.5.17.zip'
extra=[root/'core/pose2d/internal_mask.py',root/'app/internal_mask_worker.py',root/'app/internal_mask_job.py',root/'tests/test_internal_mask.py',Path(__file__),*case.glob('*.md'),*[p for p in e.rglob('*') if p.is_file()]]
with zipfile.ZipFile(root/'snapshots/v0.5.16 MVP/m2-reconnection-v0.5.16.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as out:
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
 for name in ('app/gui.py','app/automatic_postprocess.py','app/internal_mask_worker.py','app/internal_mask_job.py','core/pose2d/internal_mask.py','tests/test_internal_mask.py'):assert z.read(name)==(root/name).read_bytes()
 count=len(z.infolist())
meta={'version':'0.5.17','files':count,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'md_archive':case.name,'m2_pass':False,'automatic_pose_exclusion':False}
(folder/'snapshot.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(meta))
