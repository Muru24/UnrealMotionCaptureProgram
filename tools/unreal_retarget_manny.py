"""UE 5.8 commandlet: explicit MotionHumanoid22 -> template Manny retarget."""
import json, traceback, re, sys
from pathlib import Path
import unreal as u
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from manny_leg_alignment import correct_unreal_animation
report={'passed':False}
try:
    source_match=re.search(r'-MannySource=(/Game/[A-Za-z0-9_/]+)(?:\s|$)',u.SystemLibrary.get_command_line())
    source_folder=globals().get('BATCH_SOURCE') or (source_match.group(1) if source_match else '/Game/MotionPreview')
    source=u.load_asset(source_folder+'/ReferenceMotion')
    target=u.load_asset('/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple')
    assert source and target
    tools=u.AssetToolsHelpers.get_asset_tools()
    match=re.search(r'-MannyOutput=(/Game/[A-Za-z0-9_/]+)(?:\s|$)',u.SystemLibrary.get_command_line())
    folder=globals().get('BATCH_FOLDER') or (match.group(1) if match else '/Game/MannyMotion')
    def create(name,cls,factory):
        assert not u.EditorAssetLibrary.does_asset_exist(folder+'/'+name),name
        return tools.create_asset(name,folder,cls,factory)
    rigs=[]
    chains={'Spine':('spine_01','spine_02','spine_01','spine_05'),
            'Neck':('neck_01','head','neck_01','head')}
    for side in ('l','r'):
        chains.update({f'Clavicle_{side}':(f'clavicle_{side}',)*4,
                       f'Arm_{side}':(f'upperarm_{side}',f'hand_{side}',f'upperarm_{side}',f'hand_{side}'),
                       f'Leg_{side}':(f'thigh_{side}',f'ball_{side}',f'thigh_{side}',f'ball_{side}')})
        if globals().get('BATCH_FINGERS') or '-MannyFingers' in u.SystemLibrary.get_command_line():
            for finger in ('thumb','index','middle','ring','pinky'):
                chains[f'{finger}_{side}']=(f'{finger}_01_{side}',f'{finger}_03_{side}',f'{finger}_01_{side}',f'{finger}_03_{side}')
    for index,(name,mesh) in enumerate((('IK_Motion22',source),('IK_Manny',target))):
        rig=create(name,u.IKRigDefinition,u.IKRigDefinitionFactory())
        c=u.IKRigController.get_controller(rig)
        assert c.set_skeletal_mesh(mesh)
        assert c.set_retarget_root('pelvis')
        for chain,bones in chains.items():
            c.add_retarget_chain(chain,bones[index*2],bones[index*2+1],'')
        rigs.append(rig)
    rtg=create('RTG_Motion22_Manny',u.IKRetargeter,u.IKRetargetFactory())
    c=u.IKRetargeterController.get_controller(rtg)
    c.set_ik_rig(u.RetargetSourceOrTarget.SOURCE,rigs[0])
    c.set_ik_rig(u.RetargetSourceOrTarget.TARGET,rigs[1])
    c.set_preview_mesh(u.RetargetSourceOrTarget.SOURCE,source)
    c.set_preview_mesh(u.RetargetSourceOrTarget.TARGET,target)
    c.add_default_ops()
    for chain in chains:
        assert c.set_source_chain(chain,chain),chain
    c.auto_align_all_bones(u.RetargetSourceOrTarget.TARGET,u.RetargetAutoAlignMethod.CHAIN_TO_CHAIN)
    clip=u.load_asset(source_folder+'/ReferenceMotion_Anim')
    inputs=u.IKRetargetBatchOperationInputs()
    for key,value in {'assets_to_retarget':[u.EditorAssetLibrary.find_asset_data(clip.get_path_name())],
                      'source_mesh':source,'target_mesh':target,'ik_retarget_asset':rtg,
                      'prefix':'Manny_','target_path':folder,'include_referenced_assets':False}.items():
        inputs.set_editor_property(key,value)
    result=u.IKRetargetBatchOperation.run_batch_retarget(inputs)
    report['results']=[str(x.package_name) for x in result]
    anim=next(x.get_asset() for x in result if isinstance(x.get_asset(),u.AnimSequence))
    uncorrected=tools.duplicate_asset('Manny_Uncorrected',folder,anim)
    report['leg_alignment']=correct_unreal_animation(anim,target)
    report['uncorrected_comparison']=uncorrected.get_path_name()
    assert anim.get_editor_property('skeleton')==target.get_editor_property('skeleton')
    duration=anim.get_editor_property('sequence_length')
    assert abs(duration-clip.get_editor_property('sequence_length'))<.001
    samples=[]
    for t in (0.,duration/3,duration/2,duration):
        pose=u.AnimPoseExtensions.get_anim_pose_at_time(anim,t,u.AnimPoseEvaluationOptions())
        positions={}
        for bone in ('root','pelvis','head','hand_l','hand_r','foot_l','foot_r'):
            p=u.AnimPoseExtensions.get_bone_pose(pose,bone,u.AnimPoseSpaces.WORLD).translation
            positions[bone]=[p.x,p.y,p.z]
        samples.append({'seconds':t,'positions_cm':positions})
    u.EditorAssetLibrary.save_directory(folder,only_if_is_dirty=False,recursive=True)
    report.update(passed=True,animation=anim.get_path_name(),target_mesh=target.get_path_name(),
                  skeleton=target.get_editor_property('skeleton').get_path_name(),duration=duration,
                  frames=u.AnimationLibrary.get_num_frames(anim),samples=samples,
                  chains={k:list(v) for k,v in chains.items()},ops=c.get_num_retarget_ops())
except Exception:
    report['error']=traceback.format_exc()
    raise
finally:
    version=re.search(r'MannyLegFix(\d+)$',folder)
    report_dir=Path(globals()['BATCH_REPORT']) if globals().get('BATCH_REPORT') else ROOT/'validation'/('manny-leg-fix'+version.group(1) if version else 'manny-leg-fix');report_dir.mkdir(exist_ok=True)
    (report_dir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
