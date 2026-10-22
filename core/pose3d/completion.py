"""Second-pass native-world completion. Estimated motion is never observation."""
from collections import Counter
import numpy as np
from core.video.limits import MAX_VIDEO_FRAMES

CHAINS=((11,13,15),(12,14,16),(23,25,27),(24,26,28))


def unit(v):
    norm=float(np.linalg.norm(v))
    return v/norm if norm>1e-8 else None


def leg_ik(root, target, bend, upper, lower):
    delta=target-root
    axis=unit(delta)
    if axis is None:axis=np.array([0.,1.,0.])
    distance=float(np.clip(np.linalg.norm(delta),abs(upper-lower)+1e-5,upper+lower-1e-5))
    perpendicular=unit(bend-axis*np.dot(bend,axis))
    if perpendicular is None:
        helper=np.array([1.,0.,0.]) if abs(axis[0])<.9 else np.array([0.,0.,1.])
        perpendicular=unit(helper-axis*np.dot(helper,axis))
    along=(upper*upper-lower*lower+distance*distance)/(2*distance)
    knee=root+axis*along+perpendicular*np.sqrt(max(0,upper*upper-along*along))
    return knee,root+axis*distance


def complete(document, tracking, cancelled=lambda:False, *, chains=CHAINS,
             leg_chains=CHAINS[2:], foot_pairs=((27,29),(27,31),(28,30),(28,32)),
             allow_model_priors=False):
    frames=document['frames'];fps=document['video']['fps'];n=len(frames)
    joint_count=len(document['joint_names'])
    leg_roots={c[0] for c in leg_chains}
    if not 0<n<=MAX_VIDEO_FRAMES or len(tracking['frames'])!=n or not 1<=fps<=240:
        raise ValueError('Invalid completion timeline.')
    points=np.full((n,joint_count,3),np.nan)
    visible=np.zeros((n,joint_count),bool);eligible=np.zeros(n,bool)
    segments=[f.get('tracking_segment',0) for f in frames]
    for t,(f,tr) in enumerate(zip(frames,tracking['frames'])):
        if f['frame_index']!=t or tr['frame_index']!=t or len(f['landmarks'])!=joint_count:
            raise ValueError('Frame/joint alignment differs.')
        eligible[t]=f['person_bbox'] is not None and tr['tracking']['state']=='tracked'
        for j,p in enumerate(f['landmarks']):
            xyz=[p[k] for k in ('x','y','z')]
            if all(isinstance(v,(int,float)) and np.isfinite(v) for v in xyz):
                points[t,j]=xyz
                visible[t,j]=eligible[t] and p['valid']
    states=np.where(visible,'observed','unresolved').astype(object)
    lengths={};directions={};suspects=[];calibration={}
    for chain in chains:
        for a,b in zip(chain,chain[1:]):
            vectors=points[:,b]-points[:,a]
            distances=np.linalg.norm(vectors,axis=1)
            samples=visible[:,a]&visible[:,b]&np.isfinite(distances)&(distances>.02)&(distances<1.5)
            calibration[f'{a}-{b}']='visible_model_predictions'
            if allow_model_priors and samples.sum()<8:
                samples=eligible&np.isfinite(distances)&(distances>.02)&(distances<1.5)
                calibration[f'{a}-{b}']='hidden_model_predictions'
            # Enough observations are required before making a length prior.
            if samples.sum()<8:continue
            length=float(np.median(distances[samples]));lengths[(a,b)]=length
            trusted=visible[:,a]&visible[:,b]
            suspicious=trusted&((distances>length*1.8)|(distances<length*.5))
            for t in np.flatnonzero(suspicious):
                visible[t,b]=False;states[t,b]='suspect';suspects.append([int(t),b,'bone_length_outlier'])
            direction=np.full((n,3),np.nan)
            for t in np.flatnonzero(visible[:,a]&visible[:,b]):
                u=unit(vectors[t])
                if u is not None:direction[t]=u
            # Interpolate directions, then reconstruct at the calibrated length.
            t=0
            while t<n:
                if np.isfinite(direction[t]).all():t+=1;continue
                start=t
                while t<n and not np.isfinite(direction[t]).all():t+=1
                end=t
                if (start>0 and end<n and (end-start)/fps<=.2 and eligible[start:end].all() and
                        all(s==segments[start-1] for s in segments[start-1:end+1])):
                    u,v=direction[start-1],direction[end]
                    if np.dot(u,v) > -.8:
                        for k in range(start,end):
                            direction[k]=unit((1-(k-start+1)/(end-start+1))*u+((k-start+1)/(end-start+1))*v)
                            states[k,b]='interpolated'
            directions[(a,b)]=direction
    suspect_set={(s[0],s[1]) for s in suspects}
    offsets={}
    leg_priors={};prior_calibration={}
    for hip,knee,ankle in leg_chains:
        mask=visible[:,hip]&visible[:,knee]&visible[:,ankle]
        prior_calibration[f'leg_{hip}']='visible_model_predictions'
        if allow_model_priors and mask.sum()<8:
            mask=eligible&np.isfinite(points[:,[hip,knee,ankle]]).all(axis=(1,2))
            prior_calibration[f'leg_{hip}']='hidden_model_predictions'
        if mask.sum()>=8:
            leg_priors[hip]=(np.median(points[mask,ankle]-points[mask,hip],axis=0),
                             np.median(points[mask,knee]-points[mask,hip],axis=0))
    for ankle,tip in foot_pairs:
        mask=visible[:,ankle]&visible[:,tip]
        prior_calibration[f'foot_{ankle}_{tip}']='visible_model_predictions'
        if allow_model_priors and mask.sum()<8:
            mask=eligible&np.isfinite(points[:,[ankle,tip]]).all(axis=(1,2))
            prior_calibration[f'foot_{ankle}_{tip}']='hidden_model_predictions'
        if mask.sum()>=8:offsets[(ankle,tip)]=np.median(points[mask,tip]-points[mask,ankle],axis=0)
    result=[];counts=Counter()
    for t,f in enumerate(frames):
        if cancelled():raise KeyboardInterrupt
        xyz=points[t].copy();available=visible[t].copy();sources=states[t].copy()
        if not eligible[t]:
            available[:]=False;sources[:]='unresolved'
        else:
            for chain in chains:
                for a,b in zip(chain,chain[1:]):
                    if not available[a] or (a,b) not in lengths:continue
                    direction=directions[(a,b)][t]
                    if not np.isfinite(direction).all() and available[b]:
                        projected=unit(xyz[b]-xyz[a])
                        if projected is not None:direction=projected
                    if np.isfinite(direction).all():
                        xyz[b]=xyz[a]+direction*lengths[(a,b)];available[b]=True
                        if sources[b]=='observed':
                            sources[b]='length_constrained' if sources[a] in ('observed','length_constrained') else 'estimated_parent_direction'
                    elif chain[0] in leg_roots:
                        # Long or one-sided leg gaps: explicit standing/FK prior,
                        # not interpolation and not claimed ground-contact IK.
                        prior=None
                        for k in range(t-1,max(-1,t-int(.2*fps)-1),-1):
                            if not eligible[k] or segments[k]!=segments[t]:break
                            if np.isfinite(directions[(a,b)][k]).all():
                                prior=directions[(a,b)][k];break
                        direction=prior if prior is not None else np.array([0.,1.,0.])
                        xyz[b]=xyz[a]+direction*lengths[(a,b)];available[b]=True
                        sources[b]='estimated_recent_direction' if prior is not None else 'estimated_standing_prior'
            for hip,knee,ankle in leg_chains:
                if available[hip] and not visible[t,knee] and not visible[t,ankle] and hip in leg_priors and \
                        sources[knee]!='interpolated' and sources[ankle]!='interpolated' and \
                        (hip,knee) in lengths and (knee,ankle) in lengths:
                    target,bend=leg_priors[hip]
                    xyz[knee],xyz[ankle]=leg_ik(xyz[hip],xyz[hip]+target,bend,lengths[(hip,knee)],lengths[(knee,ankle)])
                    available[knee]=available[ankle]=True
                    sources[knee]=sources[ankle]='estimated_leg_ik'
            # Heel/toe offsets use a median observed ankle-relative vector.
            for ankle,tip in foot_pairs:
                if available[ankle] and (not available[tip] or sources[ankle]!='observed'):
                    if visible[t,ankle] and visible[t,tip]:
                        xyz[tip]=xyz[ankle]+points[t,tip]-points[t,ankle]
                        available[tip]=True;sources[tip]='offset_preserved'
                    elif (ankle,tip) in offsets:
                        xyz[tip]=xyz[ankle]+offsets[(ankle,tip)]
                        available[tip]=True;sources[tip]='estimated_foot_offset'
        joints=[]
        for j in range(joint_count):
            state=str(sources[j]) if available[j] else 'unresolved'
            counts[state]+=1
            joints.append({'xyz':xyz[j].tolist() if available[j] else None,'source':state,
                           'suspect':(t,j) in suspect_set})
        result.append({'frame_index':t,'timestamp':f['timestamp'],'joints':joints})
    return {'version':1,'stage':'completion3d','joint_names':document['joint_names'],
            'coordinates':document['coordinates'],'units':'meters','root_motion':False,
            'method':'fixed_length_direction_interpolation_and_explicit_leg_priors',
            'lengths':{f'{a}-{b}':v for (a,b),v in lengths.items()},
            'length_calibration':calibration,
            'prior_calibration':prior_calibration,
            'suspects':suspects,'counts':dict(counts),'frames':result,
            'limits':['not_measured_hidden_motion','no_contact_or_global_root_solution',
                      'not_hair_segmentation','not_rotation_animation_or_UE_asset']}
