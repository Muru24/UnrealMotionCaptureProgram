"""Resumable six-video user batch. Existing canceled historical batches stay untouched."""
import sys,json,time,traceback,subprocess,shutil,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.gui_jobs import JobSettings,new_output,run_job
from app.knee_job import digest
from app.automatic_postprocess import process_sam_result
from app.motion_job import ensure_motion
from app.animation_job import export_animation,find_blender
from core.video.decoder import inspect_video
E=ROOT/'validation/all-except-norma-v079';E.mkdir(exist_ok=True)
MANIFEST=E/'batch.json';CANCEL=E/'CANCEL'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save():
    pending=E/'batch.pending.json';pending.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    # Windows readers/virus scanners may briefly deny replacement of the checkpoint.
    for attempt in range(20):
        try:pending.replace(MANIFEST);break
        except PermissionError:
            if attempt==19:raise
            time.sleep(.05)
def cancelled():return CANCEL.exists()
if MANIFEST.exists():
    state=read(MANIFEST)
    if state['status']=='completed':raise RuntimeError('Already completed; do not duplicate this batch.')
else:
    sources=sorted((p for p in Path('C:/Users/user1/Desktop/애니메이션추출').glob('*.mp4') if p.stem.casefold()!='norma'),key=lambda p:p.name.casefold())
    state={'version':'0.7.9','status':'running','excluded':['Norma.mp4'],'candidate_inference_type':'full','videos':[]}
    for i,p in enumerate(sources):
        state['videos'].append({'source':str(p),'source_sha256':digest(p),'status':'pending','review_folder':str(E/f'{i+1:02d}-{p.stem[:25]}')})
    save()
settings=JobSettings(stage='sam3d',tracking_method='sam2',target_index=None,target_frame=None)
for item in state['videos']:
    if item['status']=='completed':continue
    source=Path(item['source']);review=Path(item['review_folder']);review.mkdir(exist_ok=True)
    started=time.monotonic();last=0.;last_print=0.
    def progress(done,total):
        global last,last_print
        now=time.monotonic();item.update(done=int(done),total=int(total),stage_elapsed_seconds=round(now-started,1))
        if now-last>1:save();last=now
        if now-last_print>20:print(source.name,item.get('phase'),done,total,flush=True);last_print=now
    def phase(text):
        item.update(phase=text,done=0,total=0);save();print(source.name,text,flush=True)
    try:
        if cancelled():raise KeyboardInterrupt
        assert digest(source)==item['source_sha256']
        item['status']='running';state['status']='running';save()
        if item.get('error') and not item.get('raw_completed') and not item.get('inference_reused'):
            item.setdefault('prior_failed_outputs',[]).append(item.pop('output',None))
            item.pop('error',None)
        if not item.get('output'):
            for request in sorted((ROOT/'outputs').glob('*/sam-request.json'),key=lambda p:p.stat().st_mtime_ns,reverse=True):
                try:
                    q=read(request);out=request.parent
                    if Path(q['source']).resolve()!=source.resolve():continue
                    if q.get('source_sha256')!=item['source_sha256']:continue
                    report=read(out/'report.json')
                    if report.get('status') not in ('completed','completed_with_warnings'):continue
                    if not (out/'motion/motion.json').is_file():continue
                    item.update(output=str(out),inference_reused=True);break
                except (OSError,KeyError,ValueError):continue
            if not item.get('output'):item.update(output=str(new_output(source,'sam3d')),inference_reused=False)
            save()
        output=Path(item['output']);motion=output/'motion/motion.json'
        if item['inference_reused']:
            raw_sha=digest(output/'sam3d.json');motion_sha=digest(motion)
        else:
            if not item.get('raw_completed'):
                phase('SAM2 tracking / SAM3D full extraction')
                # First-frame preview inspected: Sword target0 is the mirror reflection.
                selected=JobSettings(stage='sam3d',tracking_method='sam2',target_index=1,target_frame=0) if source.name=='Sword.mp4' else settings
                item['target_selection']='visually_checked_real_person_index_1' if source.name=='Sword.mp4' else 'single_detected_person'
                item['raw_report']=run_job(source,output,selected,cancelled,progress)
                item['raw_completed']=True;save()
            phase('Automatic candidate / limb re-estimation')
            post=process_sam_result(output,source,cancelled,progress,phase)
            item['automatic_postprocess']=post;save()
            if post['automatic_postprocess']['status']!='completed_with_estimates':
                raise RuntimeError('Automatic postprocessing incomplete: '+str(post['automatic_postprocess'].get('errors')))
            phase('Standard motion conversion')
            motion,_=ensure_motion(output,source,post,cancelled)
            raw_sha=digest(output/'sam3d.json');motion_sha=digest(motion)
        item['motion']=str(motion);prior={p:digest(p) for p in motion.parent.glob('animation-*/animation.blend')}
        blend=None
        for report in sorted(motion.parent.glob('animation-*/report.json'),key=lambda p:p.stat().st_mtime_ns,reverse=True):
            try:
                r=read(report)
                if r.get('status')!='completed' or r.get('motion_sha256')!=motion_sha:continue
                if r.get('solver_sha256')!=digest(ROOT/'tools/animate_reference_rig.py') or r.get('correction_sha256')!=digest(ROOT/'core/motion/correction.py'):continue
                if r.get('root_solver_sha256')!=digest(ROOT/'core/motion/root_motion.py') or r.get('root_camera_job_sha256')!=digest(ROOT/'app/root_motion_job.py'):continue
                if r.get('corrected_motion_sha256')!=digest(report.parent/'corrected-motion.json'):continue
                a=read(report.parent/'animation.json')
                if a.get('orientation_policy',{}).get('revision')!=2:continue
                if (report.parent/'animation.blend').is_file():blend=report.parent/'animation.blend';break
            except (OSError,ValueError,KeyError):continue
        item['animation_reused']=blend is not None
        if blend is None:
            phase('Current correction / Blender animation');blend=export_animation(motion,cancelled)
        item['blend']=str(blend);save();phase('Independent Blender reopen / interpolation check')
        for script,kind,args in [('verify_m4_blender.py','reopen',[blend.parent,blend.parent/'corrected-motion.json']),('verify_m4_interpolation.py','fractional',[blend.parent])]:
            if cancelled():raise KeyboardInterrupt
            with (review/f'{kind}.log').open('w',encoding='utf-8') as stream:
                subprocess.run([find_blender(),'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'validation'/script),'--',*map(str,args),str(review/f'{kind}.json')],stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=300,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            assert read(review/f'{kind}.json')['passed']
        assert digest(source)==item['source_sha256'] and digest(output/'sam3d.json')==raw_sha and digest(motion)==motion_sha
        assert all(digest(p)==h for p,h in prior.items())
        a=read(blend.parent/'animation.json')
        for name in ('animation.blend','animation.json','corrected-motion.json','report.json'):
            target=review/name
            if target.exists():assert digest(target)==digest(blend.parent/name)
            else:shutil.copyfile(blend.parent/name,target)
        item.update(status='completed',phase='completed',frames=len(a['frames']),frames_with_pose=a['frames_with_pose'],fps=a['fps'],
                    seconds=round(time.monotonic()-started,1),raw_sha256=raw_sha,motion_sha256=motion_sha,originals_preserved=True)
        save();print('COMPLETED',source.name,item['frames'],flush=True)
    except KeyboardInterrupt:
        item['status']='cancelled';state['status']='cancelled_by_user';save();raise
    except Exception as error:
        item.update(status='failed',error=str(error));save();traceback.print_exc()
state['status']='completed' if all(v['status']=='completed' for v in state['videos']) else 'completed_with_errors';save()
lines=['# v0.7.9 Norma 제외 전체 영상 결과','',f"상태: {state['status']}",'','기존 추론·현행 애니메이션은 무결성 확인 후 재사용. 새 추론은 기본 full 후보 방식.','']
for v in state['videos']:
    lines.append(f"- {Path(v['source']).name}: {v['status']}"+(f" / {v['frames']}프레임 / [Blender 열기](<{Path(v['review_folder'])/'animation.blend'}>)" if v['status']=='completed' else ' / '+v.get('error','')))
(E/'결과목록.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
text=('## 2026-10-21 / v0.7.9 Norma 제외6영상 일괄 출력\n\n'
      'Scope: 원본 폴더 MP4 중 Norma만 제외, 총6개. 이전 취소 batch는 재시작하지 않고 별도 요청 batch를 생성했다. '
      '기존 현행 결과는 source/raw/M3/code SHA로 확인 후 재사용, 없는 영상은 SAM2/SAM3D·기본 full 자동후처리·M3·현행 Blender까지 실행.\n'
      f"상태: {state['status']}. 완료 {sum(v['status']=='completed' for v in state['videos'])}/6. "
      '결과 및 개별 검사: validation/all-except-norma-v079/결과목록.md, batch.json. '
      '완료 항목은 독립 Blender 재열기·접지/위치·fractional SLERP/누락경계 검사와 원본/기존 .blend SHA 보존 확인. '
      '사용자 시각확인 대기. 코드/모델 변경 없음, 기존 v0.7.9 MVP 유지.\n')
if any(v.get('prior_failed_outputs') for v in state['videos']):
    text+=('원인/조치: Sword 첫 프레임에 실제 인물과 거울 반사2후보가 있어 자동 단일대상 선택 가드가 실행을 중단했다. '
           '첫 화면의 후보 이미지를 직접 확인해 실제 인물 index1을 명시한 별도 새 출력으로 재시도했다. '
           '기존 실패 폴더와 완료된 다른 영상은 보존했다. 최종 상태/검사 결과는 위 batch.json을 기준으로 확인한다.\n')
text+=('일괄 추출 중 북북춤의 상태 JSON 교체에 Windows 공유/접근 오류(WinError5)가1회 발생했다. '
       '기본 추론·후보 결과를 보존해 후처리를 재개했다. 배치 도구의 상태 파일 교체에는 짧은 재시도를 추가하고 '
       '대기 프로세스의 동시 읽기가 끝난 뒤 이어서 실행했다. 앱의 추론·보정 코드는 변경하지 않았다.\n')
for name in ('CURRENT_TASK.md','PROGRESS.md','PROJECT.md','ISSUES.md'):
    p=ROOT/'md'/name;p.write_text(text+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
n=max(int(p.name[4:]) for p in (ROOT/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=ROOT/'진행상황'/f'case{n}';case.mkdir()
for name in ('CURRENT_TASK.md','PROGRESS.md','PROJECT.md','ISSUES.md'):
    p=ROOT/'md'/name;shutil.copyfile(p,case/name);assert digest(p)==digest(case/name)
state['md_archive']=case.name;save();print('BATCH',state['status'],case.name,flush=True)
