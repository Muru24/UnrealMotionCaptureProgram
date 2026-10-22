from pathlib import Path
import json,sys,collections
sys.path.insert(0,str(Path.cwd()))
from app.reconnection_job import ensure_reconnection
from app.knee_job import digest
root=Path.cwd();folder=root/'outputs/Norma_sam3d_20261019_165800_c118ce5d';selected=folder/'candidates_dff1f4ec';parts=folder/'parts_99f676a1';source=Path('C:/Users/user1/Desktop/애니메이션추출/Norma.mp4')
files=[source,folder/'sam3d.json',selected/'selected-joints.json',selected/'fullbody-candidates.json',selected/'joint-review.json',parts/'part-joints.json']
before={str(p):digest(p) for p in files}
out,state=ensure_reconnection(folder,source,selected,selected/'joint-review.json',parts)
r=json.loads((out/'report.json').read_text(encoding='utf-8'))
evidence=root/'validation/sam2/reconnect-v0516';evidence.mkdir(parents=True,exist_ok=True)
v={'directory':str(out),'state':state,'frames':218,'changed_frames':r['changed_frames'],'accepted_events':sum(e['accepted'] for e in r['events']),'events':len(r['events']),'reasons':dict(collections.Counter(e['reason'] for e in r['events'])),'inputs_unchanged':all(digest(p)==before[str(p)] for p in files),'new_gpu_inference':0}
assert v['inputs_unchanged'];(evidence/'verification.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(v,ensure_ascii=False))
