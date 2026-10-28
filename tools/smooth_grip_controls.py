"""Remove high-frequency arm and forearm-roll impulses without changing wrists."""
import sys,json,hashlib
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent));from grip_stability import smooth_quaternions


def run(source,out):
    source=Path(source).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False);signature=hashlib.sha256(source.read_bytes()).hexdigest();r=json.loads(source.with_name('report.json').read_text(encoding='utf-8'));bpy.ops.wm.open_mainfile(filepath=str(source));arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');scene=bpy.context.scene
    names=['左腕','左ひじ','右腕','右ひじ','左腕捩','右腕捩','左手捩','右手捩'];times=[x['frame'] for x in r['baked_sample_results']];values={n:[] for n in names}
    for f in times:
        scene.frame_set(int(f),subframe=f%1)
        for n in names:values[n].append(arm.pose.bones[n].rotation_quaternion.copy())
    filtered={n:smooth_quaternions(v,r['fps']*4,.10 if '捩' in n else .065,120 if '捩' in n else 240) for n,v in values.items()}
    for i,f in enumerate(times):
        for n in names:arm.pose.bones[n].rotation_quaternion=filtered[n][i];arm.pose.bones[n].keyframe_insert('rotation_quaternion',frame=f,group=n)
    scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'animation.blend'));assert hashlib.sha256(source.read_bytes()).hexdigest()==signature
    r['input_sha256'][str(source)]=signature;r['policy'].update(final_arm_filter_seconds=.065,final_forearm_roll_filter_seconds=.10,final_forearm_roll_speed_degrees_per_second=120)
    (out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print('ARM_ROLL_FILTER_DONE',flush=True)


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
