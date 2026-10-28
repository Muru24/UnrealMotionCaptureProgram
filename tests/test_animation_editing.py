import json
from pathlib import Path
import numpy as np
import pytest
from app.editable_animation import EditableAnimation,MODEL,rotation


@pytest.fixture
def scene(tmp_path):
    rest=np.repeat(np.eye(4)[None],2,axis=0);rest[1,2,3]=1
    (tmp_path/'scene.json').write_text(json.dumps({'source_blend':'test.blend','source_sha256':'source',
        'names':['pelvis','hand_l'],'parents':[-1,0],'fps':30,'frames':5,'frame_start':1}))
    np.savez(tmp_path/'scene.npz',vertices=np.array([[0.,0,2]]),triangles=np.empty((0,3),int),
        weight_ids=np.array([[1]]),weights=np.array([[1.]]),rest=rest,
        locations=np.zeros((5,2,3)),quaternions=np.tile([1.,0,0,0],(5,2,1)),scales=np.ones((5,2,3)),object_matrices=np.tile(np.eye(4),(5,1,1)))
    return EditableAnimation(tmp_path)


def test_bone_and_model_offsets_skin_and_undo_without_mutating_base(scene):
    before=scene.data['locations'].copy()
    scene.set_key('hand_l',2,[.1,0,0],[0,0,0])
    assert scene.transforms(2)[1,0,3]==pytest.approx(.1)
    assert scene.transforms(1)[1,0,3]==pytest.approx(.05)
    assert scene.transforms(0)[1,0,3]==0
    np.testing.assert_allclose(scene.vertices(scene.transforms(2)),[[.1,0,2]])
    scene.set_key(MODEL,0,[1,0,0],[0,0,90],whole=True)
    np.testing.assert_allclose(scene.vertices(scene.transforms(2)),[[1,.1,2]],atol=1e-10)
    scene.undo();assert MODEL not in scene.edits
    scene.undo(redo=True);assert MODEL in scene.edits
    np.testing.assert_array_equal(scene.data['locations'],before)


def test_quaternion_keys_cross_180_without_euler_flip(scene):
    scene.set_key('hand_l',0,[0,0,0],[0,0,179]);scene.set_key('hand_l',4,[0,0,0],[0,0,-179])
    _,q=scene.offset('hand_l',2)
    np.testing.assert_allclose(rotation(q)@np.array([1,0,0]),[-1,0,0],atol=1e-8)


def test_project_roundtrip_and_provenance_rejects_other_animation(scene,tmp_path):
    scene.set_key('hand_l',2,[.1,0,0],[15,0,0]);p=tmp_path/'edits.json';scene.save(p)
    original=scene.transforms(2);scene.delete_key('hand_l',2);scene.load(p)
    np.testing.assert_allclose(scene.transforms(2),original)
    packet=json.loads(p.read_text());packet['source_sha256']='other';p.write_text(json.dumps(packet))
    with pytest.raises(ValueError):scene.load(p)
    with pytest.raises(ValueError):scene.set_key('missing',0,[0,0,0],[0,0,0])
    with pytest.raises(ValueError):scene.set_key('hand_l',5,[0,0,0],[0,0,0])
    with pytest.raises(ValueError):scene.set_key('hand_l',0,[float('nan'),0,0],[0,0,0])
    packet['source_sha256']='source';packet['edits']={'hand_l':{'01':{'location':[0,0,0],'rotation':[0,0,0]}}};p.write_text(json.dumps(packet))
    with pytest.raises(ValueError):scene.load(p)


def test_parent_rotation_propagates_to_child_skin(scene):
    scene.set_key('pelvis',0,[0,0,0],[90,0,0],whole=True)
    poses=scene.transforms(2)
    np.testing.assert_allclose(poses[1,:3,3],[0,-1,0],atol=1e-8)
    np.testing.assert_allclose(scene.vertices(poses),[[0,-2,0]],atol=1e-8)


def test_ik_moves_parent_joints_and_preserves_bone_lengths(tmp_path):
    names=['upperarm_l','lowerarm_l','hand_l'];rest=np.tile(np.eye(4),(3,1,1));rest[1,:3,3]=[1,0,.2];rest[2,:3,3]=[2,0,0]
    (tmp_path/'scene.json').write_text(json.dumps({'source_blend':'test.blend','source_sha256':'source','names':names,'parents':[-1,0,1],'fps':30,'frames':5,'frame_start':1}))
    np.savez(tmp_path/'scene.npz',vertices=np.array([[2.,0,0]]),triangles=np.empty((0,3),int),weight_ids=np.array([[2]]),weights=np.array([[1.]]),rest=rest,
        locations=np.zeros((5,3,3)),quaternions=np.tile([1.,0,0,0],(5,3,1)),scales=np.ones((5,3,3)),object_matrices=np.tile(np.eye(4),(5,1,1)))
    editor=EditableAnimation(tmp_path);before=editor.transforms(2)
    editor.set_key('hand_l',2,[-.2,.3,.1],[0,0,0]);after=editor.transforms(2)
    np.testing.assert_allclose(after[2,:3,3],[1.8,.3,.1],atol=1e-8)
    assert not np.allclose(before[1],after[1])
    np.testing.assert_allclose(np.linalg.norm(np.diff(after[:,:3,3],axis=0),axis=1),np.linalg.norm(np.diff(before[:,:3,3],axis=0),axis=1),atol=1e-8)
    locations,quaternions,scales=editor.local_channels(2)
    from app.editable_animation import matrix
    rebuilt=[]
    for i,parent in enumerate(editor.parents):rebuilt.append((np.eye(4) if parent<0 else rebuilt[parent])@editor.rest_local[i]@matrix(locations[i],quaternions[i],scales[i]))
    np.testing.assert_allclose(rebuilt,after,atol=1e-8)
    editor.set_key('hand_l',2,[100,0,0],[0,0,0]);far=editor.transforms(2)
    assert np.linalg.norm(far[2,:3,3]-far[0,:3,3])<2.04


def test_connected_proportional_rotation_is_one_undo_step(scene):
    values=scene.proportional_offsets('hand_l',2,[0,0,0],[30,0,0],radius=2)
    # The pelvis is intentionally protected from a hand's proportional falloff.
    assert list(values)==['hand_l']
    scene.set_keys({n:(loc,[30,0,0]) for n,(loc,q) in values.items()},2)
    assert scene.edits
    scene.undo();assert not scene.edits
