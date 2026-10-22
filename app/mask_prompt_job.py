"""Controlled SAM3D mask conditioning A/B, no automatic output replacement."""
from pathlib import Path
from uuid import uuid4
import argparse,copy,cv2,numpy as np
from app.completion_job import read
from app.knee_job import load_context,digest
from app.fullbody_job import write
from app.internal_mask_job import local_file,load_mask
from app.leg_reestimate_job import gpu_child
from app.part_reestimate_job import render
from core.pose2d.mask_prompt import reduced_prompt
from core.pose3d.part_reestimation import PARTS


def run_mask_prompts(folder,source,internal,indices,cancelled=lambda:False,progress=lambda *a:None):
    folder=Path(folder).resolve();internal=Path(internal).resolve()
    if internal.parent!=folder:raise ValueError('Mask prompts must belong to same result.')
    raw,source_hash,_=load_context(folder,source);req=read(internal/'request.json');tracking=read(folder/'sam-tracking.json')
    if read(internal/'report.json')['status']!='completed_diagnostic' or req['source_sha256']!=source_hash or req['raw_sha256']!=digest(folder/'sam3d.json') or req['tracking_sha256']!=digest(folder/'sam-tracking.json'):raise ValueError('Stale prompt masks.')
    if not indices or indices!=sorted(set(indices)) or len(indices)>60 or any(type(i) is not int or not req['start']<=i<req['end_exclusive'] for i in indices):raise ValueError('Invalid prompt frame samples.')
    region_rows={r['frame_index']:r for r in read(internal/'regions.json')['frames']}
    w=raw['video']['width'];h=raw['video']['height'];watched=[Path(source),folder/'sam3d.json',folder/'sam-tracking.json',internal/'request.json',internal/'regions.json',internal/'report.json'];prepared={};keys=set()
    for i in indices:
        if cancelled():raise KeyboardInterrupt
        frame=raw['frames'][i];track=tracking['frames'][i]
        if frame.get('roi') is None or track.get('roi') is None or frame['tracking']['state']!='tracked' or track['tracking']['state']!='tracked':raise ValueError('Unobserved mask prompt frame.')
        keys.add((track['tracking'].get('track_id'),frame.get('tracking_segment'),track.get('scene',{}).get('index')))
        path=local_file(folder,track['mask']['file']);watched.append(path);person=load_mask(path,w,h);regions={}
        for name,obj in region_rows[i]['objects'].items():
            path=local_file(internal,obj['file']);watched.append(path);regions[name]=(load_mask(path,w,h),obj['object_logit'])
        reduced,info=reduced_prompt(person,regions);prepared[i]=(person,reduced,info)
    if len(keys)!=1:raise ValueError('Prompt sample crosses identity/scene boundary.')
    hashes={str(p):digest(p) for p in watched};out=folder/('mask_prompt_'+uuid4().hex[:8]);out.mkdir();infer=out/'inference';infer.mkdir();status='failed';rois={};mask_files={};summaries=[];results={}
    try:
        for i,(person,reduced,info) in prepared.items():
            roi=raw['frames'][i]['roi'];rois[str(i)]={'unconditioned':roi,'person-mask':roi};mask_files[str(i)]={}
            for name,mask in (('person-mask',person),('accessory-reduced',reduced)):
                if mask is None:continue
                path=Path('prompts')/f'{i:06d}-{name}.png';(infer/path).parent.mkdir(exist_ok=True)
                (infer/path).write_bytes(cv2.imencode('.png',mask.astype(np.uint8)*255)[1].tobytes())
                mask_files[str(i)][name]=path.as_posix();rois[str(i)][name]=roi
            summaries.append({'frame_index':i,**info})
        write(infer/'request.json',{'source':str(Path(source).resolve()),'start':indices[0],'end_exclusive':indices[-1]+1,
            'frames':raw['frames'],'leg_rois':rois,'mask_files':mask_files})
        gpu_child('leg_candidate_worker.py',infer,'progress.json',cancelled,progress)
        data=read(infer/'candidates.json')
        if data['joint_names']!=raw['joint_names'] or [r['frame_index'] for r in data['frames']]!=indices:raise ValueError('Mask-conditioned candidate timeline differs.')
        if any(set(r['candidates'])!=set(rois[str(r['frame_index'])]) for r in data['frames']):raise ValueError('Mask-conditioned variants differ.')
        by_frame={r['frame_index']:r['candidates'] for r in data['frames']};packet={'video':raw['video'],'frames':[]}
        for i in range(len(raw['frames'])):
            c=by_frame.get(i,{})
            packet['frames'].append({'frame_index':i,'selected_candidate':'unconditioned','candidates':c})
        for variant in ('person-mask','accessory-reduced'):
            rows=[]
            for i in range(len(raw['frames'])):
                c=by_frame.get(i,{}).get(variant)
                rows.append({'frame_index':i,'image_joints':None if c is None else c['image_joints'],
                    'world_joints':None if c is None else c['world_joints'],'changed_parts':[{'part':p} for p in PARTS] if c else [],
                    'body_reference_hypothesis':bool(c),'provenance':'mask_conditioned_model_estimate' if c else 'not_sampled_or_prompt_unavailable'})
            render(source,out/f'{variant}.partial.mp4',packet,rows,cancelled,progress,titles=('SAME ROI / NO MASK','SAME PIXELS / '+variant.upper()))
            write(out/f'{variant}-joints.json',{'schema':'mask_conditioned_mhr70_comparison_v1','source_sha256':source_hash,'frames':rows,'video':raw['video'],'model_estimates_only':True})
            results[variant]={'sampled_frames':sum(r['world_joints'] is not None for r in rows)}
        if cancelled():raise KeyboardInterrupt
        if any(digest(p)!=sha for p,sha in hashes.items()):raise ValueError('Mask prompt inputs changed.')
        for variant in results:(out/f'{variant}.partial.mp4').replace(out/f'{variant}.mp4')
        write(out/'prompt-summary.json',{'frames':summaries,'input_hashes':hashes,'pixels_unchanged':True,
            'mask_score_note':'estimator sets provided mask embedding score to1; not a calibrated confidence'})
        status='completed_mask_prompt_experiment'
    except KeyboardInterrupt:status='cancelled';raise
    finally:
        for variant in ('person-mask','accessory-reduced'):(out/f'{variant}.partial.mp4').unlink(missing_ok=True)
        write(out/'report.json',{'status':status,'source_sha256':source_hash,'input_hashes':hashes,'frames_processed':len(indices),
            'inference_count':sum(len(v) for v in rois.values()),'results':results,'automatic_pipeline_modified':False,
            'limits':['partial_masks_can_remove_real_body_cues','prompts_are_not_verified_body_segmentation','same_model_can_still_follow_cloth','unsampled_frames_are_not_filled']})
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('folder','source','internal'):p.add_argument(name)
    p.add_argument('--frames',type=int,nargs='+',required=True);a=p.parse_args()
    print(run_mask_prompts(a.folder,a.source,a.internal,a.frames))
