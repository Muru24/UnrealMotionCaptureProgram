"""Bound grip solve discontinuities without changing the tracked legs or torso."""
import bpy,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from grip_stability import smooth_quaternions,limit_wrist
from adaptive_deform import pose
source,out=map(Path,sys.argv[sys.argv.index('--')+1:]);out.mkdir(parents=True,exist_ok=False)
bpy.ops.wm.open_mainfile(filepath=str(source.resolve()));scene=bpy.context.scene;arm=next(o for o in scene.objects if o.type=='ARMATURE')
names=[p+'_'+s for s in ('l','r') for p in ('upperarm','lowerarm','hand')];samples={n:[] for n in names}
fps=scene.render.fps/scene.render.fps_base
for f in range(1,scene.frame_end+1):
 scene.frame_set(f)
 for n in names:samples[n].append(arm.pose.bones[n].rotation_quaternion.copy())
filtered={n:smooth_quaternions(v,fps,.045,420) for n,v in samples.items()}
for f in range(1,scene.frame_end+1):
 scene.frame_set(f)
 for n in names:
  p=arm.pose.bones[n];q=filtered[n][f-1];p.rotation_quaternion=limit_wrist(q,50,65) if n.startswith('hand') else q;p.keyframe_insert('rotation_quaternion',frame=f,group=n)
 pose(arm,f)
bpy.ops.wm.save_as_mainfile(filepath=str((out/'animation.blend').resolve()))
(out/'grip-stability.json').write_text(json.dumps({'status':'completed','frames':scene.frame_end,'fps':fps,'local_speed_limit_degrees_per_second':420,'smoothing_seconds':.045}),encoding='utf-8')
