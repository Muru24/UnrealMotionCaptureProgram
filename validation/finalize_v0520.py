from pathlib import Path
import json,hashlib,shutil,zipfile,re
root=Path(__file__).resolve().parents[1];e=root/'validation/sam2/mask-prompt-v0520';v=json.loads((e/'verification.json').read_text(encoding='utf-8'));assert v['inputs_unchanged'] and v['inference_count']==33
cases=root/'진행상황';n=max(int(p.name[4:]) for p in cases.iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1;case=cases/f'case{n}';case.mkdir()
title='## 2026-10-20 / v0.5.20 SAM3D 직접 마스크 입력 비교\n\n'
common='''가림 영상 근거 보강을 위해 같은 SAM3D의 native mask conditioning을 비교했다. M2 IN_PROGRESS. 원본픽셀·같은ROI를유지한3변형이며후보선택후감점/보간과다르다. 기존자동제품/원시/앞단계결과는유지하고표본추론만별도저장했다. 새모델/패키지/다운로드없음.\n'''
texts={
'CURRENT_TASK.md':'''Goal/Acceptance: SAM3D masks 입력을 사용해 같은 프레임·ROI의 unconditioned/person-mask/accessory-reduced 가설을 비교한다. 의상제외후신체근거가너무작으면보류,원본픽셀은유지한다. Scope: core/pose2d/mask_prompt.py, app/mask_prompt_job.py, 기존leg_candidate_worker의선택적mask_files/predict_candidate, tests/test_mask_prompt.py.\n사용: Norma결과→mask_prompt_cebeb718/sampled-mask-comparison.mp4(12표본의정지화면비교,연속모션아님). 왼쪽동일ROI마스크없음/가운데사람mask/오른쪽의상축소mask. 전체타임라인person-mask.mp4·accessory-reduced.mp4는표본외관절없음이며추적유실로보지않는다.59/66/68축소prompt는신체잔여20%미만이라보류해오른쪽뼈대가없다. 기존자동미리보기우선순위는유지.\n결론/다음: 직접mask조건으로출력은달라졌으나60/66망토관절오류는남는다. 같은모델의조건변경을정확도개선으로확정하거나기본승격하지않는다. 독립적인영상관절관측/조건이확인된시간모델이필요한범위로남긴다. 모델검토는validation/sam2/mask-prompt-v0520/model-audit.md 참조.\n''',
'PROGRESS.md':'''현재SAM3D estimator process_one_image는masks를받아prepare_batch→mask_score/encoder embedding을전달한다. model_config는MASK_EMBED_TYPE v2/MASK_PROMPT v1. 기존SAM2사람mask는ROI선정에만쓰였고sam3d_worker/leg_candidate_worker는bbox만전달했다. 이번worker에선택적인mask_files를추가하고없는요청은기존호출동일하게유지한다. 새로운helper는RGB변환후같은픽셀/ROI를estimator에전달하고mask있을때만binary[1,H,W]masks를추가한다. path containment/크기/빈mask를검사한다. mask있는향후실행은cfgembedding활성여부를검사하고audit를기록한다.\naccessory-reduced는양의객체존재logit이있는기존cape/hair rawmask를person에서빼는입력가설이다. 실제보이는몸분할정답이아니고가려진정상팔다리를제외할수도있다. 잔여32px/20%이상/98%미만일때만입력한다. 원본RGB는지우지않는다. estimator가provided mask score를1로설정하는것은모델maskembedding조건값이며측정confidence/의미정확도가아니다.\n새mask_prompt_UUID에검증된입력과prompts/request/기존CUDAworkerlog/추론candidates/2비교영상·joints/summary/report·hashes를저장했다. bbox는3변형모두동일,source/raw/tracking/원시의상mask의SHA를종료때확인했다. unsampled프레임은None이며0.5초씩표본정지화면을보여주는sampled-mask-comparison으로구분했다. 새로운33회GPU추론결과가생성됐으며시간모델로바꾼것은아니다.\n시간모델읽기검토: GVHMR공식LICENSE는연구/비영리및상업별도문의라현재선택안함. MotionBERT코드는Apache2.0이나확인한공식HF카드에별도weightslicense메타데이터가없고17관절2D입력에의존한다. code조건만으로모든가중치/의존모델조건을확정하거나상업불가라고단정하지않았고이번에는설치하지않았다. 공식링크/검토범위를model-audit.md에기록했다.\n재현: .venv/Scripts/python.exe -m app.mask_prompt_job [Norma결과] [원본Norma.mp4] [internal_00e79bb5] --frames 55 58 59 60 61 62 64 66 68 70 73 75. 경로는따옴표사용.\n''',
'ISSUES.md':'''M2-MASKPROMPT-001 / VERIFYING: 사람mask를사용하는추적과SAM3D에mask embedding을입력하는것이달랐다. 기존은bbox만입력했으므로마스크진단/후보감점은모델자세생성단계자체를바꾸지않았다. 직접마스크입력실험을추가했으나심한의상오추정은남아있어이누락만이원인이라고결론내리지않는다.\n실제12표본에서personmask12/의상축소9/마스크없는대조12=33회추론.55/60/66/73확인에서망토추정이남음. 제공mask를정답score1로해석하면안되고내부embedding활성값이다.59/66/68은의상제외후신체잔여0.194/0.168/0.193으로20%아래여서축소prompt보류.66표본오른쪽관절없음은추적유실이아닌의도된가설보류다.\n마스크가정확한가려진해부학을알려주는것은아니며단일프레임모델의복장/스타일편향을상쇄하지못한다. 값이달라졌다는것과정확도가좋아졌다는것을구분한다. 자동기본변경없음. QA-002 기존VERIFYING 유지,이번검증exit0.\n''',
'PROJECT.md':'''현재SAM3D의native mask조건후보를표본비교하는명시적실험경로를추가했다. 사람전체mask또는의상축소mask를원본픽셀·동일ROI와함께직접전달한다. 추적박스/후처리감점/시간보간과구분한다. 기존worker의기본호출은변하지않고자동후처리에도연결하지않았다. 결과는새MHR70카메라상대joint sidecar이며원시MHR회전/Skeleton/UE규격변경없음. 독립시간모델은이번에추가하지않았으며상업조건과입력2D오류해결가능성을추가검토해야한다.\n'''}
checks='''실제Norma55/58/59/60/61/62/64/66/68/70/73/75의12표본,새GPU33회(무mask12/사람mask12/의상축소9). 같은ROI확인·원본RGB미수정·모든입력해시불변. 출력2D변경량은후보차이일뿐정확도수치가아니다. 심한60/66의상오류미해결,새기본값채택안함. 증거validation/sam2/mask-prompt-v0520/{verification.json,body-comparison.jpg,model-audit.md}.\n검증47PASS(신규8+부위16+내부mask17+자동5=46,목록GUI1독립),모두exit0;compileallPASS. 신규는정상축소/입력불변,과다삭제·빈/동일mask·크기거부,estimator동일픽셀·ROI/선택적mask전달,3종invalid/stale/cancelGPU차단,파일기반3변형계획·표본외None·목록/원본보존,실패미게시다.\n'''
for name,body in texts.items():
 p=root/'md'/name;p.write_text(title+body+common+checks+f'원본4MD 갱신/case{n} SHA 동일 복사/v0.5.20 MVP 저장. 기존 사용자 결과·MVP·HOME ZIP 보존.\n\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8');shutil.copyfile(p,case/name);assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((case/name).read_bytes()).digest()
p=root/'README.md';p.write_text(p.read_text(encoding='utf-8').replace('현재 작업 버전은 v0.5.19','현재 작업 버전은 v0.5.20')+'\nSAM3D직접mask입력실험: Norma mask_prompt_cebeb718/sampled-mask-comparison.mp4는12표본정지화면의3변형비교입니다. 새GPU33회/같은픽셀·ROI. 심한망토오류는남고기본자동경로에는미적용입니다.\n',encoding='utf-8')
p=root/'HOME_TRANSFER.md';p.write_text('# 최신 v0.5.20 / SAM3D 직접mask조건비교\n\n기존ROI만입력과native mask조건의차이를확인.12표본33새GPU추론,심한망토오류미해결/자동미적용. 최신4MD/case'+str(n)+' 및 mask-prompt-v0520 참조. 시간모델은조건검토만하고추가하지않음.\n\n---\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
v['md_archive']=case.name;(e/'verification.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8');shutil.copytree(root/v['directory'],e/'export')
folder=root/'snapshots/v0.5.20 MVP';folder.mkdir();target=folder/'m2-mask-conditioned-comparison-v0.5.20.zip'
extra=[root/'core/pose2d/mask_prompt.py',root/'app/mask_prompt_job.py',root/'tests/test_mask_prompt.py',Path(__file__),*case.glob('*.md'),*[p for p in e.rglob('*') if p.is_file()]]
with zipfile.ZipFile(root/'snapshots/v0.5.19 MVP/m2-temporal-hypotheses-v0.5.19.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as out:
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
 for name in ('app/gui.py','app/automatic_postprocess.py','app/leg_candidate_worker.py','app/mask_prompt_job.py','core/pose2d/mask_prompt.py','tests/test_mask_prompt.py'):assert z.read(name)==(root/name).read_bytes()
 count=len(z.infolist())
meta={'version':'0.5.20','files':count,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'md_archive':case.name,'m2_pass':False,'automatic_mask_conditioning':False}
(folder/'snapshot.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(meta))
