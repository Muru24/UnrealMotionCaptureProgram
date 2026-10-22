"""MHR70 to reference-humanoid positions; no rotation or world-root solver."""
from pathlib import Path
import json
import numpy as np
from core.video.limits import MAX_VIDEO_FRAMES

DEFINITION=Path(__file__).resolve().parents[2]/'assets/skeletons/humanoid_v1.json'
AXIS=np.array([[1.,0.,0.],[0.,0.,1.],[0.,-1.,0.]])
MHR={1:'left-eye',2:'right-eye',3:'left-ear',4:'right-ear',5:'left-shoulder',6:'right-shoulder',7:'left-elbow',8:'right-elbow',
     9:'left-hip',10:'right-hip',11:'left-knee',12:'right-knee',13:'left-ankle',14:'right-ankle',
     15:'left-big-toe-tip',16:'left-small-toe-tip',18:'right-big-toe-tip',19:'right-small-toe-tip',
     41:'right-wrist',62:'left-wrist',69:'neck'}


def definition():
    data=json.loads(DEFINITION.read_text(encoding='utf-8'))
    bones=data['bones'];names=[b['name'] for b in bones]
    if len(names)!=len(set(names)) or not bones or bones[0]['parent'] is not None:
        raise ValueError('Invalid standard skeleton names/root.')
    for i,bone in enumerate(bones):
        if i and bone['parent'] not in names[:i]:raise ValueError('Skeleton parent order differs.')
        if np.shape(bone['head'])!=(3,) or not np.isfinite(bone['head']).all():raise ValueError('Invalid reference position.')
    return data


def mapped(points):
    """Derived torso/head points are explicitly proxies, never measured bones."""
    q=np.asarray(points,float)
    if q.shape!=(70,3):raise ValueError('Expected MHR70 positions.')
    def point(i):return q[i] if np.isfinite(q[i]).all() else None
    def mix(a,b,t):return None if a is None or b is None else a*(1-t)+b*t
    pelvis=mix(point(9),point(10),.5);shoulders=mix(point(5),point(6),.5)
    heads=[point(i) for i in (1,2,3,4)]
    result={'root':pelvis,'pelvis':pelvis,'spine_01':mix(pelvis,shoulders,.35),
            'spine_02':mix(pelvis,shoulders,.75),'neck_01':point(69),
            'head':None if any(p is None for p in heads) else np.mean(heads,axis=0)}
    for side,shoulder,elbow,wrist,hip,knee,ankle,toes in (
            ('l',5,7,62,9,11,13,(15,16)),('r',6,8,41,10,12,14,(18,19))):
        result.update({f'clavicle_{side}':mix(shoulders,point(shoulder),.25),
            f'upperarm_{side}':point(shoulder),f'lowerarm_{side}':point(elbow),f'hand_{side}':point(wrist),
            f'thigh_{side}':point(hip),f'calf_{side}':point(knee),f'foot_{side}':point(ankle),
            f'ball_{side}':mix(point(toes[0]),point(toes[1]),.5)})
    return result,pelvis


def convert(raw,rows=None,*,source_kind='raw_sam3d',cancelled=lambda:False):
    spec=definition();bones=spec['bones'];names=[b['name'] for b in bones]
    mhr=raw.get('joint_names',[])
    if raw.get('schema')!='sam3d_mhr70' or len(mhr)!=70 or any(mhr[i]!=name for i,name in MHR.items()):
        raise ValueError('Motion conversion requires the native MHR70 schema and order.')
    frames=raw['frames'];fps=float(raw['video']['fps'])
    if not 0<len(frames)<=MAX_VIDEO_FRAMES or not np.isfinite(fps) or not 1<=fps<=240:
        raise ValueError('Invalid motion timeline.')
    if rows is not None and len(rows)!=len(frames):raise ValueError('Motion input timeline differs.')
    rest={b['name']:np.asarray(b['head'],float) for b in bones};output=[]
    for i,frame in enumerate(frames):
        if cancelled():raise KeyboardInterrupt
        if frame['frame_index']!=i or (rows is not None and rows[i]['frame_index']!=i):raise ValueError('Motion frame order differs.')
        row=rows[i] if rows is not None else None
        tracked=frame.get('tracking',{}).get('state')=='tracked' and frame.get('roi') is not None
        points=(frame.get('outputs') or {}).get('pred_keypoints_3d') if row is None else row.get('world_joints')
        valid=tracked and points is not None
        positions={};mapped_positions={};status={};origin=None
        if valid:
            source,origin=mapped(points)
            for bone in bones:
                name=bone['name'];parent=bone['parent'];point=source[name]
                if point is None or origin is None:
                    positions[name]=mapped_positions[name]=None;status[name]='missing_source';continue
                mapped_positions[name]=(AXIS@(point-origin)+rest['pelvis']).tolist()
                if name=='root':positions[name]=rest['root'].copy();status[name]='virtual_in_place_root'
                elif name=='pelvis':positions[name]=rest[name].copy();status[name]='in_place_pelvis'
                elif positions.get(parent) is None or source[parent] is None:
                    positions[name]=None;status[name]='missing_parent'
                else:
                    direction=AXIS@(point-source[parent]);length=float(np.linalg.norm(direction))
                    if length<1e-7:positions[name]=None;status[name]='degenerate_direction'
                    else:
                        positions[name]=positions[parent]+direction/length*np.linalg.norm(rest[name]-rest[parent])
                        status[name]='derived_model_proxy' if name in ('spine_01','spine_02','head') or name.startswith(('clavicle','ball')) else 'model_estimate'
        output.append({'frame_index':i,'timestamp':i/fps,
            'tracking_state':frame.get('tracking',{}).get('state','unavailable'),
            'tracking_segment':frame.get('tracking_segment',0),'scene_index':frame.get('scene',{}).get('index',0),
            'source_kind':source_kind,'source_changes':[] if row is None else row.get('changed_parts',row.get('reconnected_parts',[])),
            'source_pelvis_camera_m':None if origin is None else origin.tolist(),
            'mapped_positions':[mapped_positions.get(n) for n in names],
            'positions':[None if positions.get(n) is None else positions[n].tolist() for n in names],
            'joint_status':[status.get(n,'target_unavailable') for n in names]})
    return {'schema':'standard_motion_positions_v1','version':1,'skeleton':spec,'video':raw['video'],
        'units':'meters_reference_proportions','axes':'Blender right-handed X right, Y back, Z up; facing -Y',
        'source_to_standard_matrix':AXIS.tolist(),'root_motion':False,'bone_rotations':None,
        'source_kind':source_kind,'frames':output,
        'limits':['not_world_translation','not_rotation_animation','torso_head_are_derived_proxies',
                  'fixed_reference_proportions_not_measured_height','no_occlusion_recovery','no_foot_contact_solver']}
