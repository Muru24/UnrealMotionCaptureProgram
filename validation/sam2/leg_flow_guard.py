"""Short image-motion support for candidate legs, not semantic leg detection."""
import cv2
import numpy as np
LEG_JOINTS=(11,12,13,14)


def track_leg_points(previous,current,points):
    """Track local feature clouds for C candidates x four knee/ankle points."""
    c=len(points);cloud=[];groups=[];h,w=previous.shape
    for candidate in range(c):
        for joint in range(4):
            x,y=np.round(points[candidate,joint]).astype(int)
            left=max(0,x-20);top=max(0,y-20);right=min(w,x+21);bottom=min(h,y+21)
            if right-left<10 or bottom-top<10:continue
            features=cv2.goodFeaturesToTrack(previous[top:bottom,left:right],12,.02,3)
            if features is None:continue
            features[:,0]+=[left,top];start=len(cloud);cloud.extend(features[:,0].tolist())
            groups.append((candidate,joint,start,len(cloud)))
    predicted=np.full((c,4,2),np.nan);support=np.zeros((c,4),int)
    if not cloud:return predicted,support
    features=np.asarray(cloud,np.float32).reshape(-1,1,2)
    advanced,status,error=cv2.calcOpticalFlowPyrLK(previous,current,features,None,winSize=(21,21),maxLevel=3)
    returned,back_status,_=cv2.calcOpticalFlowPyrLK(current,previous,advanced,None,winSize=(21,21),maxLevel=3)
    good=(status[:,0]>0)&(back_status[:,0]>0)&(error[:,0]<25)&(np.linalg.norm(returned[:,0]-features[:,0],axis=1)<1.5)
    for candidate,joint,start,end in groups:
        accepted=good[start:end]
        if accepted.sum()<3:continue
        delta=advanced[start:end,0][accepted]-features[start:end,0][accepted]
        median=np.median(delta,axis=0);inlier=np.linalg.norm(delta-median,axis=1)<4
        if inlier.sum()<3:continue
        predicted[candidate,joint]=points[candidate,joint]+np.median(delta[inlier],axis=0)
        support[candidate,joint]=int(inlier.sum())
    return predicted,support


def transition_evidence(predicted,support,current_points,scale):
    """Missing image evidence supplies no penalty; it never proves a good leg."""
    c=len(predicted);cost=np.zeros((c,c));residual=np.full((c,c,4),np.nan);suspect=np.zeros((c,c,4),bool)
    for before in range(c):
        good=(support[before]>=3)&np.isfinite(predicted[before]).all(axis=1)
        for after in range(c):
            residual[before,after,good]=np.linalg.norm(current_points[after,good]-predicted[before,good],axis=1)
            suspect[before,after,good]=residual[before,after,good]>max(18,.35*scale)
            if good.sum()>=2:cost[before,after]=.8*np.mean(np.minimum(residual[before,after,good]/scale,1.))
    return cost,residual,suspect
