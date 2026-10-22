"""Explicit COCO17 to H36M17 comparison adapter, never an MHR conversion."""
import numpy as np
H36M_NAMES=['pelvis','right_hip','right_knee','right_ankle','left_hip','left_knee','left_ankle',
            'spine_proxy','thorax_proxy','nose','head','left_shoulder','left_elbow','left_wrist','right_shoulder','right_elbow','right_wrist']
H36M_BONES=((0,1),(1,2),(2,3),(0,4),(4,5),(5,6),(0,7),(7,8),(8,9),(9,10),(8,11),(11,12),(12,13),(8,14),(14,15),(15,16))
COCO_TO_MHR=[0,1,2,3,4,5,6,7,8,62,41,9,10,11,12,13,14]


def mhr_comparison_points(world):
    q=np.asarray(world,float)
    if q.shape!=(70,3) or not np.isfinite(q).all():raise ValueError('Invalid comparison MHR joints.')
    result=np.zeros((17,3))
    for dest,src in {1:10,2:12,3:14,4:9,5:11,6:13,9:0,11:5,12:7,13:62,14:6,15:8,16:41}.items():result[dest]=q[src]
    result[0]=(q[9]+q[10])/2;result[8]=(q[5]+q[6])/2;result[7]=(result[0]+result[8])/2;result[10]=(q[1]+q[2])/2
    return result


def coco_to_h36m(points,scores,width,height):
    p=np.asarray(points,float);s=np.asarray(scores,float)
    if p.shape!=(17,2) or s.shape!=(17,) or not np.isfinite(p).all() or not np.isfinite(s).all() or min(width,height)<=0:raise ValueError('Invalid COCO17 observations.')
    s=np.clip(s,0,1);s[np.any(p<0,axis=1)|np.any(p>=[width,height],axis=1)]=0
    x=np.c_[p,s];y=np.zeros((17,3))
    for dest,src in {1:12,2:14,3:16,4:11,5:13,6:15,9:0,11:5,12:7,13:9,14:6,15:8,16:10}.items():y[dest]=x[src]
    for dest,a,b in ((0,11,12),(8,5,6),(10,1,2)):
        y[dest,:2]=(x[a,:2]+x[b,:2])/2;y[dest,2]=min(x[a,2],x[b,2])
    # COCO lacks a head-top landmark: eye midpoint is an explicit low-weight proxy.
    y[10,2]*=.5;y[7,:2]=(y[0,:2]+y[8,:2])/2;y[7,2]=min(y[0,2],y[8,2])
    y[:,:2]=(y[:,:2]-np.array([width,height])/2)/(min(width,height)/2)
    return y


def flip_h36m(x):
    x=np.array(x,copy=True);left=[4,5,6,11,12,13];right=[1,2,3,14,15,16]
    x[...,0]*=-1;x[...,left+right,:]=x[...,right+left,:];return x


def normalize_clip(motion):
    """Official crop_scale([1,1]) geometry; keep inverse parameters for XY proxy."""
    x=np.array(motion,dtype=float,copy=True)
    if x.ndim!=3 or x.shape[1:]!=(17,3) or not np.isfinite(x).all():raise ValueError('Invalid temporal observations.')
    x[...,2][x[...,2]<.3]=0
    valid=x[...,:2][x[...,2]>0]
    if len(valid)<4:raise ValueError('Insufficient 2D observations for normalization.')
    low=valid.min(axis=0);high=valid.max(axis=0);scale=float(np.max(high-low));center=(low+high)/2
    if scale<1e-6:raise ValueError('Degenerate temporal normalization.')
    x[...,:2]=(x[...,:2]-center)/scale*2
    return np.clip(x,-1,1),{'center':center.tolist(),'scale':scale,'low_score_threshold':.3}


def segments(rows,maxlen=243):
    if not 1<=maxlen<=243:raise ValueError('Invalid MotionBERT clip length.')
    result=[];current=[];previous_key=None
    for i,row in enumerate(rows):
        if row['frame_index']!=i:raise ValueError('MotionBERT frame order differs.')
        k=(row.get('target_id'),row.get('tracking_segment'),row.get('scene_index'))
        usable=row.get('h36m_input') is not None and all(v is not None for v in k)
        if current and (not usable or k!=previous_key or len(current)>=maxlen):result.append(current);current=[]
        if usable:current.append(i)
        previous_key=k
    if current:result.append(current)
    return result
