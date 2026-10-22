from pathlib import Path
from collections import Counter
import json
from app.knee_job import load_context,digest
from app.candidate_job import latest_selection
from app.fullbody_job import ensure_fullbody,write
from app.joint_review_job import ensure_joint_review

ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'validation/sam2/joint-review-v0514'

def main():
    DEST.mkdir(parents=True,exist_ok=True);results=[]
    for folder in sorted((ROOT/'outputs').glob('Norma_sam3d_*')):
        if not all((folder/name).is_file() for name in ('sam-request.json','sam3d.json','report.json')):continue
        request=json.loads((folder/'sam-request.json').read_text(encoding='utf-8'));source=Path(request['source'])
        raw,source_hash,_=load_context(folder,source);selection=latest_selection(folder,source_hash)
        if selection is None:continue
        packet,_=ensure_fullbody(folder,source,selection,raw,source_hash)
        frozen={str(p):digest(p) for p in (source,folder/'sam3d.json',selection/'selected-joints.json',packet)}
        path,state=ensure_joint_review(folder,source,packet,source_hash)
        assert all(digest(Path(p))==h for p,h in frozen.items())
        report=json.loads(path.read_text(encoding='utf-8'));parts=Counter(part for row in report['frames'] for part in row['review_parts'])
        sample=[]
        for i in (0,6,12,24,58,60,62,66,70,74):
            row=report['frames'][i]
            sample.append({'frame':i,'parts':row['review_parts'],'leg_reasons':{str(j):row['joints'][j]['reasons'] for j in (9,10,11,12,13,14)}})
        results.append({'folder':folder.name,'selection':selection.name,'status':state,'summary':report['summary'],
            'part_frame_counts':dict(parts),'sample':sample,'inputs_unchanged':True,'input_hashes':frozen})
        print(json.dumps(results[-1],ensure_ascii=False),flush=True)
    assert len(results)==2
    write(DEST/'verification.json',{'version':'0.5.14','results':results,'new_gpu_inferences':0,'pose_replaced':False,'m2_pass':False})

if __name__=='__main__':main()
