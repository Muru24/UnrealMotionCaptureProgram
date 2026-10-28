"""Joint-only flip restoration; never converts MHR pose/rotation parameters."""
import numpy as np


def mirror_indices(names):
    lookup={name:i for i,name in enumerate(names)}
    if len(lookup)!=len(names):raise ValueError('Duplicate joint names.')
    mapping=[]
    for name in names:
        other='right-'+name[5:] if name.startswith('left-') else 'left-'+name[6:] if name.startswith('right-') else name
        if other not in lookup:raise ValueError('Unpaired joint name.')
        mapping.append(lookup[other])
    return np.array(mapping)


def restore_flip(image,world,names,width):
    mapping=mirror_indices(names)
    p=np.asarray(image,dtype=float)[mapping].copy();q=np.asarray(world,dtype=float)[mapping].copy()
    if p.shape!=(len(names),2) or q.shape!=(len(names),3):raise ValueError('Joint dimensions differ.')
    p[:,0]=width-1-p[:,0];q[:,0]*=-1
    return p,q


def flip_roi(roi,width):
    x1,y1,x2,y2=roi
    return [width-x2,y1,width-x1,y2]
