"""Freeze the stronger jitter filter with source-preserving Blender evidence."""
from pathlib import Path
import json,hashlib,re,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1];e=ROOT/'validation/m4-jitter'
results=json.loads((e/'results.json').read_text(encoding='utf-8'));comparison=json.loads((e/'comparison.json').read_text());reports={}
for item in results:
    src=Path(item['blend']).parent;dest=e/(item['label']+'-example');dest.mkdir(exist_ok=True)
    provenance=json.loads((src/'report.json').read_text(encoding='utf-8'))
    assert provenance['correction_sha256']==hashlib.sha256((ROOT/'core/motion/correction.py').read_bytes()).hexdigest()
    for name in ('animation.blend','animation.json','corrected-motion.json','report.json'):shutil.copyfile(src/name,dest/name)
    for kind in ('reopen','fractional'):
        report=json.loads((e/f"{item['label']}-{kind}.json").read_text(encoding='utf-8'));assert report['passed'];reports[item['label']+'-'+kind]=report
heading='## 2026-10-21 / MVP4 v0.7.3 잔떨림 보정 강화\n\n'
common=('사용자 v0.7.2 연속성 개선 확인, 잔떨림 추가 보정 요청. M4 회전/움직임 보정만 강화했다. '
 '원시SAM3D/후처리/M3 motion.json·22본·이전애니메이션/MVP 보존, 모델/패키지/GPU추론 변경 없음.\n')
change=('원인/조치: 기존 적응형 필터는 저속3Hz 하한과 각속도 기반 적응 때문에 잔떨림이 남고, '
 '시간상 역방향으로 오가는 잡음도 빠른동작으로 취급할 수 있었다. '
 '저속 하한을1.5Hz로 강화하고 주변0.10초 순이동각/누적이동각의 일관성으로 속도 가중치를 조정한다. '
 '일관된 빠른동작은 최대18Hz 반응을 유지한다. 이웃 두 회전이6도 이내로 비슷하고 중앙만12도 이상 벗어난 '
 '고립된1프레임 회전은 이웃의 최단SLERP 중간값으로 억제. '
 '관절 누락/scene/segment별 유효span 안에서만 적용한다. '
 '접지/충돌/전환 IK의 무릎 굴곡평면은 직전 평면을 현재 다리축에 투영하고 시간간격 기반으로 완만하게 갱신 '
 '(기본0.07초, 큰 방향변화0.025초). 본길이·도달거리·굴곡면 부호 보호는 유지한다.\n')
usage=('사용: 프로그램 재시작→SAM3D 결과 선택→Blender 애니메이션 저장을 다시 실행. '
 '새 motion/animation-<id>/에 저장, 오른쪽3D 보정 미리보기에도 표시. 기존 파일은 자동수정하지 않는다. '
 '확인용 파일 validation/m4-jitter/LongSword-example/animation.blend.\n')
checks=('검증: 고유78 PASS/권한opt-in1 SKIP, compileall PASS. '
 '비GUI27(보정11/animation job6/M3코어10)+기존회귀38+격리실제GUI3+기존GUI10. '
 '신규3: 고립65도 impulse 제거, 의도적인20도/3초 slow turn 비고정 및30/60fps 일관성, '
 '무릎pole 노이즈 감소와 양쪽 본길이 유지. 기존빠른180도회전·발차기/착지·누락/컷·취소·원본보존 회귀 통과. '
 'LongSword445/합성80프레임 새 .blend 저장·재오픈 및 fractional 보간 검사 PASS: '
 '실제 최대head오차1.485e-6m/접지 프레임이동1.214e-6m, 접지프록시 밑면 최소Z약0.002m. '
 'LongSword29304/합성4950개의 서브프레임 Quaternion 평가와 합성 경계44개 hold 확인. '
 'v0.7.2 대비 상완시작점 상대 손목 위치2차차분 평균 좌0.032644→0.024776m(24.1%), '
 '우0.040305→0.029182m(27.6%) 감소. 허벅지시작점 상대 무릎은 좌32.6%/우11.7% 감소. '
 '최대발목 프레임이동 좌0.2150/우0.2199m로 기존 전환점프 회귀<0.3m 유지. 원본motion 불변. '
 '이 지표는 시간적 흔들림 대용이며 영상 정답 정확도나 모든 떨림 해결의 증거가 아니다.\n')
limits=('남은 한계: 실제 빠른 단발 동작이 고립잡음과 비슷하면 약해질 수 있고 필터로 작은 동작도 감쇠될 수 있다. '
 '원시 지속오추정/Norma 의상·긴누락·정답접지/월드이동·전관절 해부학적 제약은 해결하지 않는다. '
 '전체 사용자 영상/5분 bake 자원부하/엔진임포트는 이번 검증 대상 아님. '
 '연속재생·접지 기반 추정과 누락/컷 보호는 유지, 사용자 v0.7.3 시각확인 대기.\n')
current=heading+'Milestone M4 잔떨림 보정 강화 / 구현·자동검증 완료, 사용자 확인 대기.\n'
current+=('Goal/Acceptance: 대기잔떨림·고립스파이크·IK 무릎흔들림 감소, 빠른/느린 의도동작과 접지/연속성/누락경계 보존. '
 'Scope: core/motion/correction.py, app/gui.py 버전, tests/test_motion_correction.py, validation/run_m4_jitter.py와 관련MD.\n')
current+=common+usage+checks+limits+'다음: 사용자 새결과 재생 후 남은 영상/구간의 잡음과 실제 동작을 구분해 강도 조정. M5 자동진입 없음.\n'
(ROOT/'md/CURRENT_TASK.md').write_text(current,encoding='utf-8')
for name,text in {
 'PROGRESS.md':common+change+checks+usage+limits,
 'ISSUES.md':('M4-JITTER-001 PARTIAL: 시간필터 존재만으로 잔떨림이 충분히 줄지 않음. '
  '저속 cutoff·방향일관성·고립 회전 impulse 억제 및 무릎 IK 평면 시간안정화 추가. '
  'LongSword 손목24~28%/무릎12~33% 추가지표감소. 지속 오추정·정답 정확도와 구분한다.\n')+change+checks+limits,
 'PROJECT.md':common+change+('correction.revision=3, cutoff_hz=[1.5,18], motion_coherence_weighting=true, '
  'isolated_impulse_degrees=12, ik_pole_smoothing_seconds=0.07 기록. '
  '기존 positions/animation 스키마와22본·부모계층/Quaternion 순서는 그대로다. '
  '정상구간의 quarter-frame 재생 보간 및 scene/missing hold 정책은 v0.7.2 그대로 유지.\n')+usage+limits
}.items():
    p=ROOT/'md'/name;p.write_text(heading+text+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
p=ROOT/'md/MOTION_FORMAT.md';p.write_text(p.read_text(encoding='utf-8')+'\n\n## v0.7.3 잔떨림 파라미터\n\n'
 'correction.revision=3. 기존 하한3Hz를1.5Hz로 낮추고 상한18Hz 유지, 이웃0.10초 각운동 일관성 가중을 추가한다. '
 '이웃6도 이내/중앙12도 초과의 고립 impulse 억제와 IK 굴곡면0.07초(빠른변화0.025초) 안정화 포함. '
 '추정/누락 상태와 유효span/컷 경계를 보존하며 원본 M3 motion을 바꾸지 않는다. '
 '재생 보간 정책과 root_motion_kind는 v0.7.2 그대로다.\n',encoding='utf-8')
(ROOT/'MVP요약/MVP4_잔떨림보정_v073.md').write_text(heading+common+change+checks+usage+limits,encoding='utf-8')
for name in ('README.md','HOME_TRANSFER.md'):
    p=ROOT/name;p.write_text('# 최신 MVP4 v0.7.3 · 잔떨림 강화\n\n'+usage+limits+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
n=max(int(p.name[4:]) for p in (ROOT/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=ROOT/'진행상황'/f'case{n}';case.mkdir()
for name in ('CURRENT_TASK.md','PROGRESS.md','ISSUES.md','PROJECT.md'):
    p=ROOT/'md'/name;shutil.copyfile(p,case/name)
    assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((case/name).read_bytes()).digest()
verification={'version':'0.7.3','tests_passed':78,'skipped':1,'compileall':'PASS','blender':reports,'comparison':comparison,
 'md_archive':case.name,'gpu_inference':False,'user_visual_review_pending':True,
 'review':['impulse/slow/fast/rate consistency, fixed lengths and IK pole noise',
          'existing core/app/Blender interfaces and raw/reference preservation',
          'source hashes, own-worker cancellation, unique outputs and isolated GUI/continuity regression']}
(e/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
folder=ROOT/'snapshots/v0.7.3 MVP';folder.mkdir();target=folder/'m4-jitter-refinement-v0.7.3.zip'
extras=[Path(__file__),ROOT/'validation/run_m4_jitter.py',ROOT/'MVP요약/MVP4_잔떨림보정_v073.md',*case.glob('*.md'),
 *[p for p in e.iterdir() if p.is_file()],*[p for d in ('LongSword-example','synthetic-example') for p in (e/d).glob('*') if p.is_file()]]
with zipfile.ZipFile(ROOT/'snapshots/v0.7.2 MVP/m4-continuous-playback-v0.7.2.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
    names=set()
    for info in old.infolist():
        name=info.filename
        if '__pycache__' in name or name.endswith('.pyc'):continue
        p=ROOT/name;z.writestr(name,p.read_bytes() if not name.startswith('진행상황/') and p.is_file() else old.read(info));names.add(name)
    for p in extras:
        name=p.relative_to(ROOT).as_posix()
        if name not in names:z.write(p,name);names.add(name)
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    for p in [ROOT/'app/gui.py',ROOT/'core/motion/correction.py',ROOT/'tests/test_motion_correction.py',*extras]:
        assert z.read(p.relative_to(ROOT).as_posix())==p.read_bytes()
    count=len(z.infolist())
with target.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
meta={'version':'0.7.3','files':count,'bytes':target.stat().st_size,'sha256':sha,'md_archive':case.name,'user_visual_review_pending':True}
(folder/'snapshot.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');print(json.dumps(meta),flush=True)
