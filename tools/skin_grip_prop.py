"""Preserve the fitted rigid sword in both the editor skin and skeletal FBX."""
import sys,json,hashlib
from pathlib import Path
import bpy
from mathutils import Matrix

source,out=map(lambda p:Path(p).resolve(),sys.argv[sys.argv.index('--')+1:])
out.mkdir(exist_ok=False);signature=hashlib.sha256(source.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(source));scene=bpy.context.scene;scene.frame_set(1)
arm=next(o for o in scene.objects if o.type=='ARMATURE');sword=bpy.data.objects['GripSword']
world=sword.matrix_world.copy();hand=arm.pose.bones['hand_r'];rest=hand.bone.matrix_local
bind=rest@hand.matrix.inverted()@arm.matrix_world.inverted()@world
sword.animation_data_clear();sword.parent=None
sword.data.transform(bind);sword.parent=arm;sword.parent_type='OBJECT';sword.matrix_parent_inverse=Matrix.Identity(4)
sword.matrix_world=arm.matrix_world.copy();group=sword.vertex_groups.new(name='hand_r')
group.add(list(range(len(sword.data.vertices))),1.,'REPLACE');modifier=sword.modifiers.new('RigidHandSocket','ARMATURE');modifier.object=arm
sword['grip_anchor_rest']=list(bind.translation);sword['grip_axis_rest']=list(bind.to_3x3().col[2]);sword['grip_front_rest']=list(bind.to_3x3().col[1])
arm['motion_preserve_materials']=True;bpy.ops.wm.save_as_mainfile(filepath=str(out/'animation.blend'))
assert hashlib.sha256(source.read_bytes()).hexdigest()==signature
(out/'prop-binding.json').write_text(json.dumps({'status':'completed','bone':'hand_r','vertices':len(sword.data.vertices),
    'source_sha256':signature,'binding':'rigid armature skin for editor and FBX'}),encoding='utf-8')
