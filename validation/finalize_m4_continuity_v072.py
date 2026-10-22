"""Archive the continuous playback/contact-transition fix without changing prior MVPs."""
from pathlib import Path
import json,hashlib,re,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1];e=ROOT/'validation/m4-continuity'
results=json.loads((e/'results.json').read_text(encoding='utf-8'))
reports={}
for item in results:
    label=item['label'];src=Path(item['blend']).parent;dest=e/(label+'-example');dest.mkdir(exist_ok=True)
    for name in ('animation.blend','animation.json','corrected-motion.json','report.json'):shutil.copyfile(src/name,dest/name)
    provenance=json.loads((src/'report.json').read_text(encoding='utf-8'))
    for key,path in (('solver_sha256',ROOT/'tools/animate_reference_rig.py'),('correction_sha256',ROOT/'core/motion/correction.py')):
        assert provenance[key]==hashlib.sha256(path.read_bytes()).hexdigest()
    for kind in ('reopen','fractional'):
        report=json.loads((e/f'{label}-{kind}.json').read_text(encoding='utf-8'));assert report['passed'];reports[label+'-'+kind]=report
steps=json.loads((e/'transition-comparison.json').read_text())
heading='## 2026-10-21 / MVP4 v0.7.2 자세 전환 연속 재생\n\n'
common=('사용자: 자세가 이어지지 않고 순간이동처럼 바뀜. 정상 구간의 재생 보간과 접지 제약의 진입/해제 전환을 수정했다. '
 '원본22본/M3 motion/모델출력·이전애니메이션/MVP는 보존. GPU추론·새의존성 없음.\n')
change=('원인/조치: v0.7.0/1은 누락 경계 보호를 위해 모든 FCurve를 CONSTANT로 저장해 정상프레임 사이도 자세가 계단식으로 변했다. '
 '동일 segment/scene의 두 유효 bone pose 사이만 1/4프레임 간격 Quaternion 최단SLERP와 위치선형키를 bake, '
 '그 사이 FCurve는 LINEAR로 변경. 실제 장면전환·관절누락·전체미검출과 가시성 채널은 CONSTANT 유지. '
 '기존 q/-q 부호연속과 단위Quaternion 유지. 더 촘촘한 키 사이 회전은 Blender 선형성분 보간의 근사다.\n'
 '접지 제약도 갑자기 끊겼다. 루트 예측이0.15m를 넘으면 앵커를 버리던 처리를 연속적인 속도제한/감쇠로 바꿨다. '
 '앵커 유무만으로 골반높이를 즉시 재설정하지 않고 같은 관측구간에서는 완만하게 갱신한다. '
 '고정발 해제는 제약오프셋을 점차 제거하고, 새 접지/지면충돌 진입은 이전 발 위치에서 목표로 접근시킨다. '
 '접지→지면충돌 전환도 별도 release로 처리한다. 무릎 IK/도달거리 투영/다리길이/지면 한계를 유지. '
 '보정 offset 해제속도3m/s, 추정 루트XY soft1.8m/s/Z soft1.2m/s; 원래 swing 속도 전체를 동일 제한하지 않는다.\n')
usage=('사용: 프로그램 재시작→결과 선택→Blender 애니메이션 저장을 다시 누른다. '
 '이전 .blend는 바뀌지 않는다. 새 결과는 motion/animation-<id>/에 고유 저장되고 오른쪽 보정 미리보기도 갱신. '
 '확인용 최신파일: validation/m4-continuity/LongSword-example/animation.blend.\n')
checks=('검증: 고유75 PASS/기존권한 opt-in1 SKIP, compileall PASS. 비GUI24+기존38+격리GUI3+기존GUI10. '
 '발차기·착지 테스트에 최대발점프<0.3m 및 release_blend 상태 회귀 추가. '
 '처음 강화한 테스트는 swing→ground_collision 복귀에서0.75m가 남아 실패했고 해당 전환까지 보완 후 통과. '
 '접지/충돌을 같은 상태로 합친 중간 수정은 실제 LongSword에서 점프가 다시 커져, 앵커 해제와 충돌 진입을 구분해 최종 검증했다. '
 'LongSword445/합성80프레임 새 Blender저장·재오픈·전체 유효본/메쉬/접지 검사 PASS. '
 '정수프레임만 보던 이전검증을 확장해 실제 Blender 0.25/0.5/0.75 서브프레임 회전값을 SLERP와 비교: '
 'LongSword29304/합성4950회전 표본 PASS, 합성 누락/컷44개 hold PASS. '
 '원본 motion SHA 불변. 최대발목 프레임 이동 좌0.7091→0.2244m/우0.7345→0.2394m, 골반0.1514→0.0724m. '
 '이는 전체 위치변화 지표이며 정답 동작/모든 순간튐 해결을 뜻하지 않는다.\n')
limits=('남은 한계: 추정접지·접지기반 루트이고 영상의 실제 월드이동을 측정하지 않는다. '
 '위치 연속성은 개선했으나 고속 원본/오추정/몸통 회전 급변·개별 누락 fallback은 여전히 튈 수 있다. '
 '긴 누락/컷은 동작을 꾸며 연결하지 않는다. 전환 보정은 작은 시간 지연/발 미끄러짐을 유발할 수 있다. '
 '사용자가 본 영상/구간은 이번에 새로 특정하지 않았고 실제 재검증은 LongSword 및 합성이다. '
 '5분 대용량의 subframe 키4배 bake 속도·메모리 미측정, 엔진임포트 미검증. 사용자 새 결과 확인 대기.\n')
current=heading+'Milestone M4 연속재생 수정 / 구현·이번 자동검증 완료, 사용자 시각확인 대기.\n'
current+=('Goal/Acceptance: 정상 동작구간의 subframe 연속 회전·위치 재생, 접지/충돌 전환 점프 감소, 누락/컷 보호·원본보존. '
 'Scope: core/motion/correction.py, tools/animate_reference_rig.py, app/gui.py 버전, tests/test_motion_correction.py, '
 'validation/run_m4_continuity.py/verify_m4_interpolation.py와 관련MD.\n')+common+usage+checks+limits
current+='다음: 사용자가 새 파일 재생 확인. 잔여 튐은 해당 영상/시간대를 기준으로 원시 방향오류와 제약 전환을 분리. M5 자동진입 없음.\n'
(ROOT/'md/CURRENT_TASK.md').write_text(current,encoding='utf-8')
for name,text in {
    'PROGRESS.md':common+change+checks+usage+limits,
    'ISSUES.md':('M4-PLAYBACK-001 FIXED_FOR_VALID_SPANS: 모든 애니메이션 채널의 CONSTANT 보간으로 정상 프레임도 계단식. '
        '유효 동일구간에 SLERP subframe+LINEAR, 경계/가시성 step 유지. 실제 fractional 평가로 확인.\n'
        'M4-CONTACT-TRANSITION-001 PARTIAL: 큰 루트예측 거부 시 앵커 해제, 해제 뒤 큰 보정offset이 즉시 없어짐, '
        '새 접지에서 골반높이 재설정, 충돌 진입/종료가 발점프 유발. 감쇠·전환 오프셋 fade·도달거리 IK 추가. '
        '최종 LongSword 발최대점프 감소 확인, 원시의 빠른동작/지속관절오류는 별도.\n')+change+checks+limits,
    'PROJECT.md':common+change+usage+('schema/22본/기존파일 변경 없음. correction.revision=2, 전환상태 '
        'contact_transition/collision_transition/release_blend와 속도 메타데이터 추가. '
        'animation.json.playback_interpolation으로 valid span의 quarter-frame bake 방식을 명시한다. '
        '정수 pose 데이터는 유지하고 재생파일에 subframe 키를 추가하며 미검출/컷 보호는 유지한다.\n')+limits
}.items():
    p=ROOT/'md'/name;p.write_text(heading+text+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
p=ROOT/'md/MOTION_FORMAT.md';p.write_text(p.read_text(encoding='utf-8')+'\n\n## v0.7.2 연속 재생\n\n'
 '이전 CONSTANT 전체샘플 정책은 아래 방식으로 대체한다. JSON 정수프레임의 두 bone pose가 모두 유효하고 같은 segment/scene일 때 '
 '.blend에0.25/0.5/0.75프레임 SLERP 회전·선형 위치키를 추가하고 그 구간은 LINEAR. '
 '미검출/컷/개별 관절누락 경계 및 가시성 채널은 CONSTANT를 유지한다. 추가키 사이 Quaternion 성분은 선형 근사다. '
 'correction.revision=2의 feet 전환상태(contact_transition/collision_transition/release_blend)는 완전히 고정된 접지가 아니므로 '
 '접지 정확도나 foot-lock 지표에 inferred_contact와 합산하지 않는다. 원래 swing 동작과 제약offset 감쇠를 구분한다.\n',encoding='utf-8')
(ROOT/'MVP요약/MVP4_자세전환_연속재생_수정.md').write_text(heading+common+change+checks+usage+limits,encoding='utf-8')
for name in ('README.md','HOME_TRANSFER.md'):
    p=ROOT/name;p.write_text('# 최신 MVP4 v0.7.2 · 연속 재생 수정\n\n'+usage+limits+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
n=max(int(p.name[4:]) for p in (ROOT/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=ROOT/'진행상황'/f'case{n}';case.mkdir()
for name in ('CURRENT_TASK.md','PROGRESS.md','ISSUES.md','PROJECT.md'):
    p=ROOT/'md'/name;shutil.copyfile(p,case/name)
    assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((case/name).read_bytes()).digest()
verified={'version':'0.7.2','tests_passed':75,'skipped':1,'compileall':'PASS','blender':reports,'steps':steps,
 'md_archive':case.name,'gpu_inference':False,'user_visual_review_pending':True,
 'review':['fractional quaternion evaluation, safe interval/visibility interpolation and fixed-length contact transitions',
          'unchanged model/raw/skeleton interfaces, core correction and Blender playback responsibilities',
          'provenance and unique outputs, source hashes, cancellation/GUI regression and explicit residual limits']}
(e/'verification.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2),encoding='utf-8')
folder=ROOT/'snapshots/v0.7.2 MVP';folder.mkdir();target=folder/'m4-continuous-playback-v0.7.2.zip'
extras=[Path(__file__),ROOT/'validation/run_m4_continuity.py',ROOT/'validation/verify_m4_interpolation.py',
 ROOT/'MVP요약/MVP4_자세전환_연속재생_수정.md',*case.glob('*.md'),*[p for p in e.iterdir() if p.is_file()],
 *[p for d in ('LongSword-example','synthetic-example') for p in (e/d).glob('*') if p.is_file()]]
with zipfile.ZipFile(ROOT/'snapshots/v0.7.1 MVP/m4-ground-slerp-v0.7.1.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
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
    for p in [ROOT/'app/gui.py',ROOT/'tools/animate_reference_rig.py',ROOT/'core/motion/correction.py',*extras]:
        assert z.read(p.relative_to(ROOT).as_posix())==p.read_bytes()
    count=len(z.infolist())
with target.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
meta={'version':'0.7.2','files':count,'bytes':target.stat().st_size,'sha256':sha,'md_archive':case.name,
      'valid_span_subframe_interpolation':True,'contact_transition_blend':True,'user_visual_review_pending':True}
(folder/'snapshot.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');print(json.dumps(meta),flush=True)
