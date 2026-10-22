"""Generate comparison-only limb/body context hypotheses, retaining all inputs."""
from pathlib import Path
from uuid import uuid4
import argparse,copy,numpy as np
from app.completion_job import read
from app.knee_job import load_context,digest
from app.fullbody_job import write
from app.part_reestimate_job import signatures,render
from core.pose3d.temporal_hypotheses import generate
from core.pose3d.part_reestimation import PARTS,editable_joints


def run_temporal(folder,source,selection,baseline_dir,start,stop,cancelled=lambda:False,progress=lambda *a:None):
    folder=Path(folder).resolve();selection=Path(selection).resolve();baseline_dir=Path(baseline_dir).resolve()
    if selection.parent!=folder or baseline_dir.parent!=folder:raise ValueError('Temporal inputs must belong to same result.')
    raw,source_hash,_=load_context(folder,source);review_path=selection/'joint-review.json';expected=signatures(folder,source_hash,selection,review_path)
    path=baseline_dir/'region-candidate-joints.json'
    if not path.is_file():path=baseline_dir/'part-joints.json'
    data=read(path);report=read(baseline_dir/'report.json');packet=read(selection/'fullbody-candidates.json');review=read(review_path)
    if report.get('status') not in ('completed_experiment','completed_with_estimates') or any(data.get(k)!=v for k,v in expected.items()):raise ValueError('Stale temporal baseline.')
    if len(data['frames'])!=len(raw['frames']):raise ValueError('Temporal timeline differs.')
    watched=[Path(source),folder/'sam3d.json',selection/'selected-joints.json',selection/'fullbody-candidates.json',review_path,path,baseline_dir/'report.json']
    hashes={str(p):digest(p) for p in watched};out=folder/('temporal_'+uuid4().hex[:8]);out.mkdir();status='failed';results={}
    try:
        before=copy.deepcopy(packet)
        for frame,row in zip(before['frames'],data['frames']):
            frame['selected_candidate']='baseline';frame['candidates']={'baseline':row} if row['world_joints'] is not None else {}
        for name,body in (('limbs',False),('body-context',True)):
            rows,details=generate(packet,review,data,start,stop,body_context=body,cancelled=cancelled)
            display=copy.deepcopy(rows)
            for row,base in zip(display,data['frames']):
                row['changed_parts']=[]
                if row['world_joints'] is not None:
                    for part in PARTS:
                        indices=editable_joints(part)
                        if not np.array_equal(np.asarray(row['world_joints'])[indices],np.asarray(base['world_joints'])[indices]):row['changed_parts'].append({'part':part})
            render(source,out/f'{name}-hypothesis.partial.mp4',before,display,cancelled,progress,titles=('EXISTING ESTIMATES','UNOBSERVED '+name.upper()+' HYPOTHESIS'))
            write(out/f'{name}-hypothesis.json',{'schema':'unobserved_temporal_hypothesis_mhr70_v1',**expected,'video':packet['video'],
                'coordinates':packet['coordinates'],'frames':rows,'details':details,'hypothesis_only':True})
            results[name]={'changed_frames':details['changed_frames'],'accepted_hypotheses':sum('references' in e for e in details['events']),
                'body_reference_frames':sum(bool(r.get('body_reference_hypothesis')) for r in rows)}
        if cancelled():raise KeyboardInterrupt
        if any(digest(p)!=sha for p,sha in hashes.items()):raise ValueError('Temporal inputs changed.')
        for name in results:(out/f'{name}-hypothesis.partial.mp4').replace(out/f'{name}-hypothesis.mp4')
        status='completed_hypotheses'
    except KeyboardInterrupt:status='cancelled';raise
    finally:
        for name in ('limbs','body-context'):(out/f'{name}-hypothesis.partial.mp4').unlink(missing_ok=True)
        write(out/'report.json',{'status':status,**expected,'start':start,'end_exclusive':stop,'results':results,'input_hashes':hashes,
            'automatic_pipeline_modified':False,'new_gpu_inference':0,'hypothesis_only':True,'native_rotations_modified':False})
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('folder','source','selection','baseline'):p.add_argument(name)
    p.add_argument('--start',type=int,required=True);p.add_argument('--stop',type=int,required=True);a=p.parse_args()
    print(run_temporal(a.folder,a.source,a.selection,a.baseline,a.start,a.stop))
