from pathlib import Path
from collections import Counter
import json,numpy as np,sys
from app.knee_job import load_context,digest
from app.candidate_job import latest_selection
from app.fullbody_job import ensure_fullbody,write
from app.joint_review_job import ensure_joint_review
from app.part_reestimate_job import run_part_reestimation,latest_part_result,mask_support,render
from core.pose3d.part_reestimation import combine

ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'validation/sam2/parts-v0515'

def main():
    DEST.mkdir(parents=True,exist_ok=True)
    folder=ROOT/'outputs/Norma_sam3d_20261019_165800_c118ce5d'
    source=Path(json.loads((folder/'sam-request.json').read_text(encoding='utf-8'))['source'])
    raw,source_hash,_=load_context(folder,source);selection=latest_selection(folder,source_hash)
    packet_path,_=ensure_fullbody(folder,source,selection,raw,source_hash)
    review,_=ensure_joint_review(folder,source,packet_path,source_hash)
    frozen={str(p):digest(p) for p in (source,folder/'sam3d.json',selection/'selected-joints.json',packet_path,review)}
    out=latest_part_result(folder,source_hash,selection,review)
    if out is None:out,report=run_part_reestimation(folder,source,selection,review,phase=lambda text:print(text,flush=True))
    else:report=json.loads((out/'report.json').read_text(encoding='utf-8'))
    if '--recombine' in sys.argv:
        packet=json.loads(packet_path.read_text(encoding='utf-8'));diagnosis=json.loads(review.read_text(encoding='utf-8'));plan=json.loads((out/'plan.json').read_text(encoding='utf-8'))
        fresh=json.loads((out/'inference/candidates.json').read_text(encoding='utf-8'))
        support,_=mask_support(folder,packet,diagnosis,lambda:False)
        rows,details=combine(packet,diagnosis,plan,{r['frame_index']:r['candidates'] for r in fresh['frames']},support)
        data=json.loads((out/'part-joints.json').read_text(encoding='utf-8'));data.update(frames=rows,details=details);write(out/'part-joints.json',data)
        render(source,out/'part-overlay.partial.mp4',packet,rows,lambda:False,lambda *a:None);(out/'part-overlay.partial.mp4').replace(out/'part-overlay.mp4')
        report.update(changed_frames=details['changed_frames'],changed_part_frames=details['changed_part_frames']);write(out/'report.json',report)
    data=json.loads((out/'part-joints.json').read_text(encoding='utf-8'));packet=json.loads(packet_path.read_text(encoding='utf-8'))
    requested={r['frame_index']:set(r['parts']) for r in json.loads((out/'plan.json').read_text(encoding='utf-8'))['targets']}
    parts=Counter();variants=Counter()
    for old,new in zip(packet['frames'],data['frames']):
        pose=old['candidates'].get(old['selected_candidate'])
        if pose is None:assert new['world_joints'] is None;continue
        for change in new['changed_parts']:
            assert change['part'] in requested[new['frame_index']];parts[change['part']]+=1;variants[change['variant']]+=1
        fixed=[5,6,9,10,69]
        np.testing.assert_array_equal(np.asarray(new['world_joints'])[fixed],np.asarray(pose['world_joints'])[fixed])
        np.testing.assert_array_equal(np.asarray(new['image_joints'])[fixed],np.asarray(pose['image_joints'])[fixed])
    assert all(digest(Path(p))==h for p,h in frozen.items())
    result={'version':'0.5.15','folder':folder.name,'selection':selection.name,'part_directory':out.name,
        'frames':len(data['frames']),'inference_count':report['inference_count'],'changed_frames':report['changed_frames'],
        'changed_part_counts':dict(parts),'changed_variant_counts':dict(variants),'inputs_unchanged':True,
        'body_attachments_unchanged':True,'unrequested_parts_unchanged':True,'m2_pass':False,
        'limits':['proxy_cost_improvement_not_accuracy_ground_truth','initial_unflagged_frames_not_requested']}
    write(DEST/'verification.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
