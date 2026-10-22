"""Save the delayed-person selection change without restarting any user job."""
from pathlib import Path
import json,hashlib,re,zipfile
root=Path(__file__).resolve().parents[1];e=root/'validation/late-v0524'
v=json.loads((e/'worker-verification.json').read_text(encoding='utf-8'))
assert v['first_person_frame']==10 and v['prefix_raw_outputs_none'] and not v['gpu_inference_executed']
n=max(int(p.name[4:]) for p in (root/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=root/'진행상황'/f'case{n}';case.mkdir()
common=('기본 SAM3D+SAM2 경로에서 인물이 나중에 등장해도 최초검출/사용자선택 프레임으로 추적을 시작한다. '
        '원본 전체 프레임번호·시간은 유지하고 시작 전에는 ROI/관절/예측을 만들지 않는다. '
        '기존5분/18000프레임 제한·모델·회전·후처리 순서는 유지. M2 IN_PROGRESS. '
        '일괄추출 재시작/실제GPU추론/사용자GUI 종료 없음.\n')
texts={
'CURRENT_TASK.md':('Goal/Acceptance: 첫0프레임에 사람이 없더라도 늦은 등장 프레임에서 대상을 지정하고 '
 '전체 타임라인 추출 가능. 기본은0부터 매프레임 YOLOX로 첫후보를 탐색하고, 재생바 이동→대상확인은 '
 '그 정확한 프레임을 검사한다. 여러 후보면 번호 선택이 필요하며 임의로 다른 프레임 대상을 택하지 않는다. '
 '후보확인 프레임번호를 JobSettings.target_frame→sam2-request.initial_frame_index→SAM2 seed/propagation/guard까지 전달.\n'
 '테스트116PASS/1권한 opt-in skip. 실제 YOLOX가 빈10프레임 이후10에서인물발견. '
 '실제worker본문은 CPU모델대역으로 양출력20프레임/앞10관절None/후10만추론/경고구분 확인. '
 '실제SAM2/SAM3D 모델 GPU추론·정확도 검증은 미실시. 프로그램 재시작 후 실제 늦은등장 영상 확인 필요.\n'),
'PROGRESS.md':('원인: sam2_job이프레임0의박스만검사, worker도frame_idx=0 seed 고정, '
 'MaskPositionGuard가초기index!=0을재선택필요로잠갔다. 세부분을함께수정. '
 'app/target_start.py는정확한선택프레임/최초후보탐색·취소·EOF오류·자원반납을공유한다. '
 'GUI대상확인화면의프레임·재생바와출력설정을고정하고새영상/설정변경시초기화한다.\n'
 'SAM2worker는시작전빈mask/uninitialized/before_target_start를기록, 실제seed프레임부터만 '
 'propagate_in_video(start_frame_idx) 실행한다. MaskTrack/PositionGuard의시작인덱스를명시, '
 '이후정상분실/재연결보호는유지한다. 선택시작프레임의장면전환은새seed기준이며 '
 '직전빈배경과appearance비교하지않는다. SAM3D는시작전추론을건너뛰고WAITING표시, '
 '시작전빈구간경고와시작후추적유실경고를구분한다. SAM2 CLI에--target-frame 추가.\n'
 '116고유PASS/1skip: 비GUI회귀100, 분리선택5, 기존GUI11. '
 '대상탐색13+신규GUI1은10등장/지정15/빈지정5/모호2인/EOF·무인/취소/음수bool소수거부/늦은guard·후분실/ '
 '앞구간SAM3D미호출/request전달/GUI고정·재로드를포함. '
 '실제YOLOX/합성20프레임영상/실제SAM2·SAM3Dworker본문의CPU모델대역검증도완료. '
 '실제GPU모델은실행하지않았다. compileallPASS.\n'),
'ISSUES.md':('M2-LATESTART-001 / IMPLEMENTED_VERIFYING_GPU: 첫프레임검출필수/0seed고정/guard0초기화전제로 '
 '후등장인물이추출전거부됨. 공통등장탐색과명시프레임선택, seed/startidx전달, '
 '시작전uninitialized와전체시간보존으로수정. 10프레임등장과15프레임직접선택등회귀통과. '
 '실제GPU의나중seed동작/실제영상관절정확도는사용자확인남음. '
 '독립2D/MediaPipe 및 옛SAM3D detector방식에임의중간시드선택을확장하지않았고, 기본SAM2옵션에적용했다.\n'
 'QA-002 VERIFYING 유지: mask+GUI결합시험에서두번째Tk초기화에auto.tcl없음TclError가발생. '
 '제품코드를추측수정하지않고GUI종료시험을독립프로세스로재실행해1PASS, '
 '나머지기존GUI10/신규GUI1/자동GUI2도분리PASS. 환경문제해결확정아님. '
 '무인영상은손상영상이아닌인물후보없음으로알리고, 특정빈프레임선택시뒤의다른사람으로이동하지않는다.\n'),
'PROJECT.md':('v0.5.24: 기본SAM2대상확인/추출은0프레임없음시첫YOLOX후보를탐색한다. '
 '재생바를원하는위치로이동후대상확인을누르면해당프레임과후보번호를고정한다. '
 '0프레임에서대상확인은자동등장탐색, 0보다뒤위치에서는정확한그프레임만검사한다. '
 '최초후보가오검출/배경인물이라면원하는뒤프레임에서명시선택가능. '
 '초기프레임검색은identity검증이아니며후보가여럿이면사용자선택필요. '
 '시작전프레임을잘라내거나보간하지않고None/빈mask로유지, '
 '이후기존가림·분실정책은보존. 모델/가중치다운로드없음.\n')}
for name,text in texts.items():
 p=root/'md'/name
 p.write_text('## 2026-10-20 / v0.5.24 늦은 인물 등장·시작 프레임 선택\n\n'+text+common+
              f'4MD/{case.name} 동일SHA 보관/v0.5.24 MVP 저장.\n\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
 data=p.read_bytes();(case/name).write_bytes(data)
 assert hashlib.sha256(data).digest()==hashlib.sha256((case/name).read_bytes()).digest()
p=root/'README.md';text=p.read_text(encoding='utf-8').replace('현재 작업 버전은 v0.5.23','현재 작업 버전은 v0.5.24')
text=text.replace('2. 기본 SAM 3D + SAM 2 마스크 모드에서 필요하면 **대상 확인**으로 인물을 선택합니다.',
 '2. 기본 SAM 3D + SAM 2 마스크 모드에서 필요하면 **대상 확인**으로 인물을 선택합니다. '
 '시작에 사람이 없으면 첫 검출 프레임을 찾습니다. 원하는 위치로 재생바를 옮겨 대상 확인을 누르면 '
 '그 프레임에서 번호를 선택할 수 있습니다. 등장 전 구간은 빈 상태로 보존합니다.')
p.write_text(text+'\nv0.5.24 기본 SAM2 모드의 늦은 등장 지원은 위 사용법을 따릅니다. '
 '아래 옛 CLI/다른 추적 모드의 첫 프레임 설명과 구분하세요. '
 '영상 내 모든 사람이 자동으로 동일 인물로 확인되는 것은 아닙니다. 실제GPU 후등장 추론 확인은 남아 있습니다.\n',encoding='utf-8')
p=root/'HOME_TRANSFER.md';p.write_text('# 최신 v0.5.24 / 늦은 등장·시작 프레임 선택\n\n'+common+
 '116PASS/1skip. realYOLOX10등장/CPU대역worker20타임라인 확인, 실제GPU모델추론은미검증. '
 '프로그램 재실행→SAM2모드→재생바 이동→대상확인→번호선택→출력. '+case.name+' 참조.\n\n---\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
v.update(unique_tests_passed=116,skipped=1,md_archive=case.name,three_pass_review=[
 'frame selection/seed/motion guard/cancellation/EOF correctness',
 'shared scan and preserved full timeline/default initial frame compatibility',
 'no phantom prefix pose/identity substitution/local output preservation/no GPU contention'])
(e/'verification.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
folder=root/'snapshots/v0.5.24 MVP';folder.mkdir();target=folder/'m2-delayed-target-start-v0.5.24.zip'
extra=[root/'app/target_start.py',root/'tests/test_target_start.py',root/'validation/verify_late_v0524.py',
       Path(__file__),*case.glob('*.md'),*[p for p in e.rglob('*') if p.is_file()]]
with zipfile.ZipFile(root/'snapshots/v0.5.23 MVP/m2-five-minute-input-v0.5.23.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as out:
 names=set()
 for info in old.infolist():
  name=info.filename
  if '__pycache__' in name or name.endswith('.pyc'):continue
  path=root/name
  out.writestr(name,path.read_bytes() if not name.startswith('진행상황/') and path.is_file() else old.read(info));names.add(name)
 for path in extra:
  name=path.relative_to(root).as_posix()
  if name not in names:out.write(path,name);names.add(name)
with zipfile.ZipFile(target) as z:
 assert z.testzip() is None
 for name in ('app/gui.py','app/gui_jobs.py','app/sam2_job.py','app/sam2_worker.py','app/sam3d_worker.py',
              'app/target_start.py','core/pose2d/mask_tracking.py','tests/test_target_start.py'):
  assert z.read(name)==(root/name).read_bytes()
 count=len(z.infolist())
with target.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
meta={'version':'0.5.24','files':count,'bytes':target.stat().st_size,'sha256':sha,
      'md_archive':case.name,'m2_pass':False,'delayed_start_gpu_verified':False}
(folder/'snapshot.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');print(json.dumps(meta),flush=True)
