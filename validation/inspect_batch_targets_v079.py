import sys,json,cv2
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.gui_jobs import JobSettings,make_backend,draw_candidates
from app.target_start import find_target_start
E=ROOT/'validation/all-except-norma-v079';records=[]
for pattern,label in [('Sword.mp4','Sword'),('전설*.mp4','northdance')]:
    source=next(Path('C:/Users/user1/Desktop/애니메이션추출').glob(pattern))
    settings=JobSettings(stage='sam3d',tracking_method='sam2')
    index,frame,boxes=find_target_start(source,settings,lambda:False,make_backend)
    draw_candidates(frame,boxes);ok,encoded=cv2.imencode('.jpg',frame)
    assert ok
    (E/f'{label}-targets.jpg').write_bytes(encoded.tobytes())
    records.append({'source':str(source),'frame':index,'boxes':boxes.tolist()})
(E/'initial-targets.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(records,ensure_ascii=False))
