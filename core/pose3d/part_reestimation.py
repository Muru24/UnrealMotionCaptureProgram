"""Selective two-bone proposals and temporal selection. Native rotations stay raw."""
import numpy as np
from core.pose3d.manual_leg_geometry import fit_camera,project

PARTS={'left_arm':(5,7,62,list(range(42,62))), 'right_arm':(6,8,41,list(range(21,41))),
       'left_leg':(9,11,13,[15,16,17]),'right_leg':(10,12,14,[18,19,20])}
AUXILIARY={'left_arm':{63:7,65:7},'right_arm':{64:8,66:8}}

def editable_joints(part):
    _,middle,end,children=PARTS[part]
    return [middle,end]+children+list(AUXILIARY.get(part,{}))

def key(row):return (row['target_id'],row['tracking_segment'],row['scene_index'],row.get('pose_track_start'))

def make_plan(packet,review,cancelled=lambda:False):
    frames=packet['frames'];n=len(frames);w,h=packet['video']['width'],packet['video']['height']
    if len(review['frames'])!=n:raise ValueError('Part review timeline differs.')
    targets={name:{} for name in PARTS}
    for req in review['repair_requests']:
        if req['part'] not in PARTS:continue
        a,b,lo,hi=(req[k] for k in ('start','end_exclusive','context_start','context_end_exclusive'))
        if not 0<=lo<=a<b<=hi<=n:raise ValueError('Invalid part repair range.')
        expected=tuple(req[k] for k in ('target_id','tracking_segment','scene_index','pose_track_start'))
        if any(key(row)!=expected for row in review['frames'][lo:hi]):raise ValueError('Part context crosses tracking boundary.')
        for i in range(a,b):targets[req['part']][i]=(lo,hi)
    rois={};target_rows=[]
    for i,row in enumerate(frames):
        if cancelled():raise KeyboardInterrupt
        if row['status']!='model_estimates' or row['selected_candidate'] is None:continue
        current=np.asarray(row['candidates'][row['selected_candidate']]['image_joints']);boxes={};parts=[]
        for family in ('arm','leg'):
            requested=[name for name in PARTS if family in name and i in targets[name]]
            if not requested:continue
            lo=min(targets[name][i][0] for name in requested);hi=max(targets[name][i][1] for name in requested)
            indices=[5,6,9,10,7,8,41,62,69] if family=='arm' else [5,6,9,10,11,12,13,14,15,16,17,18,19,20]
            roots=[5,6] if family=='arm' else [9,10];center=current[roots].mean(axis=0);points=[]
            for neighbor in frames[lo:hi]:
                candidate=neighbor['candidates'].get(neighbor['selected_candidate'])
                if candidate is None:continue
                p=np.asarray(candidate['image_joints']);points.append(p[indices]+center-p[roots].mean(axis=0))
            if not points:continue
            points=np.concatenate(points);low=points.min(axis=0);high=points.max(axis=0)
            span=np.maximum(high-low,[w*.12,h*.12]);box=np.r_[low-span*.18,high+span*.18]
            bbox=np.asarray(row['person_bbox']);size=bbox[2:]-bbox[:2]
            box=np.r_[np.maximum(box[:2],bbox[:2]-size*.2),np.minimum(box[2:],bbox[2:]+size*.2)]
            box=np.clip(box,[0,0,0,0],[w,h,w,h])
            if np.any(box[2:]-box[:2]<16):continue
            boxes[family+'-context']=box.tolist();parts.extend(requested)
        if boxes:rois[str(i)]=boxes;target_rows.append({'frame_index':i,'parts':parts})
    return {'rois':rois,'targets':target_rows,'inference_count':sum(len(v) for v in rois.values()),
            'limits':['spatial_per_frame_SAM3D_not_temporal_neural_model','neighbor_frames_define_ROI_and_sequence_cost',
                      'torso_requests_are_not_automatically_repaired']}

def proposal(base,candidate,part,camera,lengths,width,height):
    root,middle,end,children=PARTS[part];q=np.asarray(base['world_joints'],float);p=np.asarray(base['image_joints'],float)
    fresh=np.asarray(candidate['world_joints'],float);image=np.asarray(candidate['image_joints'],float)
    if fresh.shape!=(70,3) or image.shape!=(70,2) or not np.isfinite(fresh).all() or not np.isfinite(image).all():raise ValueError('invalid_candidate')
    diagonal=max(np.linalg.norm(np.ptp(p[[5,6,9,10]],axis=0)),1.)
    if np.linalg.norm(image[root]-p[root])>max(18.,diagonal*.15):raise ValueError('body_attachment_conflict')
    if np.any(image[[middle,end]]<0) or np.any(image[[middle,end]]>=[width,height]):raise ValueError('candidate_endpoint_outside_frame')
    upper=fresh[middle]-fresh[root];lower=fresh[end]-fresh[middle]
    lu,ll=np.linalg.norm(upper),np.linalg.norm(lower)
    if min(lu,ll,*lengths)<1e-6 or not np.all((np.asarray([lu,ll])/lengths>=.6)&(np.asarray([lu,ll])/lengths<=1.6)):raise ValueError('candidate_bone_length_conflict')
    result=q.copy();result[middle]=q[root]+upper/lu*lengths[0];result[end]=result[middle]+lower/ll*lengths[1]
    for child in children:result[child]=result[end]+fresh[child]-fresh[end]
    for child,anchor in AUXILIARY.get(part,{}).items():result[child]=result[anchor]+fresh[child]-fresh[anchor]
    editable=editable_joints(part);pixels=p.copy();pixels[editable]=project(result[editable],camera)
    error=float(np.mean(np.linalg.norm(pixels[[middle,end]]-image[[middle,end]],axis=1)))
    if error>max(12.,min(30.,diagonal*.12)):raise ValueError('fixed_body_projection_conflict')
    return {'world_joints':result,'image_joints':pixels,'projection_error_pixels':error}

def combine(packet,review,plan,fresh,support=lambda i,p:0.,cancelled=lambda:False,region_cost=lambda i,p:0.):
    frames=packet['frames'];video=packet['video'];n=len(frames)
    poses=[r['candidates'].get(r['selected_candidate']) for r in frames]
    requested={name:set() for name in PARTS}
    for r in plan['targets']:
        for part in r['parts']:requested[part].add(r['frame_index'])
    output=[{'frame_index':i,'world_joints':None if p is None else np.asarray(p['world_joints']).copy(),
             'image_joints':None if p is None else np.asarray(p['image_joints']).copy(),'changed_parts':[],
             'provenance':'baseline_preserved' if p else 'unavailable'} for i,p in enumerate(poses)]
    cameras={};events=[];summaries=[]
    for part,(root,middle,end,children) in PARTS.items():
        start=0
        while start<n:
            if poses[start] is None:start+=1;continue
            stop=start+1
            while stop<n and poses[stop] is not None and key(review['frames'][stop])==key(review['frames'][start]):stop+=1
            if not any(i in requested[part] for i in range(start,stop)):start=stop;continue
            q=np.asarray([poses[i]['world_joints'] for i in range(start,stop)])
            lengths=np.median(np.stack((np.linalg.norm(q[:,middle]-q[:,root],axis=1),np.linalg.norm(q[:,end]-q[:,middle],axis=1)),axis=1),axis=0)
            scale=max(float(np.median(np.linalg.norm((q[:,5]+q[:,6]-q[:,9]-q[:,10])/2,axis=1))),1e-6)
            pools=[];costs=[]
            for i in range(start,stop):
                if cancelled():raise KeyboardInterrupt
                base=poses[i];bq=np.asarray(base['world_joints']);bp=np.asarray(base['image_joints'])
                options=[{'world_joints':bq,'image_joints':bp,'variant':'baseline'}]
                if i in requested[part]:
                    if i not in cameras:
                        try:cameras[i]=fit_camera(bq,bp,video['width'],video['height'])
                        except ValueError:cameras[i]=None
                    if cameras[i] is not None:
                        family='arm' if 'arm' in part else 'leg'
                        candidates=[('fresh_'+family,c) for name,c in fresh.get(i,{}).items() if name==family+'-context']
                        candidates += [('existing_'+name,c) for name,c in frames[i]['candidates'].items() if name!=frames[i]['selected_candidate']]
                        for name,candidate in candidates:
                            try:
                                o=proposal(base,candidate,part,cameras[i],lengths,video['width'],video['height'])
                                if support(i,o['image_joints'][[middle,end]])>support(i,bp[[middle,end]])+.25:raise ValueError('mask_support_worse')
                                options.append(dict(o,variant=name))
                            except ValueError as error:events.append({'frame':i,'part':part,'variant':name,'rejected':str(error)})
                    else:events.append({'frame':i,'part':part,'rejected':'baseline_camera_fit_failed'})
                unary=[]
                expected=None
                if i>start and i+1<stop:
                    expected=sum(np.asarray(poses[j]['world_joints'])[[middle,end]]-np.asarray(poses[j]['world_joints'])[root] for j in (i-1,i+1))/2
                reference=np.median(np.array([c['image_joints'] for c in frames[i]['candidates'].values()])[:,[middle,end]],axis=0)
                diagonal=max(np.linalg.norm(np.subtract(frames[i]['person_bbox'][2:],frames[i]['person_bbox'][:2])),1.)
                for option in options:
                    local=option['world_joints'][[middle,end]]-option['world_joints'][root]
                    temporal=0 if expected is None else min(float(np.mean(np.linalg.norm(local-expected,axis=1))/scale),3.)
                    consensus=float(np.mean(np.linalg.norm(option['image_joints'][[middle,end]]-reference,axis=1))/diagonal)
                    length=np.array([np.linalg.norm(option['world_joints'][middle]-option['world_joints'][root]),np.linalg.norm(option['world_joints'][end]-option['world_joints'][middle])])
                    shape=float(np.mean(np.abs(np.log(np.maximum(length,1e-6)/np.maximum(lengths,1e-6)))))
                    accessory=float(region_cost(i,option['image_joints'][[middle,end]]))
                    if not np.isfinite(accessory) or not 0<=accessory<=.2:raise ValueError('Invalid accessory soft cost.')
                    unary.append(.4*temporal+.2*consensus+.25*shape+.35*support(i,option['image_joints'][[middle,end]])+.04*(option['variant']!='baseline')+accessory)
                pools.append(options);costs.append(unary)
            def transition(a,b):
                x=a['world_joints'][[middle,end]]-a['world_joints'][root];y=b['world_joints'][[middle,end]]-b['world_joints'][root]
                return .3*min(float(np.mean(np.linalg.norm(y-x,axis=1))/scale),3.)+.025*(a['variant']!=b['variant'])
            cost=np.asarray(costs[0]);backs=[]
            for t in range(1,len(pools)):
                edges=np.array([[old+transition(a,b) for b in pools[t]] for old,a in zip(cost,pools[t-1])])
                backs.append(np.argmin(edges,axis=0));cost=np.asarray(costs[t])+np.min(edges,axis=0)
            path=[int(np.argmin(cost))]
            for back in reversed(backs):path.append(int(back[path[-1]]))
            path=path[::-1];baseline=sum(row[0] for row in costs)+sum(transition(pools[t-1][0],pools[t][0]) for t in range(1,len(pools)))
            best=float(np.min(cost));changed=sum(k!=0 for k in path)
            accepted=changed>0 and baseline-best>.03*changed
            summaries.append({'part':part,'start':start,'end_exclusive':stop,'baseline_cost':float(baseline),'path_cost':best,'accepted_sequence':accepted})
            if accepted:
                editable=editable_joints(part)
                for i,k in enumerate(path,start):
                    if k==0:continue
                    option=pools[i-start][k]
                    output[i]['world_joints'][editable]=option['world_joints'][editable]
                    output[i]['image_joints'][editable]=option['image_joints'][editable]
                    output[i]['changed_parts'].append({'part':part,'variant':option['variant']})
                    output[i]['provenance']='part_model_reestimate'
            start=stop
    for i,row in enumerate(output):
        if poses[i] is None:continue
        editable={j for change in row['changed_parts'] for j in editable_joints(change['part'])}
        fixed=[j for j in range(70) if j not in editable]
        np.testing.assert_array_equal(row['world_joints'][fixed],np.asarray(poses[i]['world_joints'])[fixed])
        np.testing.assert_array_equal(row['image_joints'][fixed],np.asarray(poses[i]['image_joints'])[fixed])
        row['world_joints']=row['world_joints'].tolist();row['image_joints']=row['image_joints'].tolist()
    return output,{'changed_frames':[r['frame_index'] for r in output if r['changed_parts']],
        'changed_part_frames':sum(len(r['changed_parts']) for r in output),'sequences':summaries,'rejections':events,
        'limits':['proxy_cost_improvement_is_not_joint_accuracy','all_models_can_agree_on_cloth',
                  'body_attachments_are_fixed_not_reestimated','no_MHR_rotations_replaced']}
