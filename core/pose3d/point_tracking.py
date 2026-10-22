"""Local forward/backward optical flow for explicitly clicked image points."""
import cv2
import numpy as np


class ImagePointTracker:
    def __init__(self):
        self.gray = None
        self.points = {}
        self.bound = set()
        self.last_verified = {}

    def update(self, frame, manual):
        if 'pelvis' in manual:
            self.reset_motion()
            self.bound.clear()
            self.last_verified.clear()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        tracked = {}
        if self.gray is not None and self.points:
            names = list(self.points)
            before = np.asarray([self.points[n] for n in names],dtype=np.float32).reshape(-1,1,2)
            options = dict(winSize=(21,21),maxLevel=3,
                           criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,30,.01))
            after, status, error = cv2.calcOpticalFlowPyrLK(self.gray,gray,before,None,**options)
            if after is not None:
                back, reverse, _ = cv2.calcOpticalFlowPyrLK(gray,self.gray,after,None,**options)
                if back is not None:
                    for i,name in enumerate(names):
                        xy = after[i,0]
                        if status[i,0] and reverse[i,0] and error[i,0]<12 and \
                                np.isfinite(xy).all() and np.linalg.norm(back[i,0]-before[i,0])<1.2 and \
                                10<=xy[0]<gray.shape[1]-10 and 10<=xy[1]<gray.shape[0]-10:
                            old_patch=cv2.getRectSubPix(self.gray,(15,15),tuple(before[i,0]))
                            new_patch=cv2.getRectSubPix(gray,(15,15),tuple(xy))
                            # Flat patches and an inconsistent local appearance are not evidence.
                            if old_patch.std()>5 and new_patch.std()>5 and \
                                    cv2.matchTemplate(new_patch,old_patch,cv2.TM_CCOEFF_NORMED)[0,0]>.8:
                                tracked[name]=xy.astype(float)
        for name,xy in manual.items():
            tracked[name]=np.asarray(xy,dtype=float)
            self.bound.add(name)
        self.gray=gray
        self.points=tracked
        self.last_verified.update(tracked)
        return tracked

    def reset_motion(self):
        self.gray=None
        self.points={}
