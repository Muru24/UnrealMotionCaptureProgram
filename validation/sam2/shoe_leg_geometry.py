"""Joint-only shoe-constrained leg hypotheses; no calibrated depth claim."""
import numpy as np
from core.pose3d.completion import leg_ik


def fit_camera(world,image,width,height):
    q=np.asarray(world,float);p=np.asarray(image,float);center=np.array([width/2,height/2])
    if q.ndim!=2 or q.shape[1]!=3 or p.shape!=(len(q),2) or not np.isfinite(np.r_[q.ravel(),p.ravel()]).all():raise ValueError('Invalid camera correspondences.')
    uv=p-center
    design=np.vstack([np.c_[q[:,0],np.ones(len(q)),np.zeros(len(q)),-uv[:,0]],
                      np.c_[q[:,1],np.zeros(len(q)),np.ones(len(q)),-uv[:,1]]])
    target=np.r_[uv[:,0]*q[:,2],uv[:,1]*q[:,2]]
    parameters,_,rank,_=np.linalg.lstsq(design,target,rcond=None)
    if rank<4:raise ValueError('Degenerate camera fit.')
    focal,a,b,depth=parameters
    if not 100<focal<20000 or np.min(q[:,2]+depth)<=.1:raise ValueError('Invalid fitted camera.')
    camera={'focal':float(focal),'translation':[float(a/focal),float(b/focal),float(depth)],'center':center.tolist()}
    camera['rms_pixels']=float(np.sqrt(np.mean((project(q,camera)-p)**2)))
    if camera['rms_pixels']>.1:raise ValueError('Inconsistent projection fit.')
    return camera


def project(world,camera):
    q=np.asarray(world,float)+np.asarray(camera['translation'])
    return q[...,:2]/q[...,2:]*camera['focal']+np.asarray(camera['center'])


def body_basis(q):
    x=q[6]-q[5]
    if np.linalg.norm(x)<1e-6:raise ValueError('Degenerate shoulder reference.')
    x=x/np.linalg.norm(x)
    y=(q[9]+q[10]-q[5]-q[6])/2;y=y-x*np.dot(x,y)
    if np.linalg.norm(y)<1e-6:raise ValueError('Degenerate body reference.')
    y/=np.linalg.norm(y);return np.column_stack((x,y,np.cross(x,y)))


def anchor_in_mask(mask,hip_image,fraction):
    ys,xs=np.nonzero(mask)
    if len(xs)<32:raise ValueError('No stable shoe pixels.')
    points=np.c_[xs,ys].astype(float);center=points.mean(0)
    _,vectors=np.linalg.eigh(np.cov((points-center).T));axis=vectors[:,-1]
    if np.dot(axis,np.asarray(hip_image)-center)<0:axis=-axis
    along=(points-center)@axis;level=np.quantile(along,float(np.clip(fraction,.1,.9)))
    band=points[np.abs(along-level)<=max(2,np.ptp(along)*.06)]
    target=band.mean(0);return points[np.argmin(np.linalg.norm(points-target,axis=1))]


def reference_fraction(mask,ankle,hip):
    ys,xs=np.nonzero(mask);points=np.c_[xs,ys].astype(float);center=points.mean(0)
    _,vectors=np.linalg.eigh(np.cov((points-center).T));axis=vectors[:,-1]
    if np.dot(axis,np.asarray(hip)-center)<0:axis=-axis
    return float(np.clip(np.mean((points-center)@axis<=np.dot(np.asarray(ankle)-center,axis)),.1,.9))


def solve_leg(hip,knee,ankle,target,camera,upper,lower,reference_knee,reference_ankle,knee_target=None):
    """Sample feasible ankle depth on a ray; exact two-bone IK for each."""
    if not .02<upper<1.5 or not .02<lower<1.5:raise ValueError('Invalid bone lengths.')
    hip=np.asarray(hip,float);translation=np.asarray(camera['translation'])
    ray=np.r_[(np.asarray(target)-camera['center'])/camera['focal'],1.]
    rmax=np.sqrt(upper**2+lower**2-2*upper*lower*np.cos(np.radians(175)))
    rmin=np.sqrt(upper**2+lower**2-2*upper*lower*np.cos(np.radians(10)))
    origin=hip+translation;a=np.dot(ray,ray);b=-2*np.dot(ray,origin);c=np.dot(origin,origin)-rmax**2
    determinant=b*b-4*a*c
    if determinant<=0:return None
    lo=max(.1,(-b-np.sqrt(determinant))/(2*a));hi=(-b+np.sqrt(determinant))/(2*a)
    if hi<=lo:return None
    depths=list(np.linspace(lo+1e-6,hi-1e-6,21))
    for point in (ankle,reference_ankle):depths.append(float(np.clip(np.dot(ray,np.asarray(point)+translation)/a,lo+1e-6,hi-1e-6)))
    best=None
    for depth in depths:
        foot=depth*ray-translation;distance=np.linalg.norm(foot-hip)
        if not rmin<=distance<=rmax:continue
        bends=[np.asarray(reference_knee)-hip,np.asarray(knee)-hip,hip-np.asarray(reference_knee)]
        if knee_target is not None:
            # Explore the knee circle instead of forcing a 2D point into 3D.
            axis=(foot-hip)/distance;u=np.cross(axis,[1.,0.,0.])
            if np.linalg.norm(u)<1e-6:u=np.cross(axis,[0.,1.,0.])
            u/=np.linalg.norm(u);v=np.cross(axis,u)
            bends += [u*np.cos(theta)+v*np.sin(theta) for theta in np.linspace(0,2*np.pi,48,endpoint=False)]
        for bend in bends:
            new_knee,new_ankle=leg_ik(hip,foot,bend,upper,lower)
            cost=(np.linalg.norm(new_ankle-reference_ankle)+.5*np.linalg.norm(new_knee-reference_knee)
                  +.15*np.linalg.norm(new_ankle-ankle))/(upper+lower)
            error=float(np.linalg.norm(project(new_ankle[None],camera)[0]-target))
            knee_error=None
            if knee_target is not None:
                knee_error=float(np.linalg.norm(project(new_knee[None],camera)[0]-knee_target))
                cost+=knee_error/10.
            if error>.1:continue
            if best is None or cost<best['cost']:best={'knee':new_knee,'ankle':new_ankle,'cost':float(cost),'projection_error':error,'knee_error_pixels':knee_error}
    return best
