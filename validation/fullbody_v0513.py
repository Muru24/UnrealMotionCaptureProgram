from pathlib import Path
import json,subprocess
from app.knee_job import load_context,digest
from app.candidate_job import latest_selection,choose
from app.fullbody_job import ensure_fullbody,write

ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'validation/sam2/fullbody-v0513'

def main():
    DEST.mkdir(parents=True,exist_ok=True);results=[];context=None
    for folder in sorted((ROOT/'outputs').glob('Norma_sam3d_*')):
        if not all((folder/name).is_file() for name in ('sam-request.json','sam3d.json','report.json')):continue
        request=json.loads((folder/'sam-request.json').read_text(encoding='utf-8'));source=Path(request['source'])
        raw,source_hash,_=load_context(folder,source);selection=latest_selection(folder,source_hash)
        if selection is None:continue
        frozen={str(p):digest(p) for p in (source,folder/'sam3d.json',selection/'selected-joints.json',selection/'candidates.json')}
        path,state=ensure_fullbody(folder,source,selection,raw,source_hash)
        assert all(digest(Path(p))==h for p,h in frozen.items())
        packet=json.loads(path.read_text(encoding='utf-8'));assert packet['summary']['frames_with_four_candidates']==len(raw['frames'])
        results.append({'folder':folder.name,'selection':selection.name,'status':state,'summary':packet['summary'],'raw_and_selected_unchanged':True})
        context=(folder,source,raw,source_hash)
        print(json.dumps(results[-1]),flush=True)
    assert context is not None
    folder,source,raw,source_hash=context;out=DEST/'fresh-window';out.mkdir(exist_ok=True)
    request={'source':str(source),'source_sha256':source_hash,'start':60,'end_exclusive':68,'frames':raw['frames']}
    write(out/'request.json',request)
    if not (out/'candidates.json').is_file():
        print('Fresh GPU candidates: Norma frames 60..67 (24 inferences)',flush=True)
        with (out/'runtime.log').open('w',encoding='utf-8') as log:
            subprocess.run([str(ROOT/'.validation/sam3d/env/Scripts/python.exe'),'-u',str(ROOT/'app/candidate_worker.py'),str(out)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=True)
    data=json.loads((out/'candidates.json').read_text(encoding='utf-8'));assert [r['frame_index'] for r in data['frames']]==list(range(60,68))
    assert data['joint_names']==raw['joint_names']
    assert all(set(r['candidates'])=={'observed','tight','stable-flip'} for r in data['frames'])
    variants={r['frame_index']:r['candidates'] for r in data['frames']};rows,_=choose(raw,variants)
    write(out/'selected-joints.json',{'schema':'candidate_joint_selection_not_mhr_animation',
        'source_sha256':source_hash,'raw_sha256':digest(folder/'sam3d.json'),'video':raw['video'],'frames':rows})
    path,state=ensure_fullbody(folder,source,out,raw,source_hash)
    packet=json.loads(path.read_text(encoding='utf-8'));assert packet['summary']['frames_with_four_candidates']==8
    assert packet['summary']['candidate_count']==len(raw['frames'])+24
    results.append({'fresh_gpu_window':[60,68],'summary':packet['summary'],'outside_window':'baseline_only_not_new_inference','file':str(path)})
    write(DEST/'verification.json',{'version':'0.5.13','existing_full_sequences':results[:-1],'fresh_window':results[-1],
        'tracking_recomputed':False,'new_candidate_gpu_inferences':24,'raw_rotations_replaced':False,'m2_pass':False})
    print(json.dumps(results[-1]),flush=True)

if __name__=='__main__':main()
