"""Inspect a local model and prepare either rig preservation or a static rig plan."""
import hashlib,json,sys
from pathlib import Path
import bpy
import numpy as np


def guessed_landmarks(body, meshes, key):
    points=np.array([list(body.matrix_world@v.co) for v in body.data.vertices])
    lo,hi=points.min(axis=0),points.max(axis=0);height=float(hi[2]-lo[2])
    if height<=1e-5:raise ValueError('모델 높이를 확인할 수 없습니다.')
    center=(hi+lo)/2;cx,cy=center[:2];floor=lo[2]
    normalized=(points-np.array([cx,cy,floor]))/height
    half=float(np.quantile(abs(normalized[:,0]),.995))
    if not .14<half<.8:raise ValueError('정면을 향한 사람형 T/A 포즈 모델이 필요합니다.')
    outside=normalized[abs(normalized[:,0])>half*.9]
    tip_z=float(np.clip(np.median(outside[:,2]),.32,.86))
    bones=[]
    def pt(x,y,z):return [float(cx+x*height),float(cy+y*height),float(floor+z*height)]
    def add(n,p,h,t):bones.append(dict(name=n,parent=p,head=h,tail=t))
    add('root',None,pt(0,0,0),pt(0,0,.08))
    add('pelvis','root',pt(0,0,.52),pt(0,0,.60))
    add('spine_01','pelvis',pt(0,0,.60),pt(0,0,.70))
    add('spine_02','spine_01',pt(0,0,.70),pt(0,0,.84))
    add('neck_01','spine_02',pt(0,0,.84),pt(0,0,.90))
    add('head','neck_01',pt(0,0,.90),pt(0,0,.99))
    for side,s in [('l',1),('r',-1)]:
        def p(x,y,z):return pt(s*x,y,z)
        hand_points=normalized[normalized[:,0]*s>half*.9]
        tip=np.array(p(half,0,tip_z))
        if len(hand_points):tip[1]=float(cy+np.median(hand_points[:,1])*height)
        shoulder=np.array(p(.16,0,.79));direction=tip-shoulder;direction/=np.linalg.norm(direction)
        # Reserve the complete palm + middle-finger length inside the mesh.
        # A fixed percentage of reach placed fingertips beyond short T-pose hands.
        wrist=tip-direction*height*.104
        elbow=shoulder*.48+wrist*.52
        direction=(wrist-shoulder);direction/=np.linalg.norm(direction)
        palm=wrist+direction*height*.035
        for n,parent,h,t in [('clavicle','spine_02',p(.03,0,.80),shoulder),
            ('upperarm','clavicle_'+side,shoulder,elbow),('lowerarm','upperarm_'+side,elbow,wrist),
            ('hand','lowerarm_'+side,wrist,palm),('thigh','pelvis',p(.065,0,.52),p(.07,-.01,.29)),
            ('calf','thigh_'+side,p(.07,-.01,.29),p(.07,0,.065)),
            ('foot','calf_'+side,p(.07,0,.065),p(.07,-.07,.025)),
            ('ball','foot_'+side,p(.07,-.07,.025),p(.07,-.12,.025))]:
            add(n+'_'+side,parent,list(h),list(t))
        for finger,y,length in [('thumb',-.042,.045),('index',-.024,.061),('middle',-.008,.069),('ring',.009,.063),('pinky',.025,.050)]:
            base=palm+np.array([0,y*height,0])
            if finger=='thumb':base=wrist+direction*height*.02+np.array([0,y*height,0])
            for i in range(3):
                h=base+direction*height*length*i/3;t=base+direction*height*length*(i+1)/3
                add(f'{finger}_{i+1:02d}_{side}','hand_'+side if i==0 else f'{finger}_{i:02d}_{side}',h.tolist(),t.tolist())
    return dict(id=key,body_mesh=body.name,scale=1.8/height,offset=[-float(cx),-float(cy),-float(floor)],
        bones=bones,rigid_meshes={},proxy_vertices=30000,estimated=True,adaptive_deform=True)


def run(source,key,output):
    source,output=Path(source).resolve(),Path(output).resolve()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ext=source.suffix.lower()
    if ext=='.fbx':bpy.ops.import_scene.fbx(filepath=str(source),ignore_leaf_bones=False)
    elif ext in ('.glb','.gltf'):bpy.ops.import_scene.gltf(filepath=str(source))
    elif ext=='.obj':bpy.ops.wm.obj_import(filepath=str(source))
    elif ext=='.blend':
        # Append objects as data, without loading embedded scripts or startup handlers.
        with bpy.data.libraries.load(str(source),link=False) as (a,b):b.objects=a.objects
        for obj in b.objects:
            if obj is not None:bpy.context.collection.objects.link(obj)
    else:raise ValueError('FBX, GLB, GLTF, OBJ, BLEND 모델을 선택해 주세요.')
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    arms=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    if not meshes:raise ValueError('모델에 메시가 없습니다.')
    if len(arms)>1:raise ValueError('단일 사람형 스켈레톤 모델을 선택해 주세요.')
    for image in bpy.data.images:
        if image.source!='FILE' or Path(bpy.path.abspath(image.filepath)).is_file():continue
        name=Path(image.filepath.replace('\\','/')).name
        for folder in (source.parent,source.parent/'textures',source.parent.parent/'textures'):
            candidate=folder/name
            if candidate.is_file():image.filepath=str(candidate);image.reload();break
    signature=hashlib.sha256(source.read_bytes()).hexdigest()
    plan={'source_sha256':signature,'has_armature':bool(arms),'estimated':False}
    if not arms:
        profiles=Path(__file__).resolve().parents[1]/'assets/rigging_profiles'
        known=None
        for path in profiles.glob('*.json'):
            value=json.loads(path.read_text(encoding='utf-8'))
            if value.get('source_sha256')==signature:known=value;break
        settings=known or guessed_landmarks(max(meshes,key=lambda o:len(o.data.vertices)),meshes,key)
        settings['id']=key
        plan['estimated']=settings.get('estimated',False)
        (output/'landmarks.json').write_text(json.dumps(settings,indent=2),encoding='utf-8')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes+arms:obj.hide_set(False);obj.select_set(True)
    bpy.context.view_layer.objects.active=(arms+meshes)[0]
    bpy.ops.export_scene.fbx(filepath=str(output/'input.fbx'),use_selection=True,
        object_types={'ARMATURE','MESH'},add_leaf_bones=False,bake_anim=False,
        axis_forward='-Y',axis_up='Z',path_mode='COPY',embed_textures=True)
    (output/'inspection.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
