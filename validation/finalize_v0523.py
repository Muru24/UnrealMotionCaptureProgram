"""Preserve the five-minute input change and its verification as one local MVP."""
from pathlib import Path
import hashlib
import json
import re
import zipfile

root=Path(__file__).resolve().parents[1]
evidence=root/'validation/long-v0523'
evidence.mkdir(exist_ok=True)
case_numbers=[int(m.group(1)) for p in (root/'진행상황').iterdir()
              if p.is_dir() and (m:=re.fullmatch(r'case(\d+)',p.name))]
case=root/'진행상황'/f'case{max(case_numbers,default=0)+1}'
case.mkdir()
common=('사용자 요청으로 입력·추출 지원을 최대5분(300초)/18000프레임으로 확장했다. '
        '1920px 이하 짝수 해상도/2GiB 파일 제한은 유지한다. 5분60fps까지 프레임 한도에 들어가며 '
        '더 높은fps는 길이 이내라도 총프레임 한도에 걸릴 수 있다. 모델·대상선택·회전·추론횟수는 유지. '
        'Norma 의상가림은 알려진 한계로 보류, M2 IN_PROGRESS.\n')
texts={
 'CURRENT_TASK.md':('Goal/Acceptance: 3분 입력 거부의 원인이던60초/3600프레임 검사를 사용자가 지정한5분으로 '
   '확장. GUI/2D/MediaPipe3D/SAM2/SAM3D/완성후처리에서 동일18000프레임 한도, 300초 경계 허용/초과 거부. '
   'core/video/limits.py를 공통 정책으로 사용한다.\n'
   '검증: 실제32x32·60fps·300초18000프레임 합성 MP4의 로드/CPU stub추출/프레임·timestamp·MP4 전체디코드 '
   '완료. 실제 인물5분 GPU 전체추출은 미실행/품질·최대RAM 미검증. 사용자 GUI 작업과 GPU 경쟁을 만들지 않았다. '
   '프로그램 종료·재실행 뒤 실제 긴 영상 확인 필요. 일괄추출 사용자취소 상태 유지/자동재개 없음.\n'),
 'PROGRESS.md':('원인: gui_jobs.read_source가60초/3600프레임 초과를 인식 전 거부했고, SAM2/SAM3D worker와 '
   '2D/MediaPipe 및 completion에도 별도3600 가드가 있었다. 이를 공통300초/18000 가드로 함께 변경. '
   '수동 guidance의 총지정수 상한도 프레임 한도와 동기화(수동 UI 재추가 없음).\n'
   '긴 SAM2 forward(total>3600)에만 오래된non_cond_frame_outputs를 제거한다. 모델이 읽는 strided '
   'num_maskmem 기억과 max_obj_ptrs 최근 포인터보다 보수적인 최소32프레임을 유지하고 '
   '최초/모든 conditioning 출력은 보존한다. 원본 SAM2 소스/가중치 수정 없음. 기존 짧은 영상 경로 유지. '
   '로컬 child script의 core 공통모듈 import를 위해 sam3d_worker의 ROOT sys.path도 명시했다.\n'
   '128고유PASS/1skip, compileall PASS. 신규14: 60/180/300초 및18000 경계, 시간·프레임 초과, '
   '오류타입, 3종stride/기억설정의18000타임라인 메모리읽기 동일·상한/conditioning 보존, '
   '실제5분 MP4 CPU 추출/전체디코드, GUI 조기거부, completion18000 누락관절미생성. '
   '기존114PASS/1skip: completion/guidance25, 2D/3D/SAM/자동74+4, GUI11. '
   '권한 opt-in Windows process tree1skip. 실제 GPU5분/추적 정확도·최대RAM 검증 아님.\n'),
 'ISSUES.md':('M2-LONGVIDEO-001 / IMPLEMENTED_VERIFYING_GPU: 3분 영상은 ML사람인식 실패가 아니라 '
   '60초/3600프레임 입력 제한으로 거부됨. 5분/18000으로 전체 관련 가드를 통일, 실제 합성5분 '
   'CPU 입출력 및 후처리 타임라인 검증 통과. 사용자 실제 파일은 아직 미제공, 2GiB/1920px '
   '별도 제한 여부 미확인. 실제5분 SAM2/SAM3D GPU 및 최대RAM 검증은 남김.\n'
   'M2-LONGVIDEO-MEMORY / MITIGATED_UNIT_VERIFIED: 기존SAM2가 모든 비조건부 과거 출력을 CPU에 '
   '계속 보관하는 구조를 확인. 긴 단방향 처리에서 미래 추론에 필요한 최근 기억보다 오래된 '
   '출력만 폐기. 3종 설정18000프레임에서 다음frame이 참조할 모든 기억 동일성/최초조건 보존 검사. '
   '이미지LazyFrames2개 cache와 CPUoffload 유지. GPU실측 및 downstream 대형JSON 최대RAM은 미측정. '
   'PERF-001 동시GPU경쟁 제거 이후 속도회복/동일영상 버전비교는 계속 VERIFYING.\n'),
 'PROJECT.md':('v0.5.23: GUI/CLI 처리 입력은 최대300초·18000프레임, MP4/최대2GiB/각변1920px 이하 '
   '짝수 해상도. M0 메타데이터 검사 자체는 더 큰 해상도를 읽을 수 있지만 추출 규격과 다르다. '
   '길이공통정책 core/video/limits.py, 긴SAM2 저장수 제한 core/pose2d/sam2_memory.py. '
   '기존 모델·SAM2대상추적→SAM3D→후보→관절검사→부위재추정→재관측 순서 유지. '
   '기존 프로그램 프로세스는 재실행해야 새 제한 적용. 배치추출 재시작/사용자 프로세스종료 없음.\n')}
for name,text in texts.items():
 p=root/'md'/name
 p.write_text('## 2026-10-20 / v0.5.23 최대 5분 입력\n\n'+text+common+
              f'원본4MD 갱신/{case.name} 동일SHA 보관/v0.5.23 MVP 저장.\n\n---\n\n'+
              p.read_text(encoding='utf-8'),encoding='utf-8')
 data=p.read_bytes();(case/name).write_bytes(data)
 assert hashlib.sha256(data).digest()==hashlib.sha256((case/name).read_bytes()).digest()
p=root/'README.md';text=p.read_text(encoding='utf-8')
text=text.replace('현재 작업 버전은 v0.5.22','현재 작업 버전은 v0.5.23')
text=text.replace('60초/3600프레임 이하','5분(300초)/18,000프레임 이하')
text=text.replace('최대 60초 / 3600프레임','최대 5분(300초) / 18,000프레임')
p.write_text(text+'\n긴 영상: 5분60fps까지 총프레임 한도에 들어갑니다. 2GiB/1920px 짝수 해상도 제한은 유지합니다. '
 'v0.5.23은 합성5분 MP4 CPU 입출력/프레임검증 완료, 실제5분 GPU전체추출 검증은 남아 있습니다. '
 '프로그램을 재실행해야 새 제한이 적용됩니다.\n',encoding='utf-8')
p=root/'HOME_TRANSFER.md';p.write_text('# 최신 v0.5.23 / 최대 5분 입력\n\n'+
 common+'128PASS/1skip. 합성5분 CPU입출력 확인, 실제긴영상 GPU 전체검증 남음. '
 '배치추출 사용자취소 유지, 사용자GUI 재시작 필요.\n\n---\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
clip=next((root/'validation/long-v0523-final-tests').glob('test_five_minute*/5분 입력.mp4'))
video_report=clip.parent/'result/report.json'
verification={'version':'0.5.23','max_seconds':300,'max_frames':18000,'unique_pass':128,'skipped':1,
 'skip_reason':'Windows real process-tree test requires explicit opt-in',
 'synthetic_source':str(clip.relative_to(root)),'synthetic_source_sha256':hashlib.file_digest(clip.open('rb'),'sha256').hexdigest(),
 'synthetic_report':json.loads(video_report.read_text(encoding='utf-8')),
 'synthetic_decoded_output_frames':18000,'gpu_long_video_executed':False,'source_person_accuracy_verified':False,
 'three_pass_review':['boundary/import correctness','shared policy and unchanged model/short path',
                      'local path protections/output preservation/forward memory retention'],
 'md_archive':case.name,'m2_pass':False}
(evidence/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
folder=root/'snapshots/v0.5.23 MVP';folder.mkdir()
target=folder/'m2-five-minute-input-v0.5.23.zip'
extra=[root/'core/video/limits.py',root/'core/pose2d/sam2_memory.py',root/'tests/test_long_video.py',
       Path(__file__),*case.glob('*.md'),evidence/'verification.json',
       root/'validation/run_all_mp4_v0522.py',root/'validation/all-mp4-v0522/batch.json',
       root/'validation/all-mp4-v0522/performance-diagnosis.json']
oldpath=root/'snapshots/v0.5.22 MVP/m2-gated-native-point-guidance-v0.5.22.zip'
with zipfile.ZipFile(oldpath) as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as out:
 names=set()
 for info in old.infolist():
  name=info.filename
  if '__pycache__' in name or name.endswith('.pyc'):continue
  path=root/name
  out.writestr(name,path.read_bytes() if not name.startswith('진행상황/') and path.is_file() else old.read(info))
  names.add(name)
 for path in extra:
  name=path.relative_to(root).as_posix()
  if name not in names:out.write(path,name);names.add(name)
with zipfile.ZipFile(target) as archive:
 assert archive.testzip() is None
 for name in ('app/gui.py','app/gui_jobs.py','app/sam2_worker.py','app/sam3d_worker.py','app/sam3d_job.py',
              'app/processing.py','app/processing3d.py','core/pose3d/completion.py','core/pose3d/guidance.py',
              'core/video/limits.py','core/pose2d/sam2_memory.py','tests/test_long_video.py'):
  assert archive.read(name)==(root/name).read_bytes()
 count=len(archive.infolist())
with target.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
meta={'version':'0.5.23','files':count,'bytes':target.stat().st_size,'sha256':sha,
      'md_archive':case.name,'m2_pass':False,'gpu_long_video_verified':False}
(folder/'snapshot.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
print(json.dumps(meta),flush=True)
