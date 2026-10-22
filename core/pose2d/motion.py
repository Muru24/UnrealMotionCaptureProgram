"""2D constant-velocity Kalman prediction; predictions are not detections."""
import numpy as np


class BodyMotion:
    transition_noise_policy='torso_scaled_shoulder_proxy_and_returning_hip_floor'

    def __init__(self,fps):
        if not np.isfinite(fps) or not 1<=fps<=240:raise ValueError('Invalid motion fps')
        self.dt=1/float(fps);self.x=None;self.P=None
        self.shoulder_offset=None;self.box_offset=np.zeros(2);self.scale=100.
        self.torso_length=None
        self.accepted_kind=None;self.accepted_base_std=None

    def measurement(self,box,pose):
        box=np.asarray(box,dtype=float);center=(box[:2]+box[2:])/2
        diagonal=max(float(np.linalg.norm(box[2:]-box[:2])),1.)
        def pair(a,b):
            if pose is None:return None
            points,scores=pose
            if not np.isfinite(points[[a,b]]).all() or not np.isfinite(scores[[a,b]]).all() or min(scores[a],scores[b])<.5:return None
            p=points[[a,b]]
            if not (p>=box[:2]-(box[2:]-box[:2])*.1).all() or not (p<=box[2:]+(box[2:]-box[:2])*.1).all():return None
            if not 4<=np.linalg.norm(p[0]-p[1])<=diagonal*.7:return None
            return p.mean(axis=0)
        hip=pair(11,12);shoulder=pair(5,6)
        quality={'hip_pair_valid':hip is not None,'shoulder_pair_valid':shoulder is not None,
                 'torso_rejected':False,'torso_length_pixels':None}
        # Confidence alone cannot validate a torso: hair/cloth can score highly.
        if hip is not None and shoulder is not None:
            length=float(np.linalg.norm(hip-shoulder))
            quality['torso_length_pixels']=length
            coherent=diagonal*.04<=length<=diagonal*.65
            if self.torso_length is not None:
                coherent=coherent and .5*self.torso_length<=length<=2*self.torso_length
            if not coherent:
                quality['torso_rejected']=True
                hip=shoulder=None
        if hip is not None:z,kind,std=hip,'hip',max(diagonal*.015,3.)
        elif shoulder is not None and self.shoulder_offset is not None:
            # The calibrated offset is a proxy, not a current hip observation.
            # Torso rotation/crouching changes its direction while hips are hidden.
            offset_uncertainty=float(self.torso_length or 0.)*.35
            z,kind,std=shoulder+self.shoulder_offset,'shoulder_with_hip_offset',max(diagonal*.03,offset_uncertainty,6.)
        else:z,kind,std=center+self.box_offset,'box_fallback',max(diagonal*.07,10.)
        base_std=std
        source_changed=self.accepted_kind is not None and kind!=self.accepted_kind
        # Returning hips and a shoulder-derived center need not coincide exactly.
        # Preserve the shoulder proxy's noise on the first returning hip. A box
        # is not an anatomical observation and must not relax a hip candidate.
        transition_floor=(kind=='hip' and self.accepted_kind=='shoulder_with_hip_offset')
        if transition_floor:
            std=max(base_std,self.accepted_base_std)
        quality.update(base_std_pixels=base_std,measurement_std_pixels=std,
                       previous_accepted_kind=self.accepted_kind,source_changed=source_changed,
                       shoulder_to_hip_noise_floor=transition_floor)
        quality['selection_reason']=('incoherent_torso' if quality['torso_rejected'] else
            'valid_hip_pair' if kind=='hip' else 'shoulder_with_calibrated_offset' if shoulder is not None and self.shoulder_offset is not None else
            'no_hip_and_no_calibrated_shoulder')
        self.observation_quality=quality
        return np.asarray(z),kind,std,hip,shoulder

    def initialize(self,box,pose):
        z,kind,std,hip,shoulder=self.measurement(box,pose)
        self.scale=max(float(np.linalg.norm(np.asarray(box)[2:]-np.asarray(box)[:2])),1.)
        self.x=np.r_[z,0.,0.];self.P=np.diag([std**2,std**2,(self.scale*2)**2,(self.scale*2)**2])
        self.accept_offsets(box,z,hip,shoulder)
        self.accepted_kind=kind;self.accepted_base_std=self.observation_quality['base_std_pixels']
        return z,kind

    def accept_offsets(self,box,z,hip,shoulder):
        box=np.asarray(box);self.box_offset=z-(box[:2]+box[2:])/2
        if hip is not None and shoulder is not None:
            delta=hip-shoulder
            length=float(np.linalg.norm(delta))
            self.torso_length=length if self.torso_length is None else .9*self.torso_length+.1*length
            self.shoulder_offset=delta if self.shoulder_offset is None else .8*self.shoulder_offset+.2*delta

    def predict(self):
        dt=self.dt;F=np.eye(4);F[0,2]=F[1,3]=dt
        G=np.array([[dt*dt/2,0],[0,dt*dt/2],[dt,0],[0,dt]])
        self.x=F@self.x;self.P=F@self.P@F.T+G@G.T*(self.scale*6)**2
        return self.x[:2].copy()

    def innovation(self,z,std):
        delta=z-self.x[:2];S=self.P[:2,:2]+np.eye(2)*std**2
        return float(delta@np.linalg.solve(S,delta))

    def update(self,box,pose):
        z,kind,std,hip,shoulder=self.measurement(box,pose)
        H=np.eye(2,4);R=np.eye(2)*std**2;S=H@self.P@H.T+R
        K=np.linalg.solve(S,(self.P@H.T).T).T
        self.x=self.x+K@(z-H@self.x)
        I=np.eye(4)-K@H;self.P=I@self.P@I.T+K@R@K.T
        self.scale=.9*self.scale+.1*max(float(np.linalg.norm(np.asarray(box)[2:]-np.asarray(box)[:2])),1.)
        self.accept_offsets(box,z,hip,shoulder)
        self.accepted_kind=kind;self.accepted_base_std=self.observation_quality['base_std_pixels']
        return z,kind
