"""Normalize an actual rigged FBX and bind known humanoid roles explicitly."""
import sys,json,hashlib
from pathlib import Path
import bpy
from mathutils import Vector


def run(source,key,out):
    source=Path(source).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'model.blend').exists():raise FileExistsError(out/'model.blend')
    signature=hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # Unreal's head/toe/fingertip bones may be real leaf joints, not FBX end markers.
    bpy.ops.import_scene.fbx(filepath=str(source),ignore_leaf_bones=False)
    arms=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    if len(arms)!=1:raise ValueError('단일 Humanoid 스켈레톤 FBX가 필요합니다.')
    arm=arms[0]
    bpy.ops.object.select_all(action='SELECT');bpy.context.view_layer.objects.active=arm
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    if not meshes or not any(any(m.type=='ARMATURE' and m.object==arm for m in o.modifiers) for o in meshes):raise ValueError('스킨 메시가 없습니다.')
    def norm(n):return n.split(':')[-1].lower().replace('_','').replace(' ','')
    lookup={norm(b.name):b.name for b in arm.data.bones}
    mapping={}
    aliases={'pelvis':['pelvis','hips'],'spine_01':['spine01','spine'],'spine_02':['spine05','upperchest','chest','spine02','spine2'],
             'neck_01':['neck01','neck'],'head':['head']}
    for side,prefix in [('l','Left'),('r','Right')]:
        for role,unity in [('clavicle','Shoulder'),('upperarm','UpperArm'),('lowerarm','LowerArm'),('hand','Hand'),('thigh','UpperLeg'),('calf','LowerLeg'),('foot','Foot'),('ball','Toes')]:
            extra={'UpperArm':'Arm','LowerArm':'ForeArm','UpperLeg':'UpLeg','LowerLeg':'Leg','Toes':'ToeBase'}.get(unity,unity)
            aliases[f'{role}_{side}']=[role+side,prefix+unity,prefix+extra]
    for role,choices in aliases.items():
        target=next((lookup[norm(c)] for c in choices if norm(c) in lookup),None)
        if target is None:raise ValueError('필수 본을 찾을 수 없습니다: '+role)
        mapping[target]={'source':role,'mode':'rest_delta' if role in ('pelvis','spine_01','spine_02','neck_01','head') or role.startswith(('foot_','ball_')) else 'direction'}
    for side,prefix in [('l','Left'),('r','Right')]:
        for finger in ('thumb','index','middle','ring','pinky'):
            for i in range(1,4):
                choices=[f'{finger}0{i}{side}',f'{prefix}Hand{finger.title()}{i}',f'{prefix}{finger.title()}{i}']
                target=next((lookup[norm(c)] for c in choices if norm(c) in lookup),None)
                if target:mapping[target]={'source':f'{finger}_0{i}_{side}','mode':'direction'}
    pelvis=next(n for n,r in mapping.items() if r['source']=='pelvis')
    root=arm.data.bones[pelvis]
    while root.parent:root=root.parent
    arm['motion_root_bone']=root.name
    points=[o.matrix_world@Vector(c) for o in meshes for c in o.bound_box]
    height=max(p.z for p in points)-min(p.z for p in points)
    if not .5<height<3:raise ValueError(f'FBX 단위가 예상과 다릅니다: 높이 {height:.3f}m')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
    profile={'schema':'builtin_humanoid_v1','id':key,'source_fbx':str(source),'source_sha256':signature,
             'mapping':mapping,'root':root.name,'pelvis':pelvis,'height_m':height,'bones':len(arm.data.bones),
             'model_sha256':hashlib.sha256((out/'model.blend').read_bytes()).hexdigest()}
    (out/'profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf-8')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==signature
    print('BUILTIN_MODEL_READY',key,height,len(mapping),flush=True)


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
