from pathlib import Path
import json,hashlib,shutil,zipfile,re
root=Path(__file__).resolve().parents[1];e=root/'validation/sam2/temporal-v0519';v=json.loads((e/'verification.json').read_text(encoding='utf-8'));assert v['inputs_unchanged']
cases=root/'진행상황';n=max(int(p.name[4:]) for p in cases.iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1;case=cases/f'case{n}';case.mkdir()
title='## 2026-10-20 / v0.5.19 양방향 가림 자세 후보 비교\n\n'
common='''앞뒤 기준 프레임을 이용한 팔다리 후보와 몸통 기준 보강 후보를 분리 구현·비교했다. M2 IN_PROGRESS. 모델 미검토 프레임은 실제 보이는 정상 관절로 확정된 것이 아니며 새 결과는 unobserved_temporal_hypothesis_not_measurement다. SAM3D새추론/새모델/패키지 없음. 기존 자동 제품 및 입력 데이터는 유지한다.\n'''
texts={
'CURRENT_TASK.md':'''Goal/Acceptance: 같은 대상/segment/scene/pose track의 앞뒤 미검토 자세에서 몸통 상대 팔다리 방향을 구면 보간해 새 후보를 생성한다. 팔다리 전용/몸통 기준 보강 비교를 분리하고 원시/기존 결과 불변, 근거 부족·긴 구간·큰 위치 충돌은 보류한다. Scope: core/pose3d/temporal_hypotheses.py, app/temporal_hypothesis_job.py, 공유render의몸통표시, tests/test_temporal_hypotheses.py.\n사용: Norma 결과 목록 → temporal_a121622e/limbs-hypothesis.mp4 또는 body-context-hypothesis.mp4. 왼쪽 기존v0.5.18의상감점결과/오른쪽 새 시간 후보. 주황은 새A/B차이,측정된 실제 관절 아님. 45~90프레임만 후보 생성, 원본218프레임 비교영상이다. 기본 자동 미리보기는 유지.\n현재 결론: 짧은 왼팔 후보는 생성되지만2초대 심한 다리 오류는 해결 못 했다. 다리 앞뒤 기준 간격이 너무 길고 모델 몸통 기준도 불확실하다. 다음은 해당 가림 구간에서 영상 근거가 있는 신체 부착점/발 관측을 확보하거나 시간 기반 모델의 별도 후보를 검토해야 하며, 긴 보간을 정답처럼 쓰지 않는다.\n''',
'PROGRESS.md':'''body_basis로 기준 자세를 몸통 좌표계에 옮기고 양끝 본 방향을 SLERP/길이는 선형 보간한다. 좌우 라벨을 바꾸지 않고 root를 고정한다. 손/발·팔꿈치 보조점은 기준의 wrist/ankle/elbow 상대 오프셋을 전달한다. 몸통 보강 후보는 hipcenter는 현재값을 유지하고 미검토 torso 앞뒤 basis의 SO(3)최단회전/Rodrigues와 local torso형상을 보간한다. 이는 native MHR quaternion/본회전 출력이 아니라 camera-relative joint 후보이며 온전한 한 바퀴 회전 경로의 모호성이 남는다. 몸통 변경시 자식/머리도 부착점 이동을 따른다.\n처음 최대2.5초 기준 간격을 허용한 실험 temporal_fc7340bc는 두 변형 모두46프레임을 변경했으나55/60/66표본에서 발이 실제 신체에서 멀어지고 몸통이 머리카락 쪽으로 이동했다. long-gap-rejected.jpg로 실패 근거를 보존하고 이 가설은 채택하지 않았다. 최대기준간격0.6초,몸통이동0.25torso,팔다리영상이동max20px/사람bbox대각선0.12를 적용했다. 길이비0.65~1.55/반대방향모호성/화면밖/카메라부정합/다른대상·장면·누락 경계도 거부한다. 몸통 대수정은 제한하며 body기준이 틀린 채로 남을 수 있다.\n최종은 temporal_a121622e에 비교2영상/2JSON/report·input hashes. 앞 단계변경 provenance가 주황색으로 재표시되는 문제는 새A/B좌표차이만 표시하도록 수정했고 회귀시험을 추가했다. 중간실험도 삭제하지 않았다. 후보0.6초 제약을 통과했다는 것은 관절 정확도 합격이 아니다. 자동 결과나 새로운 실측으로 승격하지 않는다.\n재현: .venv/Scripts/python.exe -m app.temporal_hypothesis_job [Norma결과폴더] [원본영상] [candidates_dff1f4ec] [region_compare_c172b82b] --start45 --stop91 (실행시옵션과값사이공백,각경로따옴표). CLI명령은 --start 45 --stop 91이다.\n''',
'ISSUES.md':'''M2-TEMPORAL-001 / VERIFYING: 단순양끝보간으로긴회전/발차기구간을복원할수없음. 최초2.5초실험에서실제발과큰괴리/몸통이동을확인했다. 앞뒤모델미검토값이실측정답이아니고중간동작을복원할근거가부족한것이원인이다. 기준간격0.6초와영상·몸통이동제약으로근거약한가설을보류하도록수정했다. 실패사진·실험출력은보존. 수정은오류가설차단이지Norma다리복원해결이아니다.\n최종양변형모두15프레임변경.팔다리가설16부위프레임=왼팔15/오른다리1,몸통보강은추가torso1프레임만. 왼다리2초대는긴기준간격으로보류.66프레임은최종A/B좌표변경없음. review되지않은기준도옷오추정일수있고몸통basis가틀리면방향전달도틀린다. 관측이필요한문제를보간강도로숨기지않는다.\nQA-002 기존VERIFYING 유지,이번검증프로세스exit0. 최초테스트1건은동일tmp에fixture를두번생성해FileExistsError였고입력복사재사용으로시험구성수정후통과(제품파일오류아님).\n''',
'PROJECT.md':'''가림 복원의 새 후보를 만들기 위한 양방향 시간 후보 생성기를 실험 경로로 추가했다. 팔다리 방향/길이 보간과 제한적인 몸통 reference 보강의2변형이며 관측을 새로 얻는 모델이 아니다. MHR70 camera-relative joint sidecar만 저장하고 native MHR회전/Skeleton/UE 규격은 바꾸지 않는다. 기존 자동 파이프라인은 그대로다. 긴가림/회전의다리복원은실패한범위로명시하고0.6초이내의근거제약후보만비교한다. 다음은더나은영상신체·발관측또는별도시간모델후보검토가필요하다.\n'''}
checks='''실제Norma218프레임/후보구간45~90: 두변형모두45/46/51~55/59~64/68/69의15프레임변경. limb16가설(왼팔15/오른다리1), body-context17가설(위16+torso1). limb에서151요청은기준부족/긴간격,5요청은영상이동충돌로보류; body-context는body이동17요청보류. source/raw/선택/전신/검사/의상감점baselineSHA불변,새GPU추론0. 정확도개선미확정,심한다리문제미해결.\n검증57PASS(신규13+부위16+영역8+재관측14+자동5=56/GUI목록1독립),모두exit0,compileallPASS. 신규는요청부위/몸통고정·입력불변,4종경계,누락/장기간격거부,구면방향·SO3/반대방향,취소/순서,무요청분리출력·stale거부,큰영상/몸통이동거부,취소미게시,기존provenance오색표시방지를포함한다. 증거validation/sam2/temporal-v0519.\n'''
for name,body in texts.items():
 p=root/'md'/name;p.write_text(title+body+common+checks+f'원본4MD 갱신/case{n} SHA 동일 복사/v0.5.19 MVP 저장. 기존 사용자 결과·MVP·HOME ZIP 보존.\n\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8');shutil.copyfile(p,case/name);assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((case/name).read_bytes()).digest()
p=root/'README.md';p.write_text(p.read_text(encoding='utf-8').replace('현재 작업 버전은 v0.5.18','현재 작업 버전은 v0.5.19')+'\n양방향 시간 가설: Norma temporal_a121622e의 limbs-hypothesis.mp4와 body-context-hypothesis.mp4. 왼쪽 기존/오른쪽 미관측가설. 긴기준간격의다리는보류하며2초대망토문제해결본이아닙니다. 자동기본값유지.\n',encoding='utf-8')
p=root/'HOME_TRANSFER.md';p.write_text('# 최신 v0.5.19 / 양방향 시간 후보 비교\n\n긴2.5초보간은영상상실패→0.6초/몸통·영상이동제약으로보류. 왼팔중심15프레임가설/다리핵심오류미해결,자동미적용. 최신4MD/case'+str(n)+' 및 temporal-v0519 참조.\n\n---\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
v['md_archive']=case.name;(e/'verification.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8');shutil.copytree(root/v['directory'],e/'export')
folder=root/'snapshots/v0.5.19 MVP';folder.mkdir();target=folder/'m2-temporal-hypotheses-v0.5.19.zip'
extra=[root/'core/pose3d/temporal_hypotheses.py',root/'app/temporal_hypothesis_job.py',root/'tests/test_temporal_hypotheses.py',Path(__file__),*case.glob('*.md'),*[p for p in e.rglob('*') if p.is_file()]]
with zipfile.ZipFile(root/'snapshots/v0.5.18 MVP/m2-accessory-cost-comparison-v0.5.18.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as out:
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
 for name in ('app/gui.py','app/automatic_postprocess.py','app/temporal_hypothesis_job.py','core/pose3d/temporal_hypotheses.py','app/part_reestimate_job.py','tests/test_temporal_hypotheses.py'):assert z.read(name)==(root/name).read_bytes()
 count=len(z.infolist())
meta={'version':'0.5.19','files':count,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'md_archive':case.name,'m2_pass':False,'automatic_temporal_fill':False}
(folder/'snapshot.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(meta))
