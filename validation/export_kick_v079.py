"""Additional user-requested video: reuse saved inference, export current animation."""
import sys,json,subprocess,shutil,time,hashlib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.animation_job import export_animation,find_blender
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
e=ROOT/'validation/kick-v079';e.mkdir(exist_ok=False)
motion=next(p for p in (ROOT/'outputs').glob('*20261021_153218_249115c1/motion/motion.json'))
source=next(p for p in Path('C:/Users/user1/Desktop/애니메이션추출').glob('뒤차기*.mp4'))
data=json.loads(motion.read_text(encoding='utf-8'));raw=motion.parent.parent/'sam3d.json'
original={'source':sha(source),'motion':sha(motion),'raw':sha(raw)}
prior={p:sha(p) for p in motion.parent.glob('animation-*/animation.blend')}
state={'version':'0.7.9','status':'running','source':str(source),'motion':str(motion),'gpu_inference':False,'original_sha256':original}
def save():(e/'status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
save();start=time.monotonic()
try:
    blend=export_animation(motion);state['blend']=str(blend);save();print(str(blend),flush=True)
    for script,kind,args in [('verify_m4_blender.py','reopen',[blend.parent,blend.parent/'corrected-motion.json']),('verify_m4_interpolation.py','fractional',[blend.parent])]:
        with (e/f'{kind}.log').open('w',encoding='utf-8') as stream:
            subprocess.run([find_blender(),'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'validation'/script),'--',*map(str,args),str(e/f'{kind}.json')],stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=240,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        assert json.loads((e/f'{kind}.json').read_text(encoding='utf-8'))['passed']
    assert original=={'source':sha(source),'motion':sha(motion),'raw':sha(raw)}
    assert all(sha(p)==h for p,h in prior.items())
    animation=json.loads((blend.parent/'animation.json').read_text(encoding='utf-8'))
    assert animation['orientation_policy']['revision']==2
    example=e/'example';example.mkdir()
    for name in ('animation.blend','animation.json','corrected-motion.json','report.json'):shutil.copyfile(blend.parent/name,example/name)
    state.update(status='completed',frames=len(animation['frames']),frames_with_pose=animation['frames_with_pose'],fps=animation['fps'],
                 elapsed_seconds=round(time.monotonic()-start,1),originals_and_previous_blends_unchanged=True,
                 long_missing_spans=sum(s['kind']=='long_missing' for s in animation['orientation_policy']['missing_spans']))
    save()
    text=('## 2026-10-21 / v0.7.9 뒤차기4종류 추가 영상 확인\n\n'
          '사용자가 v0.7.9 결과를 긍정 확인하고 다른 영상 추출을 요청했다. 회전·발차기가 많은 뒤차기4종류를 선택했다. '
          '기존 SAM2/SAM3D/M3 추론을 재사용해 현행 보정·축 방향 정책으로 새 Blender 애니메이션을 출력했다. GPU 재추론 없음.\n'
          f"결과 {state['frames']}프레임 / {state['fps']:.3f}fps, 골반 유효 {state['frames_with_pose']}프레임. "
          '실제 Blender 독립 재오픈의 본 위치·회전·접지 및 fractional SLERP/누락경계 검사 PASS. 원본영상·원시JSON·M3·이전 .blend SHA 보존.\n'
          f"출력: {blend}\n짧은 확인경로: validation/kick-v079/example/animation.blend\n"
          '코드/모델/의존성 변경 없음, 기존 v0.7.9 MVP는 유지. 새 영상 사용자 시각확인 대기. '
          '기계적 검사 통과는 추정 자세의 정답률이나 모든 발차기 접지의 정확도를 뜻하지 않는다.\n')
    p=ROOT/'md/CURRENT_TASK.md';p.write_text(text+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
    for name in ('PROGRESS.md','PROJECT.md','ISSUES.md'):
        p=ROOT/'md'/name;p.write_text(text+'\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
    number=max(int(p.name[4:]) for p in (ROOT/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
    case=ROOT/'진행상황'/f'case{number}';case.mkdir()
    for name in ('CURRENT_TASK.md','PROGRESS.md','ISSUES.md','PROJECT.md'):
        p=ROOT/'md'/name;shutil.copyfile(p,case/name);assert sha(p)==sha(case/name)
    state['md_archive']=case.name;save();print(json.dumps(state,ensure_ascii=False),flush=True)
except BaseException as error:
    state.update(status='failed',error=str(error));save();raise
