"""Unordered visible shoe support, not left/right identity or ankle truth."""
import cv2
import numpy as np


def mask_distance(mask,point):
    x,y=np.round(point).astype(int);h,w=mask.shape
    if not 0<=x<w or not 0<=y<h:return float(np.hypot(w,h))
    field=cv2.distanceTransform((~mask).astype(np.uint8),cv2.DIST_L2,cv2.DIST_MASK_PRECISE)
    return float(field[y,x])


def regions_at(folder,records,index):
    masks=[]
    for boot in records[index]['boots']:
        if boot['accepted']:
            p=folder/f'boot-{boot["id"]}'/f'{index:06d}.png'
            mask=cv2.imdecode(np.fromfile(p,np.uint8),0)
            if mask is None:raise ValueError('Missing shoe mask.')
            masks.append(mask>0)
    if len(masks)==2:
        overlap=np.count_nonzero(masks[0]&masks[1])/max(1,np.count_nonzero(masks[0]|masks[1]))
        if overlap>.4:masks=[masks[0]|masks[1]]
    return masks


def shoe_support(masks,ankles,tolerance=18):
    regions=[np.asarray(m,bool) for m in masks if np.any(m)]
    if len(regions)==2:
        overlap=np.count_nonzero(regions[0]&regions[1])/max(1,np.count_nonzero(regions[0]|regions[1]))
        if overlap>.4:regions=[regions[0]|regions[1]]
    if not regions:return {'regions':0,'status':'unknown','disagrees':False,'error_pixels':None}
    distances=[]
    for region in regions:
        field=cv2.distanceTransform((~region).astype(np.uint8),cv2.DIST_L2,cv2.DIST_MASK_PRECISE)
        h,w=region.shape;d=[]
        for x,y in ankles:
            d.append(float(field[round(y),round(x)]) if 0<=round(x)<w and 0<=round(y)<h else float(np.hypot(w,h)))
        distances.append(d)
    d=np.array(distances)
    error=float(d.min()) if len(regions)==1 else float(min(max(d[0,0],d[1,1]),max(d[0,1],d[1,0])))
    return {'regions':len(regions),'status':'two_shoe_regions' if len(regions)==2 else 'one_region_other_leg_unknown',
            'disagrees':error>tolerance,'error_pixels':error,'left_right_identity_verified':False}
