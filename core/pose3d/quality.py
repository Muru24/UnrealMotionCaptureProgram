"""Review heuristics for model positions; never classify anatomical correctness."""
from collections import Counter
import numpy as np

BONES=((5,7),(7,62),(6,8),(8,41),(9,11),(11,13),(10,12),(12,14))


def review_pose(document,cancelled=lambda:False):
    frames=document['frames'];n=len(frames)
    segments=np.array([f.get('tracking_segment',0) for f in frames])
    flagged=[set() for _ in frames];events=[];calibration=[]
    for parent,child in BONES:
        if cancelled():raise KeyboardInterrupt
        vectors=np.full((n,3),np.nan)
        for i,f in enumerate(frames):
            a,b=f['landmarks'][parent],f['landmarks'][child]
            if f['person_bbox'] is not None and a['valid'] and b['valid']:
                vectors[i]=np.subtract([b[k] for k in ('x','y','z')],[a[k] for k in ('x','y','z')])
        lengths=np.linalg.norm(vectors,axis=1)
        valid=np.isfinite(vectors).all(axis=1)&(lengths>.02)&(lengths<1.5)
        for segment in dict.fromkeys(segments.tolist()):
            sample=valid&(segments==segment)
            if sample.sum()<8:continue
            median=float(np.median(lengths[sample]));mad=float(np.median(np.abs(lengths[sample]-median)))
            calibration.append({'bone':[parent,child],'segment':segment,'samples':int(sample.sum()),
                                'median_meters':median,'mad_meters':mad})
            deviation=max(.35*median,6*mad)
            candidates=np.isfinite(lengths)&(segments==segment)&(np.abs(lengths-median)>deviation)
            candidates&=(lengths<median*.5)|(lengths>median*1.5)
            for i in np.flatnonzero(candidates):
                # Re-check original validity: an invalid/offscreen point is a gap.
                f=frames[i]
                if f['person_bbox'] is None or not all(f['landmarks'][j]['valid'] for j in (parent,child)):continue
                flagged[i].add((parent,child))
                events.append({'start':int(i),'end_exclusive':int(i)+1,'bone':[parent,child],
                               'reason':'length_outlier','length_ratio':float(lengths[i]/median)})
        # Flag a brief departure only when observations on both sides agree.
        for width in (1,2):
            if width/document['video']['fps']>.1:continue
            for start in range(1,n-width):
                end=start+width
                if not valid[start-1:end+1].all() or not (segments[start-1:end+1]==segments[start-1]).all():continue
                directions=vectors[start-1:end+1]/lengths[start-1:end+1,None]
                if np.dot(directions[0],directions[-1])<.9:continue
                if not all(np.dot(v,directions[0])<.5 and np.dot(v,directions[-1])<.5 for v in directions[1:-1]):continue
                for i in range(start,end):flagged[i].add((parent,child))
                events.append({'start':start,'end_exclusive':end,'bone':[parent,child],
                               'reason':'isolated_direction_spike'})
    return {'version':1,'meaning':'review_candidates_not_confirmed_errors','events':events,
        'frames':[{'frame_index':i,'bones':[list(b) for b in sorted(bones)]} for i,bones in enumerate(flagged)],
        'calibration':calibration,'summary':{'review_frames':sum(bool(b) for b in flagged),'events':len(events),
            'reasons':dict(Counter(e['reason'] for e in events))},
        'limits':['not_hair_or_clothing_segmentation','stable_wrong_positions_may_not_be_flagged',
                  'fast_real_motion_can_be_flagged','no_joint_values_changed','no_anatomical_ground_truth']}
