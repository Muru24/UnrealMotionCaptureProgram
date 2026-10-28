"""Run the validated engine retargeter, then export its evaluated Manny poses."""
import json,re,runpy,traceback
from pathlib import Path
import unreal as u

root=Path(__file__).resolve().parents[1]
match=re.search(r'-MotionRequest="([^"]+)"',u.SystemLibrary.get_command_line())
if not match:raise ValueError('MotionRequest required')
request=json.loads(Path(match.group(1)).read_text(encoding='utf-8'))
out=Path(request['out']);result={'status':'failed'}
try:
    runpy.run_path(str(root/'tools/unreal_import_preview.py'))
    ns=runpy.run_path(str(root/'tools/unreal_retarget_manny.py'),init_globals={
        'BATCH_SOURCE':request['destination'],'BATCH_FOLDER':request['target'],
        'BATCH_REPORT':str(out),'BATCH_FINGERS':True})
    report=ns['report'];assert report['passed']
    clip=u.load_asset(report['animation']);mesh=u.load_asset(report['target_mesh'])
    actor=u.EditorLevelLibrary.spawn_actor_from_class(u.SkeletalMeshActor,u.Vector())
    component=actor.skeletal_mesh_component;component.set_skeletal_mesh_asset(mesh)
    names=[str(component.get_bone_name(i)) for i in range(component.get_num_bones())]
    options=u.AnimPoseEvaluationOptions();duration=clip.get_editor_property('sequence_length')
    fps=request['preview_fps'];count=request['preview_frames']
    def transform(t):
        return {'p':[t.translation.x,t.translation.y,t.translation.z],
                'q':[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w],
                's':[t.scale3d.x,t.scale3d.y,t.scale3d.z]}
    rows=[];reference={}
    for i in range(count):
        pose=u.AnimPoseExtensions.get_anim_pose_at_time(clip,min(i/fps,duration),options)
        if i==0:reference={n:transform(u.AnimPoseExtensions.get_ref_bone_pose(pose,n,u.AnimPoseSpaces.WORLD)) for n in names}
        rows.append({n:transform(u.AnimPoseExtensions.get_bone_pose(pose,n,u.AnimPoseSpaces.WORLD)) for n in names})
    result={'status':'completed','pipeline':'unreal_ik_retarget_with_manny_leg_alignment',
            'animation':report['animation'],'target_mesh':report['target_mesh'],
            'fps':fps,'frames':rows,'reference':reference,'duration_seconds':duration}
    (out/'unreal-poses.json').write_text(json.dumps(result,allow_nan=False),encoding='utf-8')
finally:
    (out/'engine-status.json').write_text(json.dumps({'status':result['status']},indent=2),encoding='utf-8')
