"""Gate actual independent 2D estimates, then compare native positive-point decoding."""
from pathlib import Path
from uuid import uuid4
from collections import OrderedDict
import argparse,copy,numpy as np
from app.knee_job import load_context,digest
from app.completion_job import read
from app.fullbody_job import write
from app.internal_mask_job import local_file,load_mask
from app.part_reestimate_job import render
from app.leg_reestimate_job import gpu_child
from core.pose3d.observation_gate import gate_observations,assess_refinement
from core.pose3d.part_reestimation import PARTS


def run_guided(folder,source,independent_dir,internal_dir,cancelled=lambda:False,progress=lambda *a:None):
    folder=Path(folder).resolve();independent_dir=Path(independent_dir).resolve();internal_dir=Path(internal_dir).resolve()
    if any(p.parent!=folder for p in (independent_dir,internal_dir)):raise ValueError('Guidance inputs must belong to same result.')
    raw,source_hash,_=load_context(folder,source);tracking=read(folder/'sam-tracking.json');independent=read(independent_dir/'independent-2d.json')
    previous=read(independent_dir/'report.json');req=read(internal_dir/'request.json')
    if previous.get('status')!='completed_independent_model_comparison' or previous['source_sha256']!=source_hash or req['source_sha256']!=source_hash or req['raw_sha256']!=digest(folder/'sam3d.json') or req['tracking_sha256']!=digest(folder/'sam-tracking.json') or read(internal_dir/'report.json').get('status')!='completed_diagnostic':raise ValueError('Stale independent observation inputs.')
    # Check the extraction hash recorded by the independent comparison, too.
    if previous['input_hashes'].get(str(folder/'sam3d.json'))!=digest(folder/'sam3d.json'):raise ValueError('Independent raw hash differs.')
    region_rows={r['frame_index']:r for r in read(internal_dir/'regions.json')['frames']};w=raw['video']['width'];h=raw['video']['height'];cache=OrderedDict()
    watched=[Path(source),folder/'sam3d.json',folder/'sam-tracking.json',independent_dir/'independent-2d.json',independent_dir/'report.json',internal_dir/'request.json',internal_dir/'regions.json',internal_dir/'report.json'];mask_hashes={}
    def support(i,point):
        if i not in cache:
            row=tracking['frames'][i]
            if row.get('roi') is None or row['tracking']['state']!='tracked':return None
            path=local_file(folder,row['mask']['file']);mask_hashes[str(path)]=digest(path);person=load_mask(path,w,h);garment=np.zeros_like(person)
            # Prompted accessories apply only within their original scene and track segment.
            seed=req['seed_frame'];same=raw['frames'][i].get('tracking_segment')==raw['frames'][seed].get('tracking_segment') and raw['frames'][i].get('scene',{}).get('index',0)==raw['frames'][seed].get('scene',{}).get('index',0)
            for obj in region_rows.get(i,{}).get('objects',{}).values() if same else []:
                path=local_file(internal_dir,obj['file']);mask_hashes[str(path)]=digest(path)
                if obj['object_logit']>0:garment|=load_mask(path,w,h)
            cache[i]=(person,garment)
            while len(cache)>8:cache.popitem(last=False)
        person,garment=cache[i];x,y=np.round(point).astype(int)
        if not 0<=x<w or not 0<=y<h:return ['outside_image']
        return ([] if person[y,x] else ['outside_tracked_person'])+(['accessory_overlap_or_occlusion'] if garment[y,x] else [])
    gate=gate_observations(raw,independent,support,cancelled)
    hashes={str(p):digest(p) for p in watched};hashes.update(mask_hashes)
    eligible=sorted(gate['frames']);focus=[i for i in eligible if req['start']<=i<req['end_exclusive']]
    rest=[i for i in eligible if i not in focus];selected=focus[:12]
    if rest and len(selected)<12:selected+= [rest[k] for k in np.unique(np.linspace(0,len(rest)-1,min(12-len(selected),len(rest))).round().astype(int))]
    selected=sorted(selected);out=folder/('guided_'+uuid4().hex[:8]);out.mkdir();status='failed';results=[];infer=out/'inference';infer.mkdir()
    try:
        write(out/'observation-gate.json',gate)
        if not selected:status='completed_no_eligible_hints';return out
        prompts={str(i):{'guided-body':gate['frames'][i]} for i in selected}
        request={'source':str(Path(source).resolve()),'frames':raw['frames'],'start':selected[0],'end_exclusive':selected[-1]+1,
            'leg_rois':{str(i):{'body-control':raw['frames'][i]['roi'],'guided-body':raw['frames'][i]['roi']} for i in selected},
            'inference_types':{'body-control':'body','guided-body':'body'},'point_prompts':prompts}
        write(infer/'request.json',request);hashes[str(infer/'request.json')]=digest(infer/'request.json')
        gpu_child('leg_candidate_worker.py',infer,'progress.json',cancelled,progress)
        data=read(infer/'candidates.json')
        if data['joint_names']!=raw['joint_names'] or [r['frame_index'] for r in data['frames']]!=selected:raise ValueError('Guided candidate timeline differs.')
        by_frame={r['frame_index']:r['candidates'] for r in data['frames']};packet={'video':raw['video'],'frames':[]};rows=[]
        for i in range(len(raw['frames'])):
            variants=by_frame.get(i,{})
            if variants and set(variants)!={'body-control','guided-body'}:raise ValueError('Guided candidate variants differ.')
            control=variants.get('body-control');guided=variants.get('guided-body');chosen=control;changed=False
            if guided is not None:
                review=assess_refinement(control,guided,gate['frames'][i]);results.append({'frame_index':i,**review})
                if review['accepted_as_model_hypothesis']:chosen=guided;changed=True
            packet['frames'].append({'frame_index':i,'selected_candidate':'body-control','candidates':variants})
            rows.append({'frame_index':i,'world_joints':None if chosen is None else chosen['world_joints'],
                'image_joints':None if chosen is None else chosen['image_joints'],'changed_parts':[{'part':p} for p in PARTS] if changed else [],
                'body_reference_hypothesis':changed,'provenance':'independent_point_conditioned_model_estimate' if changed else 'body_control_or_unsampled'})
        render(source,out/'guided-comparison.partial.mp4',packet,rows,cancelled,progress,titles=('BODY DECODER CONTROL','GATED POINT HINT / ESTIMATE'))
        if cancelled():raise KeyboardInterrupt
        if any(digest(p)!=sha for p,sha in hashes.items()):raise ValueError('Guidance inputs changed.')
        write(out/'guided-joints.json',{'schema':'gated_point_guidance_mhr70_comparison_v1','frames':rows,'video':raw['video'],
            'source_sha256':source_hash,'joint_names':data['joint_names'],'native_rotations_modified':False})
        (out/'guided-comparison.partial.mp4').replace(out/'guided-comparison.mp4');status='completed_guidance_experiment'
    except KeyboardInterrupt:status='cancelled';raise
    finally:
        (out/'guided-comparison.partial.mp4').unlink(missing_ok=True)
        write(out/'report.json',{'status':status,'source_sha256':source_hash,'input_hashes':hashes,'eligible_frames':eligible,
            'sampled_frames':selected,'focus_eligible_frames':focus,'results':results,'automatic_pipeline_modified':False,
            'limits':['hints_are_unverified_model_observations','reprojection_match_is_not_anatomical_accuracy',
                      'both_control_and_guidance_use_body_decoder_no_hand_refinement','unsampled_frames_are_not_filled']})
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('folder','source','independent','internal'):p.add_argument(name)
    a=p.parse_args();print(run_guided(a.folder,a.source,a.independent,a.internal))
