"""Select crop-hand shapes without merging independent 3D camera coordinates."""
import math

FINGERS=('thumb','index','middle','ring','pinky')

def sub(a,b):return [x-y for x,y in zip(a,b)]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def norm(a):return math.sqrt(dot(a,a))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def unit(a):return [x/norm(a) for x in a]


def shape(candidate):
    if not isinstance(candidate,dict):return None
    p=candidate.get('world_joints');xy=candidate.get('image_joints')
    if not isinstance(p,list) or len(p)!=21 or not isinstance(xy,list) or len(xy)!=21:return None
    if any(not isinstance(v,list) or len(v)!=n or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in v) for rows,n in [(p,3),(xy,2)] for v in rows):return None
    forward=sub(p[9],p[0]);width=sub(p[5],p[17]);length=norm(forward)
    if length<1e-5 or not .2<norm(width)/length<2:return None
    normal=cross(width,forward)
    if norm(normal)<norm(width)*length*.25:return None
    y=unit(forward);z=unit(normal);x=unit(cross(y,z));canonical=[];valid=[]
    for f,finger in enumerate(FINGERS):
        chain=p[1+f*4:5+f*4];edges=[sub(b,a) for a,b in zip(chain,chain[1:])]
        good=all(.04<norm(e)/length<1.2 for e in edges);valid.append(good)
        canonical.append([[dot(unit(e),axis) for axis in [x,y,z]] for e in edges] if good else None)
    if sum(valid)<3:return None
    return {'world_joints':p,'valid_fingers':[f for f,v in zip(FINGERS,valid) if v],'canonical':canonical}


def select_crop_hands(raw,crop):
    if crop.get('schema')!='hand_crop_comparison_v1' or crop.get('status')!='completed':raise ValueError('완료된 손 재추정 비교 결과가 필요합니다.')
    frames=raw['frames'];rows=crop.get('frames',[])
    if len(rows)!=len(frames) or any(r.get('frame_index')!=i for i,r in enumerate(rows)):raise ValueError('손 재추정 프레임이 다릅니다.')
    keys=[(r.get('tracking_segment',0),r.get('scene',{}).get('index',0)) for r in frames]
    selected=[{'l':None,'r':None} for _ in frames];notes=[];counts={'l':0,'r':0}
    for short,side,wrist in [('l','left',62),('r','right',41)]:
        possible=[]
        for i,(r,source) in enumerate(zip(rows,frames)):
            entry=r.get('hands',{}).get(side,{})
            candidate=entry.get('candidate');s=shape(candidate) if entry.get('status')=='associated_model_candidate' else None
            pixels=(source.get('outputs') or {}).get('pred_keypoints_2d');roi=entry.get('roi')
            tracked=source.get('tracking',{}).get('state')=='tracked' and source.get('roi') is not None
            if s is not None:
                w,h=raw['video']['width'],raw['video']['height'];q=candidate['image_joints']
                valid=tracked and pixels is not None and isinstance(roi,list) and len(roi)==4
                if valid:
                    scale=max(roi[2]-roi[0],roi[3]-roi[1]);anchor=pixels[wrist]
                    valid=scale>0 and len(anchor)==2 and all(math.isfinite(x) for x in anchor) and norm(sub(q[0],anchor))<=.3*scale
                    valid=valid and all(0<=p[0]<w and 0<=p[1]<h for p in q)
                if not valid:s=None
            possible.append(s)
        start=0
        while start<len(frames):
            if possible[start] is None:start+=1;continue
            end=start+1
            while end<len(frames) and possible[end] is not None and keys[end]==keys[start]:
                a,b=possible[end-1],possible[end];angles=[]
                for x,y in zip(a['canonical'],b['canonical']):
                    if x is not None and y is not None:
                        angles.extend(math.degrees(math.acos(max(-1,min(1,dot(u,v))))) for u,v in zip(x,y))
                if not angles or max(angles)>90:break
                end+=1
            if end-start>=3:
                for i in range(start,end):
                    selected[i][short]={k:v for k,v in possible[i].items() if k!='canonical'};counts[short]+=1
            else:notes.append({'side':short,'start':start,'end':end-1,'reason':'short_or_unstable_candidate_span'})
            start=end
    # Preserve ambiguity: a crossing/overlapping pair must not claim one wrist.
    for i,row in enumerate(selected):
        if row['l'] and row['r']:
            left=rows[i]['hands']['left']['candidate']['image_joints'][0];right=rows[i]['hands']['right']['candidate']['image_joints'][0]
            if norm(sub(left,right))<8:
                row['l']=row['r']=None;counts['l']-=1;counts['r']-=1;notes.append({'frame':i,'reason':'ambiguous_duplicate_wrist'})
    # Duplicate rejection can split a previously stable run into short fragments.
    for side in ('l','r'):
        start=0
        while start<len(selected):
            if selected[start][side] is None:start+=1;continue
            end=start+1
            while end<len(selected) and selected[end][side] is not None and keys[end]==keys[start]:end+=1
            if end-start<3:
                for i in range(start,end):selected[i][side]=None
            start=end
        counts[side]=sum(row[side] is not None for row in selected)
    return {'schema':'selected_hand_shapes_v1','frames':[{'frame_index':i,'hands':r} for i,r in enumerate(selected)],'selected_hand_frames':counts,'rejections':notes,'policy':{'minimum_consecutive_frames':3,'max_canonical_joint_change_degrees':90,'palm_relative_shape_only':True,'body_and_wrist_unchanged':True,'fallback':'original_SAM_fingers','accuracy_not_verified':True}}
