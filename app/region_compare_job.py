"""Explicit CPU accessory-cost comparison using existing hypotheses only."""
from pathlib import Path
from uuid import uuid4
import copy,argparse,numpy as np,cv2
from app.completion_job import read
from app.fullbody_job import write
from app.knee_job import load_context,digest
from app.internal_mask_job import local_file,load_mask
from app.part_reestimate_job import signatures,mask_support,render
from core.pose2d.region_evidence import reconcile,soft_cost
from core.pose3d.part_reestimation import combine,PARTS,editable_joints


def run_compare(folder,source,selection,parts,internal,cancelled=lambda:False,progress=lambda *a:None):
    folder=Path(folder).resolve();selection=Path(selection);parts=Path(parts);internal=Path(internal)
    raw,source_hash,_=load_context(folder,source);review_path=selection/'joint-review.json'
    expected=signatures(folder,source_hash,selection,review_path)
    for p in (selection,parts,internal):
        if p.resolve().parent!=folder:raise ValueError('Comparison inputs must belong to the same result.')
    packet=read(selection/'fullbody-candidates.json');review=read(review_path);old=read(parts/'part-joints.json')
    if any(old.get(k)!=v for k,v in expected.items()) or read(parts/'report.json').get('status')!='completed_with_estimates':raise ValueError('Stale part input.')
    req=read(internal/'request.json');tracking=read(folder/'sam-tracking.json')
    if read(internal/'report.json').get('status')!='completed_diagnostic' or req['source_sha256']!=source_hash or req['raw_sha256']!=expected['raw_sha256'] or req['tracking_sha256']!=digest(folder/'sam-tracking.json'):raise ValueError('Stale region input.')
    plan=read(parts/'plan.json');data=read(internal/'regions.json');fresh_data=read(parts/'inference/candidates.json') if plan['inference_count'] else {'frames':[]}
    fresh={r['frame_index']:r['candidates'] for r in fresh_data['frames']}
    support,manifest=mask_support(folder,packet,review,cancelled)
    watched=[Path(source),folder/'sam3d.json',folder/'sam-tracking.json',selection/'selected-joints.json',selection/'fullbody-candidates.json',review_path,parts/'part-joints.json',parts/'plan.json',internal/'request.json',internal/'regions.json',internal/'report.json']
    if plan['inference_count']:watched.append(parts/'inference/candidates.json')
    watched.extend(Path(p) for p,h in manifest if h is not None)
    w=packet['video']['width'];h=packet['video']['height'];previous={};regions={};diagnostics=[]
    if [r['frame_index'] for r in data['frames']]!=list(range(req['start'],req['end_exclusive'])):raise ValueError('Region timeline differs.')
    keys=set()
    for row in data['frames']:
        if cancelled():raise KeyboardInterrupt
        i=row['frame_index'];track=tracking['frames'][i]
        if track['roi'] is None or track['tracking']['state']!='tracked':raise ValueError('Region person unavailable.')
        keys.add((track['tracking'].get('track_id'),track.get('tracking_segment'),track.get('scene',{}).get('index'),raw['frames'][i].get('tracking_segment')))
        path=local_file(folder,track['mask']['file']);watched.append(path);person=load_mask(path,w,h);regions[i]={}
        if set(row['objects'])!={o['name'] for o in req['objects']}:raise ValueError('Region names differ.')
        for name,obj in row['objects'].items():
            path=local_file(internal,obj['file']);watched.append(path)
            mask,info=reconcile(load_mask(path,w,h),person,obj['object_logit'],previous.get(name));previous[name]=mask
            regions[i][name]=(mask,info)
            diagnostics.append({'frame_index':i,'name':name,**info})
    if len(keys)!=1:raise ValueError('Region interval crosses tracking boundary.')
    hashes={str(p):digest(p) for p in watched}
    baseline,_=combine(packet,review,plan,fresh,support,cancelled)
    # A different upstream algorithm must not masquerade as a clothing-only A/B.
    for a,b in zip(baseline,old['frames']):
        if a!=b:raise ValueError('Recomputed baseline differs from stored part output.')
    rows,details=combine(packet,review,plan,fresh,support,cancelled,region_cost=lambda i,p:soft_cost(p,regions.get(i,{})))
    changed=[i for i,(a,b) in enumerate(zip(rows,baseline)) if a['world_joints']!=b['world_joints']]
    out=folder/('region_compare_'+uuid4().hex[:8]);out.mkdir();status='failed'
    try:
        before=copy.deepcopy(packet)
        for frame,row in zip(before['frames'],baseline):
            frame['selected_candidate']='before';frame['candidates']={'before':row} if row['world_joints'] is not None else {}
        display=copy.deepcopy(rows)
        for row,base in zip(display,baseline):
            row['changed_parts']=[]
            if row['world_joints'] is not None:
                for part in PARTS:
                    indices=editable_joints(part)
                    if not np.array_equal(np.asarray(row['world_joints'])[indices],np.asarray(base['world_joints'])[indices]):row['changed_parts'].append({'part':part})
        render(source,out/'region-candidate-overlay.partial.mp4',before,display,cancelled,progress,titles=('EXISTING PART ESTIMATES','ACCESSORY SOFT COST / EXPERIMENT'))
        if cancelled():raise KeyboardInterrupt
        if any(digest(p)!=sha for p,sha in hashes.items()):raise ValueError('Comparison inputs changed.')
        write(out/'region-candidate-joints.json',{'schema':'accessory_cost_comparison_mhr70_v1',**expected,'frames':rows,'video':packet['video'],'coordinates':packet['coordinates'],'details':details})
        write(out/'region-evidence.json',{'frames':diagnostics,'input_hashes':hashes,'hard_exclusion':False,'person_tracking_modified':False})
        (out/'region-candidate-overlay.partial.mp4').replace(out/'region-candidate-overlay.mp4');status='completed_experiment'
    except KeyboardInterrupt:status='cancelled';raise
    finally:
        (out/'region-candidate-overlay.partial.mp4').unlink(missing_ok=True)
        write(out/'report.json',{'status':status,**expected,'frames_processed':len(rows),'changed_frames_vs_parts':changed,
            'automatic_pipeline_modified':False,'new_gpu_inference':0,'limits':['overlap_is_not_anatomical_error','model_candidates_can_all_be_wrong','body_and_requested_parts_only_as_original_plan']})
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('folder','source','selection','parts','internal'):p.add_argument(name)
    a=p.parse_args();print(run_compare(a.folder,a.source,a.selection,a.parts,a.internal))
