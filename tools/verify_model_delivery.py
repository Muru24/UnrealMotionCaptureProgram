"""Blender-side round-trip check of a separated custom-model delivery."""
import bpy,json,sys,math
from pathlib import Path
def run(preview):
    preview=Path(preview).resolve();root=Path(__file__).resolve().parents[1];meta=json.loads(preview.with_suffix('.json').read_text(encoding='utf-8'));out=preview.parent
    registry=json.loads((root/'assets/user_models'/meta['model_id']/'registry.json').read_text(encoding='utf-8'));expected=registry['bones']
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.fbx(filepath=str(out/'Model_Animation.fbx'),ignore_leaf_bones=False,anim_offset=0.)
    arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');assert len(arm.data.bones)==expected;assert arm.animation_data and arm.animation_data.action
    for frame in (1,max(1,meta['frames']//2),meta['frames']):
        bpy.context.scene.frame_set(frame)
        assert all(math.isfinite(x) for p in arm.pose.bones for row in p.matrix for x in row)
    report={'status':'completed','bones':expected,'frames':meta['frames'],'fbx_animation_present':True,'finite_sampled_poses':True,'engine_playback_verified':False}
    (out/'delivery-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('DELIVERY_ROUND_TRIP_PASS',report,flush=True)
if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
