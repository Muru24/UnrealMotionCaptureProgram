"""After the GPU batch: verify six exports and provide short, unambiguous review paths."""
import sys,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.knee_job import digest
E=ROOT/'validation/all-except-norma-v079';state=json.loads((E/'batch.json').read_text(encoding='utf-8'))
assert state['status']=='completed' and len(state['videos'])==6
aliases=['01-LongSword','02-Sword','03-vivian','04-kick','05-dance','06-northdance']
rows=[];lines=['# MVP4 v0.7.9 · Norma 제외 전체 결과','','6개 완료. 신규 추론3개, 기존 추론 재사용3개.','','| 영상 | 프레임 | 유효 골반 | Blender |','|---|---:|---:|---|']
for item,alias in zip(state['videos'],aliases):
    assert item['status']=='completed' and item['originals_preserved']
    if item.get('error'):item.setdefault('prior_errors',[]).append(item.pop('error'))
    source=Path(item['source']);motion=Path(item['motion']);blend=Path(item['blend'])
    assert source.stem.casefold()!='norma'
    assert digest(source)==item['source_sha256'] and digest(motion)==item['motion_sha256']
    assert digest(motion.parent.parent/'sam3d.json')==item['raw_sha256']
    original=Path(item['review_folder']);target=E/alias;target.mkdir(exist_ok=True)
    for name in ('animation.blend','animation.json','corrected-motion.json','report.json'):
        p=target/name
        if p.exists():assert digest(p)==digest(original/name)
        else:shutil.copyfile(original/name,p)
        assert digest(p)==digest(blend.parent/name)
    for kind in ('reopen','fractional'):
        assert json.loads((original/f'{kind}.json').read_text(encoding='utf-8'))['passed']
    report=json.loads((target/'report.json').read_text(encoding='utf-8'))
    assert report['solver_sha256']==digest(ROOT/'tools/animate_reference_rig.py')
    assert report['correction_sha256']==digest(ROOT/'core/motion/correction.py')
    lines.append(f"| {source.name} | {item['frames']} | {item['frames_with_pose']} | [열기](<{target/'animation.blend'}>) |")
    rows.append({'source':str(source),'review_blend':str(target/'animation.blend'),'frames':item['frames'],'frames_with_pose':item['frames_with_pose'],'inference_reused':item['inference_reused'],'verified':True})
lines+=['','원본과 기존 결과 보존. 새 출력은 프로그램 결과목록에서도 선택 가능.','본 위치·회전·접지 및 서브프레임 보간 검사를 통과했으며, 동작 정답률 평가는 사용자 시각확인이 필요하다.']
(E/'결과목록.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(E/'verification.json').write_text(json.dumps({'version':'0.7.9','status':'completed','videos':rows,'md_archive':state['md_archive'],'norma_excluded':True},ensure_ascii=False,indent=2),encoding='utf-8')
(E/'batch.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(rows,ensure_ascii=False,indent=2),flush=True)
