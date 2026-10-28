import copy
import numpy as np
from core.motion.hand_orientation import palm_observations
from core.motion.skeleton import AXIS
from test_motion_skeleton import sample_raw


def palm_fixture():
 raw=sample_raw(4)
 for side,wrist,elbow,ids,sign in [('left',62,7,[49,53,61],1),('right',41,8,[28,32,40],-1)]:
  for name,j in zip(['index','middle','pinky'],ids):raw['joint_names'][j]=f'{side}-{name}-third-joint'
  for row in raw['frames']:
   q=np.array(row['outputs']['pred_keypoints_3d']);w=AXIS@q[wrist];middle=w+[sign*.1,0,0]
   for j,p in zip(ids,[middle+[0,-.03,0],middle,middle+[0,.03,0]]):q[j]=AXIS.T@p
   row['outputs']['pred_keypoints_3d']=q.tolist();row['outputs'].pop('pred_keypoints_2d',None)
 return raw


def test_palm_frame_is_orthogonal_and_input_immutable():
 raw=palm_fixture();before=copy.deepcopy(raw);out=palm_observations(raw);assert raw==before
 for row in out:
  for side in ['l','r']:
   p=row[side];assert p is not None
   assert abs(np.dot(p['forward'],p['lateral']))<1e-9
   np.testing.assert_allclose(np.linalg.norm(p['forward']),1)
   np.testing.assert_allclose(np.linalg.norm(p['lateral']),1)
 assert out[0]['l']['forward'][0]>0 and out[0]['r']['forward'][0]<0


def test_missing_lost_and_degenerate_palm_do_not_invent_evidence():
 raw=palm_fixture();raw['frames'][0]['outputs']=None;raw['frames'][1]['tracking']['state']='lost'
 q=raw['frames'][2]['outputs']['pred_keypoints_3d'];q[49]=q[61];q[28]=q[40]
 out=palm_observations(raw)
 assert out[:3]==[{'l':None,'r':None}]*3
 assert out[3]['l'] is not None


def test_tiny_or_outside_image_projection_is_not_used():
 raw=palm_fixture()
 for row in raw['frames']:row['outputs']['pred_keypoints_2d']=np.full((70,2),50.).tolist()
 assert all(r=={'l':None,'r':None} for r in palm_observations(raw))
