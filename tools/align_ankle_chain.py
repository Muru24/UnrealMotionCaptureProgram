"""Align shin axial rotation to foot heading while preserving knee/ankle anchors."""
import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector,Quaternion
sys.path.insert(0,str(Path(__file__).resolve().parent))
from grip_sword import set_world
from adaptive_deform import pose
source,out=map(Path,sys.argv[sys.argv.index('--')+1:]);out.mkdir(parents=True,exist_ok=False)
bpy.ops.wm.open_mainfile(filepath=str(source.resolve()));scene=bpy.context.scene;arm=next(o for o in scene.objects if o.type=='ARMATURE');rows=[];anchor_error=0.
for f in range(1,scene.frame_end+1):
 scene.frame_set(f)
 for side in ('l','r'):
  calf=arm.pose.bones['calf_'+side];foot=arm.pose.bones['foot_'+side];before=foot.matrix.copy();anchor=foot.head.copy();axis=(calf.tail-calf.head).normalized()
  cd=calf.matrix.to_3x3()@calf.bone.matrix_local.to_3x3().transposed();fd=foot.matrix.to_3x3()@foot.bone.matrix_local.to_3x3().transposed()
  a=cd@Vector((0,-1,0));b=fd@Vector((0,-1,0));a-=axis*a.dot(axis);b-=axis*b.dot(axis)
  angle=0.
  if min(a.length,b.length)>.05:
   a.normalize();b.normalize();angle=math.atan2(axis.dot(a.cross(b)),a.dot(b))
  set_world(arm,calf,Quaternion(axis,angle).to_matrix()@calf.matrix.to_3x3());set_world(arm,foot,before.to_3x3());bpy.context.view_layer.update()
  anchor_error=max(anchor_error,(foot.head-anchor).length)
  calf.keyframe_insert('rotation_quaternion',frame=f,group=calf.name);foot.keyframe_insert('rotation_quaternion',frame=f,group=foot.name)
  rows.append({'frame':f,'side':side,'shin_roll_correction_degrees':math.degrees(angle)})
 pose(arm,f)
 # A shin aligned to the foot already has its anatomical roll resolved.
 # Cancelling that roll again on its helpers recreates a twisted calf surface.
 for row in json.loads(arm.get('motion_deform_helpers','[]')):
  if row['parent'].startswith('calf_'):
   helper=arm.pose.bones[row['name']];helper.rotation_quaternion=Quaternion();helper.keyframe_insert('rotation_quaternion',frame=f,group=helper.name)
assert anchor_error<1e-5,anchor_error
bpy.ops.wm.save_as_mainfile(filepath=str((out/'animation.blend').resolve()))
(out/'ankle-chain-report.json').write_text(json.dumps({'status':'completed','frames':scene.frame_end,'max_ankle_anchor_error_m':anchor_error,'rows':rows},indent=2),encoding='utf-8')
