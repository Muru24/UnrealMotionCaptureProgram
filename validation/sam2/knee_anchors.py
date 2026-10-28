"""Explicit 2D knee observations, bound to the exact source video."""
import numpy as np


def validate_anchors(data,source_hash,width,height,frame_count):
    if data.get('schema')!='manual_knees_v1' or data.get('source_sha256')!=source_hash:
        raise ValueError('Anchor source/schema mismatch.')
    result={}
    for row in data.get('anchors',[]):
        frame=row.get('frame');joint=row.get('joint');point=np.asarray(row.get('xy'),float)
        if type(frame) is not int or not 0<=frame<frame_count or joint not in (11,12):raise ValueError('Invalid knee/frame.')
        if point.shape!=(2,) or not np.isfinite(point).all() or not (0<=point[0]<width and 0<=point[1]<height):raise ValueError('Point outside source image.')
        if joint in result.get(frame,{}):raise ValueError('Duplicate knee anchor.')
        result.setdefault(frame,{})[joint]=point
    return result


def knee_target_at(anchors,frame,joint,max_gap=16):
    if joint in anchors.get(frame,{}):return anchors[frame][joint],'manual'
    keys=sorted(f for f,v in anchors.items() if joint in v)
    for a,b in zip(keys[:-1],keys[1:]):
        if a<frame<b and b-a<=max_gap:
            alpha=(frame-a)/(b-a)
            return (1-alpha)*anchors[a][joint]+alpha*anchors[b][joint],'interpolated_2d'
    return None,'unknown'
