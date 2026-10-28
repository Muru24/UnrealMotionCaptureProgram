"""Non-destructive local bone offsets and shared live/export pose evaluation."""
import json,hashlib,math,copy
from pathlib import Path
import numpy as np


MODEL='__model__'


def quaternion(euler):
    x,y,z=np.radians(euler)/2
    cx,cy,cz=np.cos([x,y,z]);sx,sy,sz=np.sin([x,y,z])
    return np.array([cx*cy*cz+sx*sy*sz,sx*cy*cz-cx*sy*sz,cx*sy*cz+sx*cy*sz,cx*cy*sz-sx*sy*cz])


def multiply(a,b):
    w,x,y,z=a;v,i,j,k=b
    return np.array([w*v-x*i-y*j-z*k,w*i+x*v+y*k-z*j,w*j-x*k+y*v+z*i,w*k+x*j-y*i+z*v])


def rotation(q):
    q=np.asarray(q,float);q=q/np.linalg.norm(q);w,x,y,z=q
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                     [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                     [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])


def euler_angles(q):
    m=rotation(q);y=math.asin(float(np.clip(-m[2,0],-1,1)))
    x=math.atan2(m[2,1],m[2,2]);z=math.atan2(m[1,0],m[0,0])
    return np.degrees([x,y,z])


def slerp(a,b,t):
    dot=float(a@b)
    if dot<0:b=-b;dot=-dot
    if dot>.9995:
        q=a*(1-t)+b*t;return q/np.linalg.norm(q)
    angle=math.acos(np.clip(dot,-1,1))
    return (math.sin((1-t)*angle)*a+math.sin(t*angle)*b)/math.sin(angle)


def matrix(location,q,scale=(1,1,1)):
    m=np.eye(4);m[:3,:3]=rotation(q)*np.asarray(scale)[None,:];m[:3,3]=location;return m


def matrix_quaternion(m):
    m=np.asarray(m,float);t=np.trace(m)
    if t>0:
        s=math.sqrt(max(0,t+1))*2;q=np.array([s/4,(m[2,1]-m[1,2])/s,(m[0,2]-m[2,0])/s,(m[1,0]-m[0,1])/s])
    else:
        i=int(np.argmax(np.diag(m)));j=(i+1)%3;k=(i+2)%3;s=math.sqrt(max(1e-16,1+m[i,i]-m[j,j]-m[k,k]))*2
        q=np.zeros(4);q[0]=(m[k,j]-m[j,k])/s;q[i+1]=s/4;q[j+1]=(m[j,i]+m[i,j])/s;q[k+1]=(m[k,i]+m[i,k])/s
    return q/np.linalg.norm(q)


def align_vectors(a,b):
    a=np.asarray(a,float);b=np.asarray(b,float);a/=max(1e-12,np.linalg.norm(a));b/=max(1e-12,np.linalg.norm(b))
    dot=float(np.clip(a@b,-1,1));axis=np.cross(a,b);length=np.linalg.norm(axis)
    if length<1e-9:
        if dot>0:return np.eye(3)
        axis=np.cross(a,np.eye(3)[int(np.argmin(np.abs(a)))]);axis/=np.linalg.norm(axis)
        return 2*np.outer(axis,axis)-np.eye(3)
    axis/=length;x,y,z=axis;k=np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
    return np.eye(3)+k*length+k@k*(1-dot)


class EditableAnimation:
    def __init__(self,cache):
        self.cache=Path(cache);self.info=json.loads((self.cache/'scene.json').read_text(encoding='utf-8'))
        with np.load(self.cache/'scene.npz',allow_pickle=False) as d:self.data={k:d[k] for k in d.files}
        self.names=self.info['names'];self.parents=self.info['parents'];self.fps=self.info['fps'];self.count=self.info['frames']
        if self.count<1 or not math.isfinite(self.fps) or self.fps<=0:raise ValueError('편집 프레임 정보가 잘못되었습니다.')
        if not np.isfinite(self.data['locations']).all() or not np.isfinite(self.data['quaternions']).all():raise ValueError('유효하지 않은 본 데이터')
        self.edits={};self.undo_stack=[];self.redo_stack=[];self.dirty=False
        self.limb_ik=True
        self.rest_local=[]
        for i,parent in enumerate(self.parents):
            self.rest_local.append(self.data['rest'][i] if parent<0 else np.linalg.inv(self.data['rest'][parent])@self.data['rest'][i])
        self.inverse_rest=np.linalg.inv(self.data['rest'])

    def snapshot(self):
        self.undo_stack.append((copy.deepcopy(self.edits),self.limb_ik));self.undo_stack=self.undo_stack[-50:];self.redo_stack=[];self.dirty=True

    def set_key(self,name,frame,location,angles,whole=False):
        self.set_keys({name:(location,angles)},frame,whole)

    def set_keys(self,values,frame,whole=False):
        for name,(location,angles) in values.items():self.validate_value(name,frame,location,angles)
        self.snapshot()
        for name,(location,angles) in values.items():self._set_key(name,frame,location,angles,whole)

    def _set_key(self,name,frame,location,angles,whole):
        value={'location':list(map(float,location)),'rotation':list(map(float,angles))}
        if whole:self.edits[name]={'0':copy.deepcopy(value),str(self.count-1):copy.deepcopy(value)}
        else:
            track=self.edits.setdefault(name,{})
            if not track and 0<frame<self.count-1:
                track.update({'0':{'location':[0.,0.,0.],'rotation':[0.,0.,0.]},str(self.count-1):{'location':[0.,0.,0.],'rotation':[0.,0.,0.]}})
            track[str(frame)]=value

    def validate_value(self,name,frame,location,angles):
        if name not in self.names+[MODEL] or type(frame) is not int or not 0<=frame<self.count:raise ValueError('본 또는 프레임 범위가 잘못되었습니다.')
        location=np.asarray(location,dtype=float);angles=np.asarray(angles,dtype=float)
        if np.shape(location)!=(3,) or np.shape(angles)!=(3,) or not np.isfinite([location,angles]).all():raise ValueError('X·Y·Z에 유한한 숫자를 입력하세요.')
        if max(map(abs,location))>100 or max(map(abs,angles))>3600:raise ValueError('위치 ±100m, 회전 ±3600° 범위를 사용하세요.')

    def delete_key(self,name,frame):
        if str(frame) in self.edits.get(name,{}):
            self.snapshot();del self.edits[name][str(frame)]
            if not self.edits[name]:del self.edits[name]

    def undo(self,redo=False):
        stack=self.redo_stack if redo else self.undo_stack
        if stack:
            other=self.undo_stack if redo else self.redo_stack;other.append((copy.deepcopy(self.edits),self.limb_ik));self.edits,self.limb_ik=stack.pop();self.dirty=True

    def offset(self,name,frame):
        track=self.edits.get(name,{})
        if not track:return np.zeros(3),np.array([1.,0,0,0])
        keys=sorted(map(int,track));lo=max((k for k in keys if k<=frame),default=keys[0]);hi=min((k for k in keys if k>=frame),default=keys[-1])
        a,b=track[str(lo)],track[str(hi)];t=0 if lo==hi else (frame-lo)/(hi-lo)
        return np.array(a['location'])*(1-t)+np.array(b['location'])*t,slerp(quaternion(a['rotation']),quaternion(b['rotation']),t)

    def transforms(self,frame,draft=None,ik=None):
        frame=int(np.clip(frame,0,self.count-1));poses=[]
        overrides=draft if isinstance(draft,dict) else ({draft[0]:(np.asarray(draft[1]),quaternion(draft[2]))} if draft else {})
        offsets={n:overrides.get(n,self.offset(n,frame)) for n in self.names+[MODEL]}
        chains=[]
        for side in ('l','r'):
            for chain in ((f'upperarm_{side}',f'lowerarm_{side}',f'hand_{side}'),(f'thigh_{side}',f'calf_{side}',f'foot_{side}')):
                if (self.limb_ik if ik is None else ik) and all(n in self.names for n in chain):
                    ids=[self.names.index(n) for n in chain]
                    if self.parents[ids[1]]==ids[0] and self.parents[ids[2]]==ids[1]:chains.append(chain)
        ik_ends={c[2] for c in chains}
        for i,n in enumerate(self.names):
            loc,q=offsets[n]
            if n in ik_ends:loc=np.zeros(3)
            basis=matrix(self.data['locations'][frame,i]+loc,multiply(self.data['quaternions'][frame,i],q),self.data['scales'][frame,i])
            parent=self.parents[i];poses.append((np.eye(4) if parent<0 else poses[parent])@self.rest_local[i]@basis)
        loc,q=offsets[MODEL]
        obj=self.data['object_matrices'][frame]@matrix(loc,q)
        poses=obj@np.asarray(poses)
        for chain in chains:
            loc,_=offsets[chain[2]]
            if np.linalg.norm(loc)<1e-10:continue
            a,b,c=[self.names.index(n) for n in chain]
            target=poses[c,:3,3]+(poses[b]@self.rest_local[c])[:3,:3]@loc
            poses=self.solve_limb(poses,a,b,c,target)
        return poses

    def solve_limb(self,poses,a,b,c,target):
        poses=poses.copy();start,joint,end=[poses[i,:3,3].copy() for i in (a,b,c)]
        upper=np.linalg.norm(joint-start);lower=np.linalg.norm(end-joint)
        if min(upper,lower)<1e-8:return poses
        direction=target-start;distance=np.linalg.norm(direction)
        if distance<1e-9:direction=end-start;distance=np.linalg.norm(direction)
        if distance<1e-9:return poses
        direction/=distance;reach=np.clip(distance,abs(upper-lower)+1e-6,upper+lower-1e-6)
        pole=joint-start-direction*((joint-start)@direction)
        if np.linalg.norm(pole)<1e-7:
            pole=poses[a,:3,0]-direction*(poses[a,:3,0]@direction)
            if np.linalg.norm(pole)<1e-7:pole=np.cross(direction,[0,0,1])
        pole/=max(1e-12,np.linalg.norm(pole));along=(upper*upper-lower*lower+reach*reach)/(2*reach)
        new_joint=start+direction*along+pole*math.sqrt(max(0,upper*upper-along*along));new_end=start+direction*reach
        original=poses.copy();desired={}
        for i,new_pos,new_direction,old_direction in ((a,start,new_joint-start,joint-start),(b,new_joint,new_end-new_joint,end-joint)):
            m=poses[i].copy();m[:3,:3]=align_vectors(old_direction,new_direction)@m[:3,:3];m[:3,3]=new_pos;desired[i]=m
        m=poses[c].copy();m[:3,3]=new_end;desired[c]=m
        for i,parent in enumerate(self.parents):
            if i in desired:poses[i]=desired[i]
            elif parent>=0:poses[i]=poses[parent]@np.linalg.inv(original[parent])@original[i]
        return poses

    def local_channels(self,frame):
        loc,q=self.offset(MODEL,frame);obj=self.data['object_matrices'][frame]@matrix(loc,q)
        poses=np.linalg.inv(obj)@self.transforms(frame);locations=[];quaternions=[];scales=[]
        for i,parent in enumerate(self.parents):
            basis=np.linalg.inv(self.rest_local[i])@(np.linalg.inv(poses[parent]) if parent>=0 else np.eye(4))@poses[i]
            s=np.linalg.norm(basis[:3,:3],axis=0);locations.append(basis[:3,3]);quaternions.append(matrix_quaternion(basis[:3,:3]/s));scales.append(s)
        return np.array(locations),np.array(quaternions),np.array(scales)

    def proportional_offsets(self,name,frame,location,angles,radius=0):
        values={name:(np.asarray(location),quaternion(angles))}
        if not radius or name==MODEL or name not in self.names:return values
        old_loc,old_q=self.offset(name,frame);delta=multiply(old_q*np.array([1,-1,-1,-1]),quaternion(angles))
        parent=self.parents[self.names.index(name)]
        for depth in range(1,radius+1):
            if parent<0 or self.names[parent] in ('pelvis','root'):break
            n=self.names[parent];loc,q=self.offset(n,frame);weight=.3*(1-depth/(radius+1))**2
            values[n]=(loc,multiply(q,slerp(np.array([1.,0,0,0]),delta,weight)))
            if n.startswith(('clavicle','thigh')):break
            parent=self.parents[parent]
        if len(values)>1:
            index=self.names.index(name)
            desired=self.transforms(frame,{name:values[name]},ik=False)[index,:3,:3]
            actual=self.transforms(frame,values,ik=False)[index,:3,:3]
            q=values[name][1];prefix=actual@rotation(q).T
            values[name]=(values[name][0],matrix_quaternion(np.linalg.inv(prefix)@desired))
        return values

    def vertices(self,poses):
        transforms=poses@self.inverse_rest
        v=self.data['vertices'];ids=self.data['weight_ids'];weights=self.data['weights']
        result=np.zeros((len(v),3))
        for slot in range(ids.shape[1]):
            m=transforms[ids[:,slot]]
            result+=(np.einsum('nij,nj->ni',m[:,:3,:3],v)+m[:,:3,3])*weights[:,slot,None]
        return result

    def packet(self):
        return {'schema':'motion_animation_edits_v1','source_blend':self.info['source_blend'],
                'source_sha256':self.info['source_sha256'],'frames':self.count,'fps':self.fps,'edits':copy.deepcopy(self.edits),'options':{'limb_ik':self.limb_ik}}

    def save(self,path):
        path=Path(path);temp=path.with_suffix(path.suffix+'.pending');temp.write_text(json.dumps(self.packet(),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');temp.replace(path);self.dirty=False

    def load(self,path):
        p=json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(p,dict) or p.get('schema')!='motion_animation_edits_v1' or p.get('source_sha256')!=self.info['source_sha256'] or p.get('frames')!=self.count or p.get('fps')!=self.fps or not isinstance(p.get('edits'),dict):raise ValueError('이 애니메이션의 편집 파일이 아닙니다.')
        for n,track in p['edits'].items():
            if not isinstance(track,dict):raise ValueError('키프레임 형식이 잘못되었습니다.')
            for f,v in track.items():
                if not f.isdecimal() or str(int(f))!=f or not isinstance(v,dict) or 'location' not in v or 'rotation' not in v:raise ValueError('키프레임 형식이 잘못되었습니다.')
                self.validate_value(n,int(f),v['location'],v['rotation'])
        options=p.get('options',{})
        if not isinstance(options,dict) or type(options.get('limb_ik',False)) is not bool:raise ValueError('IK 옵션이 잘못되었습니다.')
        self.snapshot();self.edits=copy.deepcopy(p['edits']);self.limb_ik=options.get('limb_ik',False);self.dirty=False
