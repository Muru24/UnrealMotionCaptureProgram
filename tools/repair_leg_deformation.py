"""Resolve a humanoid leg's roll from its knee plane, retaining tracked anchors.

Opt-in repair for landmark-rigged models; does not change source motion or grips.
"""
import bpy,json,sys,math,hashlib
from pathlib import Path
from mathutils import Vector,Matrix,Quaternion
sys.path.insert(0,str(Path(__file__).resolve().parent))
from grip_sword import set_world

def frame(direction,front):
 y=direction.normalized();z=front-y*front.dot(y)
 if z.length<1e-6:raise ValueError('Degenerate leg frame')
 z.normalize();x=y.cross(z).normalized();return Matrix((x,y,z)).transposed()

def run(source,out):
 source,out=Path(source).resolve(),Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
 signature=hashlib.sha256(source.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(source));scene=bpy.context.scene;arm=next(o for o in scene.objects if o.type=='ARMATURE')
 helpers=json.loads(arm.get('motion_deform_helpers','[]'));leghelpers=[r['name'] for r in helpers if r['parent'].startswith(('thigh_','calf_'))]
 rest={};previous={};rows=[];max_error=0.;prior_rotations={};maximum_steps={}
 for side in ('l','r'):
  a,b,c=[arm.data.bones[n+'_'+side] for n in ('thigh','calf','foot')];axis=(c.head_local-a.head_local).normalized();front=b.head_local-a.head_local-axis*(b.head_local-a.head_local).dot(axis)
  if front.length<1e-5:front=Vector((0,-1,0))
  rest[side]={p:frame(q.tail_local-q.head_local,front).transposed()@q.matrix_local.to_3x3() for p,q in [('thigh',a),('calf',b)]}
 for f in range(1,scene.frame_end+1):
  scene.frame_set(f);before={p.name:p.matrix.copy() for p in arm.pose.bones};anchors={n:arm.pose.bones[n].head.copy() for n in ('thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r')}
  for side in ('l','r'):
   a,b,c=[arm.pose.bones[n+'_'+side] for n in ('thigh','calf','foot')];h,k,e=[p.head.copy() for p in (a,b,c)];axis=(e-h).normalized();front=k-h-axis*(k-h).dot(axis)
   fd=c.matrix.to_3x3()@c.bone.matrix_local.to_3x3().transposed();fallback=fd@Vector((0,-1,0));fallback-=axis*fallback.dot(axis)
   if fallback.length<1e-5:fallback=previous.get(side,Vector((0,-1,0)))
   fallback.normalize();reliability=min(1.,front.length/(min(a.length,b.length)*.10))
   if front.length>1e-6:front.normalize();front=front*reliability+fallback*(1-reliability)
   else:front=fallback
   front.normalize();previous[side]=front.copy()
   set_world(arm,a,frame(k-h,front)@rest[side]['thigh']);set_world(arm,b,frame(e-k,front)@rest[side]['calf']);set_world(arm,c,before[c.name].to_3x3())
   for p in (a,b,c):p.keyframe_insert('rotation_quaternion',frame=f,group=p.name)
   # Helpers share the resolved anatomical frame. Local twist cancellation
   # would undo this calibration and reintroduce a half turn near the ankle.
   for name in leghelpers:
    p=arm.pose.bones[name];p.rotation_quaternion=Quaternion();p.keyframe_insert('rotation_quaternion',frame=f,group=name)
   bpy.context.view_layer.update()
  error=max((arm.pose.bones[n].head-pos).length for n,pos in anchors.items());max_error=max(max_error,error)
  for n,m in before.items():
   if n not in leghelpers and not n.startswith(('thigh_','calf_','foot_')):
    assert max(abs(arm.pose.bones[n].matrix[i][j]-m[i][j]) for i in range(4) for j in range(4))<1e-5,n
  for name in ('thigh_l','calf_l','thigh_r','calf_r'):
   q=arm.pose.bones[name].matrix.to_quaternion()
   if name in prior_rotations:
    angle=prior_rotations[name].rotation_difference(q).angle;maximum_steps[name]=max(maximum_steps.get(name,0.),math.degrees(min(angle,2*math.pi-angle)))
   prior_rotations[name]=q
  rows.append({'frame':f,'max_joint_anchor_error_m':error})
 assert max_error<1e-5,max_error
 for obj in scene.objects:
  for modifier in obj.modifiers:
   if modifier.type=='ARMATURE' and modifier.object==arm:modifier.use_deform_preserve_volume=False
 scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'animation.blend'))
 assert hashlib.sha256(source.read_bytes()).hexdigest()==signature
 (out/'leg-repair.json').write_text(json.dumps({'status':'completed','frames':scene.frame_end,'fps':scene.render.fps/scene.render.fps_base,'source_sha256':signature,'max_joint_anchor_error_m':max_error,'max_world_rotation_step_degrees':maximum_steps,'method':'knee-plane rest calibration; coherent thigh and calf helpers; engine-compatible linear skin','rows':rows},indent=2),encoding='utf-8')

if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
