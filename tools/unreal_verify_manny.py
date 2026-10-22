"""Reopen Manny animation, check baked motion and save a separate preview level."""
import json,math,traceback
from pathlib import Path
import unreal as u
ROOT=Path(__file__).resolve().parents[1]
report={'passed':False}
try:
    mesh=u.load_asset('/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple')
    clip=u.load_asset('/Game/MannyMotion/Manny_ReferenceMotion_Anim')
    assert clip.get_editor_property('skeleton')==mesh.get_editor_property('skeleton')
    duration=clip.get_editor_property('sequence_length')
    assert u.AnimationLibrary.get_num_frames(clip)==446
    bones=('root','pelvis','head','upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r','thigh_l','calf_l','foot_l','thigh_r','calf_r','foot_r')
    pairs=(('upperarm_l','lowerarm_l'),('lowerarm_l','hand_l'),('thigh_l','calf_l'),('calf_l','foot_l'),('upperarm_r','lowerarm_r'),('lowerarm_r','hand_r'),('thigh_r','calf_r'),('calf_r','foot_r'))
    lengths={str(pair):[] for pair in pairs};positions=[]
    for i in range(447):
        pose=u.AnimPoseExtensions.get_anim_pose_at_time(clip,i/30,u.AnimPoseEvaluationOptions())
        data={}
        for bone in bones:
            p=u.AnimPoseExtensions.get_bone_pose(pose,bone,u.AnimPoseSpaces.WORLD).translation
            data[bone]=[p.x,p.y,p.z]
            assert all(math.isfinite(v) and abs(v)<100000 for v in data[bone]),(i,bone)
        for pair in pairs:lengths[str(pair)].append(math.dist(data[pair[0]],data[pair[1]]))
        positions.append(data)
    variation={k:max(v)-min(v) for k,v in lengths.items()}
    assert max(variation.values())<.05,variation
    root_travel=math.dist(positions[0]['root'],positions[-1]['root'])
    assert root_travel>100,'No root displacement'
    world=u.EditorLevelLibrary.new_level('/Game/MannyMotion/MannyPreview')
    actor=u.EditorLevelLibrary.spawn_actor_from_class(u.SkeletalMeshActor,u.Vector())
    actor.set_actor_label('Manny - LongSword Retarget')
    component=actor.skeletal_mesh_component
    component.set_skeletal_mesh_asset(mesh)
    component.set_animation_mode(u.AnimationMode.ANIMATION_SINGLE_NODE)
    component.set_animation(clip)
    component.set_editor_property('animation_data',u.SingleAnimationPlayData(anim_to_play=clip,saved_looping=True,saved_playing=True))
    component.set_update_animation_in_editor(True)
    floor=u.EditorLevelLibrary.spawn_actor_from_class(u.StaticMeshActor,u.Vector(-150,0,-5))
    floor.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'))
    floor.set_actor_scale3d(u.Vector(12,12,.1))
    light=u.EditorLevelLibrary.spawn_actor_from_class(u.DirectionalLight,u.Vector(0,0,300),u.Rotator(-45,-40,0))
    light.light_component.set_mobility(u.ComponentMobility.MOVABLE)
    light.light_component.set_editor_property('intensity',4.)
    u.EditorLevelLibrary.save_current_level()
    report.update(passed=True,frames_checked=447,finite_positions=True,limb_length_variation_cm=variation,
                  root_displacement_cm=root_travel,bone_count=component.get_num_bones(),
                  skeleton=clip.get_editor_property('skeleton').get_path_name(),preview_map='/Game/MannyMotion/MannyPreview',
                  limits=['LongSword only','finger/face motion not captured','ground/contact accuracy not ground-truth verified','no third-person locomotion AnimBlueprint replacement','no product GUI automation yet'])
except Exception:
    report['error']=traceback.format_exc();raise
finally:
    (ROOT/'validation/manny/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
