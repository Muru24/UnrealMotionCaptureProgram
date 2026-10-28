"""Project a filtered grip onto the shaft without discrete forearm-roll searches."""
import bpy,sys,json
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fit_humanoid_sword_grip import reach
from grip_sword import set_world
from grip_stability import limit_wrist
from hand_retarget import palm_frame
from adaptive_deform import pose
source,reportpath,out=map(Path,sys.argv[sys.argv.index('--')+1:]);out.mkdir(parents=True,exist_ok=False)
bpy.ops.wm.open_mainfile(filepath=str(source.resolve()));scene=bpy.context.scene;arm=next(o for o in scene.objects if o.type=='ARMATURE');sword=bpy.data.objects['GripSword'];report=json.loads(reportpath.read_text())
palm=palm_frame(arm,*[n+'_l' for n in ('hand','index_01','middle_01','pinky_01')]);length=(arm.data.bones['middle_01_l'].head_local-arm.data.bones['hand_l'].head_local).length
off=palm.col[1]*length*.8-palm.col[2]*report['shaft_radius_m']*1.4;names=[n+'_'+s for s in ('l','r') for n in ('upperarm','lowerarm','hand')]
for f in range(1,scene.frame_end+1):
 scene.frame_set(f);left=arm.pose.bones['hand_l'];right=arm.pose.bones['hand_r'];lr=left.matrix.to_3x3().copy();rr=right.matrix.to_3x3().copy()
 for iteration in range(14):
  delta=right.matrix@right.bone.matrix_local.inverted();anchor=delta@Vector(sword['grip_anchor_rest']);axis=(delta.to_3x3()@Vector(sword['grip_axis_rest'])).normalized();target=anchor-axis*report['grip_distance_m']
  rot=left.matrix.to_3x3()@left.bone.matrix_local.to_3x3().transposed();residual=left.head+rot@off-target
  if residual.length<.002:break
  reach(arm,'l',target-rot@off);set_world(arm,left,lr);left.rotation_quaternion=limit_wrist(left.rotation_quaternion,50,65);bpy.context.view_layer.update()
  rot=left.matrix.to_3x3()@left.bone.matrix_local.to_3x3().transposed();residual=left.head+rot@off-target
  if residual.length>.008:
   reach(arm,'r',right.head+residual*.65);set_world(arm,right,rr);right.rotation_quaternion=limit_wrist(right.rotation_quaternion,50,65);bpy.context.view_layer.update()
 for n in names:arm.pose.bones[n].keyframe_insert('rotation_quaternion',frame=f,group=n)
 pose(arm,f)
bpy.ops.wm.save_as_mainfile(filepath=str((out/'animation.blend').resolve()))
