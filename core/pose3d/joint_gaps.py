"""Fill bounded explicit limb gaps without rewriting valid model observations."""
from collections import Counter
import numpy as np
from .completion import unit

ARM_EDGES=((5,7),(7,62),(6,8),(8,41))


def fill_arm_gaps(document,result,cancelled=lambda:False):
    frames=document['frames'];repaired=result['frames'];fps=document['video']['fps'];n=len(frames)
    segments=[f.get('tracking_segment',0) for f in frames]
    eligible=np.array([f['person_bbox'] is not None for f in frames])
    spans=[];blocked=Counter()
    for parent,child in ARM_EDGES:
        t=0
        while t<n:
            if cancelled():raise KeyboardInterrupt
            if repaired[t]['joints'][child]['xyz'] is not None:t+=1;continue
            start=t
            while t<n and repaired[t]['joints'][child]['xyz'] is None:t+=1
            end=t
            reason=None
            if start==0 or end==n:reason='unbounded_gap'
            elif (end-start)/fps>.2:reason='long_gap'
            elif not eligible[start-1:end+1].all():reason='target_unavailable'
            elif any(s!=segments[start-1] for s in segments[start-1:end+1]):reason='segment_boundary'
            elif not all(frames[k]['landmarks'][j]['valid'] for k in (start-1,end) for j in (parent,child)):
                reason='untrusted_endpoints'
            elif any(repaired[k]['joints'][parent]['xyz'] is None for k in range(start,end)):
                reason='parent_unavailable'
            if reason:blocked[reason]+=1;continue
            vectors=[np.subtract(repaired[k]['joints'][child]['xyz'],repaired[k]['joints'][parent]['xyz']) for k in (start-1,end)]
            lengths=[float(np.linalg.norm(v)) for v in vectors]
            if not all(.02<=v<=1.5 for v in lengths) or max(lengths)/min(lengths)>1.5:
                blocked['inconsistent_length']+=1;continue
            directions=[unit(v) for v in vectors]
            if np.dot(*directions)<0:
                blocked['large_direction_change']+=1;continue
            for k in range(start,end):
                alpha=(k-start+1)/(end-start+1)
                direction=unit((1-alpha)*directions[0]+alpha*directions[1])
                length=(1-alpha)*lengths[0]+alpha*lengths[1]
                origin=np.asarray(repaired[k]['joints'][parent]['xyz'])
                repaired[k]['joints'][child].update(xyz=(origin+direction*length).tolist(),source='interpolated_joint')
            spans.append({'parent':parent,'joint':child,'start':start,'end_exclusive':end,
                          'segment':segments[start-1],'duration_seconds':(end-start)/fps})
    result['counts']=dict(Counter(j['source'] for f in repaired for j in f['joints']))
    result['joint_gap_completion']={'max_gap_seconds':.2,'method':'parent_relative_direction_and_length_interpolation',
        'joints':[7,62,8,41],'spans':spans,'blocked_spans':dict(blocked),
        'filled_joint_frames':sum(s['end_exclusive']-s['start'] for s in spans)}
