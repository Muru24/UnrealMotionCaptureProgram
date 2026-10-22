from copy import deepcopy
import numpy as np
import pytest
from core.pose3d.sam_completion import complete_sam


def sample():
    names=[str(i) for i in range(70)]
    for j,n in {9:'left-hip',10:'right-hip',11:'left-knee',12:'right-knee',13:'left-ankle',14:'right-ankle',17:'left-heel',20:'right-heel'}.items():names[j]=n
    xyz=np.zeros((70,3))
    for j,p in {5:[-.2,-.4,0],6:[.2,-.4,0],7:[-.4,-.2,0],8:[.4,-.2,0],62:[-.6,0,0],41:[.6,0,0],
                9:[-.15,0,0],10:[.15,0,0],11:[-.15,.4,0],12:[.15,.4,0],13:[-.15,.8,0],14:[.15,.8,0]}.items():xyz[j]=p
    for ankle,tips in ((13,(15,16,17)),(14,(18,19,20))):
        for j in tips:xyz[j]=xyz[ankle]+[0,.03,.06]
    for wrist,tips in ((62,range(42,62)),(41,range(21,41))):
        for j in tips:xyz[j]=xyz[wrist]+[.01,0,.02]
    return dict(schema='sam3d_mhr70',coordinates='sam_native_pred_keypoints_3d',joint_names=names,
                selection='sam2_video_mask',video=dict(width=400,height=400,fps=30),roi=[0,0,400,400],
                frames=[dict(frame_index=i,timestamp=i/30,tracking_segment=0,outputs=dict(
                    pred_keypoints_3d=xyz.tolist(),pred_keypoints_2d=(xyz[:,:2]*200+[200,150]).tolist())) for i in range(30)])


def spike(raw,start=10,width=1,parent=7,child=62,length=1.4):
    for i in range(start,start+width):
        f=raw['frames'][i]['outputs'];x=np.array(f['pred_keypoints_3d'])
        original=x[child].copy()
        x[child]=x[parent]-(x[child]-x[parent])*length
        from core.pose3d.temporal_guard import DEPENDENTS
        for j in DEPENDENTS[child]:x[j]+=x[child]-original
        f['pred_keypoints_3d']=x.tolist();f['pred_keypoints_2d']=(x[:,:2]*200+[200,150]).tolist()


@pytest.mark.parametrize('width',[1,2])
@pytest.mark.parametrize('parent,child,dependent',[(7,62,42),(8,41,21),(11,13,17),(12,14,20)])
def test_isolated_in_frame_spike_repaired_with_provenance_and_attached_offsets(width,parent,child,dependent):
    raw=sample();spike(raw,width=width,parent=parent,child=child);before=deepcopy(raw)
    _,old=complete_sam(raw,temporal_repair=False);_,new=complete_sam(raw)
    assert raw==before and new['temporal_guard']['repaired_joint_frames']==width
    for i in range(10,10+width):
        joint=new['frames'][i]['joints'][child]
        assert joint['source']=='temporal_interpolated' and 'before_temporal' in joint
        assert joint['xyz']==pytest.approx(new['frames'][9]['joints'][child]['xyz'])
        old_offset=np.subtract(old['frames'][i]['joints'][dependent]['xyz'],old['frames'][i]['joints'][child]['xyz'])
        new_offset=np.subtract(new['frames'][i]['joints'][dependent]['xyz'],joint['xyz'])
        assert new_offset==pytest.approx(old_offset)
    assert new['frames'][9]['joints']==old['frames'][9]['joints']


@pytest.mark.parametrize('condition',['long','cut','lost','body_turn','constant_length','projection_disagrees','parent_motion','edge','inconsistent_attachment'])
def test_unsafe_motion_is_not_automatically_replaced(condition):
    raw=sample();start=0 if condition=='edge' else 10;spike(raw,start=start,width=3 if condition=='long' else 1,length=1 if condition=='constant_length' else 1.4)
    if condition=='cut':
        for f in raw['frames'][10:]:f['tracking_segment']=1
    if condition=='lost':
        raw['frames'][9]['tracking']={'state':'lost'};raw['frames'][9]['outputs']=None
    if condition=='body_turn':
        for j in (5,6):raw['frames'][10]['outputs']['pred_keypoints_3d'][j][0]*=-1
    if condition=='projection_disagrees':raw['frames'][10]['outputs']['pred_keypoints_2d'][62]=raw['frames'][9]['outputs']['pred_keypoints_2d'][62]
    if condition=='parent_motion':raw['frames'][10]['outputs']['pred_keypoints_3d'][7][2]=.15
    if condition=='inconsistent_attachment':raw['frames'][10]['outputs']['pred_keypoints_3d'][42]=[.8,.8,.8]
    _,out=complete_sam(raw)
    assert out['temporal_guard']['repaired_joint_frames']==0


def test_cancellation_is_respected():
    with pytest.raises(KeyboardInterrupt):complete_sam(sample(),lambda:True)
