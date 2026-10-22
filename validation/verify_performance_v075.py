"""Exercise the real candidate worker on a bounded, unique derived result."""
from pathlib import Path
import json,subprocess,hashlib,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.candidate_job import save_selection
status=json.loads((ROOT/'validation/dance-v074/status.json').read_text(encoding='utf-8'))
folder=Path(status['output']);source=Path(status['source'])
raw=json.loads((folder/'sam3d.json').read_text(encoding='utf-8'))
out=ROOT/'validation/performance-v075-worker'
out.mkdir(exist_ok=(out/'candidates.json').is_file())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before={str(p):sha(p) for p in (source,folder/'sam3d.json')}
request={'source':str(source),'start':0,'end_exclusive':3,'frames':raw['frames'],'inference_type':'body'}
(out/'request.json').write_text(json.dumps(request),encoding='utf-8')
if not (out/'candidates.json').is_file():
    with (out/'runtime.log').open('w',encoding='utf-8') as log:
        subprocess.run([str(ROOT/'.validation/sam3d/env/Scripts/python.exe'),'-u',str(ROOT/'app/candidate_worker.py'),str(out)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
data=json.loads((out/'candidates.json').read_text(encoding='utf-8'))
assert data['inference_type']=='body' and len(data['frames'])==3
assert all(set(r['candidates'])=={'observed','tight','stable-flip'} for r in data['frames'])
short=dict(raw,frames=raw['frames'][:3])
(out/'sam3d.json').write_text(json.dumps(short),encoding='utf-8')
selected=out/'selection';selected.mkdir(exist_ok=False)
(selected/'candidates.json').write_text(json.dumps(data),encoding='utf-8')
save_selection(selected,source,short,{r['frame_index']:r['candidates'] for r in data['frames']})
assert all(sha(Path(p))==digest for p,digest in before.items())
(out/'verification.json').write_text(json.dumps({'worker':'PASS','candidate_selection':'PASS','frames':3,'candidate_calls':9,'source_and_raw_preserved':True,'inference_type':'body'},indent=2),encoding='utf-8')
print('PASS: real worker, selection, timeline, immutable source/raw')
