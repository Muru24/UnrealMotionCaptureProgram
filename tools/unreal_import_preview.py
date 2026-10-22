"""UE Python commandlet: isolated reference animation import and editor preview map."""
import json,re,traceback
from pathlib import Path
import unreal
command=unreal.SystemLibrary.get_command_line()
match=re.search(r'-MotionRequest=(?:"([^"]+)"|(.*?)(?=\s+-|$))',command)
if not match:raise ValueError('MotionRequest is required')
request=json.loads(Path(match.group(1) or match.group(2)).read_text(encoding='utf-8'))
report={'passed':False,'engine_version':unreal.SystemLibrary.get_engine_version()}
try:
    options=unreal.FbxImportUI()
    options.set_editor_property('automated_import_should_detect_type',False)
    options.set_editor_property('mesh_type_to_import',unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    options.set_editor_property('import_as_skeletal',True)
    options.set_editor_property('import_mesh',True)
    options.set_editor_property('import_animations',True)
    options.set_editor_property('create_physics_asset',False)
    options.set_editor_property('import_materials',True)
    options.set_editor_property('import_textures',False)
    anim=options.get_editor_property('anim_sequence_import_data')
    anim.set_editor_property('animation_length',unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
    anim.set_editor_property('use_default_sample_rate',False)
    anim.set_editor_property('custom_sample_rate',30)
    anim.set_editor_property('remove_redundant_keys',False)
    task=unreal.AssetImportTask()
    for key,value in {'filename':request['fbx'],'destination_path':'/Game/MotionPreview','destination_name':'ReferenceMotion','automated':True,'save':True,'replace_existing':False,'options':options}.items():task.set_editor_property(key,value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths=list(task.get_editor_property('imported_object_paths'))
    assets=[unreal.load_asset(p) for p in paths]
    mesh=next(a for a in assets if isinstance(a,unreal.SkeletalMesh))
    clip=next(a for a in assets if isinstance(a,unreal.AnimSequence))
    skeleton=mesh.get_editor_property('skeleton')
    count=unreal.AnimationLibrary.get_num_frames(clip)
    duration=clip.get_editor_property('sequence_length')
    report.update(imported_assets=paths,mesh=mesh.get_path_name(),animation=clip.get_path_name(),frames=count,duration_seconds=duration,skeleton=skeleton.get_path_name())
    assert abs(duration-request['expected']['fbx_duration_seconds'])<1/30+.001,(duration,request['expected'])
    # Place the reference mesh with the imported animation selected for editor playback.
    world=unreal.EditorLevelLibrary.new_level('/Game/MotionPreview/Preview')
    actor=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SkeletalMeshActor,unreal.Vector(0,0,0))
    component=actor.get_editor_property('skeletal_mesh_component')
    component.set_skeletal_mesh_asset(mesh)
    names=[str(component.get_bone_name(i)) for i in range(component.get_num_bones())]
    assert len(names)==request['expected']['bones'],names
    samples=[]
    for seconds in (0.,duration/3,duration/2,duration):
        pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(clip,seconds,unreal.AnimPoseEvaluationOptions())
        positions={}
        for name in names:
            t=unreal.AnimPoseExtensions.get_bone_pose(pose,name,unreal.AnimPoseSpaces.WORLD)
            v=t.translation;positions[name]=[v.x,v.y,v.z]
        samples.append({'seconds':seconds,'positions_cm':positions})
    report.update(bone_names=names,bone_count=len(names),pose_samples=samples)
    component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    component.set_animation(clip)
    component.set_editor_property('animation_data',unreal.SingleAnimationPlayData(anim_to_play=clip,saved_looping=True,saved_playing=True))
    component.set_update_animation_in_editor(True)
    actor.set_actor_label('Motion Reference (estimated)')
    floor=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(0,0,-2.5))
    floor.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube.Cube'))
    floor.set_actor_scale3d(unreal.Vector(4,4,.05));floor.set_actor_label('Estimated Ground')
    light=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,300),unreal.Rotator(pitch=-45,yaw=-40,roll=0))
    light.set_actor_label('Preview Light')
    unreal.EditorLevelLibrary.save_current_level()
    unreal.EditorAssetLibrary.save_directory('/Game/MotionPreview',only_if_is_dirty=False,recursive=True)
    report.update(passed=True,preview_map='/Game/MotionPreview/Preview',limits=['reference_mesh_only','no_target_retarget','NullRHI_import_check_not_visual_quality_review'])
except Exception:
    report['error']=traceback.format_exc();raise
finally:
    Path(request['report']).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
