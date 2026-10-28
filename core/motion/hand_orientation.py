"""Palm frame observations from native MHR70; no finger animation synthesis."""
import numpy as np
from core.motion.skeleton import AXIS


def palm_observations(raw):
    names=raw.get('joint_names',[]);index={n:i for i,n in enumerate(names)};out=[]
    for frame in raw['frames']:
        result={};outputs=frame.get('outputs') or {};points=outputs.get('pred_keypoints_3d');pixels=outputs.get('pred_keypoints_2d')
        tracked=frame.get('tracking',{}).get('state')=='tracked' and frame.get('roi') is not None
        for side,short in [('left','l'),('right','r')]:
            result[short]=None
            required=[side+'-'+n for n in ['wrist','index-third-joint','middle-third-joint','pinky-third-joint','elbow']]
            if not tracked or points is None or any(n not in index for n in required):continue
            q=np.asarray(points,float)
            if q.shape!=(70,3):raise ValueError('Invalid hand observation shape.')
            ids=[index[n] for n in required];p=q[ids]@AXIS.T
            if not np.isfinite(p).all():continue
            wrist,first,middle,pinky,elbow=p;forward=middle-wrist;width=first-pinky;forearm=wrist-elbow
            fl,wl,al=map(np.linalg.norm,[forward,width,forearm])
            if al<1e-6 or not .1<fl/al<1.1 or not .08<wl/al<1.1:continue
            width=width-forward*np.dot(width,forward)/(fl*fl)
            if np.linalg.norm(width)<wl*.25:continue
            if pixels is not None:
                xy=np.asarray(pixels,float)
                if xy.shape!=(70,2):raise ValueError('Invalid hand projection shape.')
                xy=xy[ids[:4]]
                if not np.isfinite(xy).all() or np.linalg.norm(xy[2]-xy[0])<5 or np.linalg.norm(xy[1]-xy[3])<3:continue
                w,h=raw['video']['width'],raw['video']['height']
                if not ((xy[:,0]>=0)&(xy[:,0]<w)&(xy[:,1]>=0)&(xy[:,1]<h)).all():continue
            result[short]={'forward':(forward/fl).tolist(),'lateral':(width/np.linalg.norm(width)).tolist(),
                           'forearm':(forearm/al).tolist(),'status':'model_palm_frame_not_verified'}
        out.append(result)
    return out
