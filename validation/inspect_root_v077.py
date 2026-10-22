import json,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
status=json.loads((ROOT/'validation/dance-v074/status.json').read_text(encoding='utf-8'))
raw=json.loads((Path(status['output'])/'sam3d.json').read_text(encoding='utf-8'))
motion=json.loads(Path(status['motion']).read_text(encoding='utf-8'))
for i in (0,60,120,140,145,150,155,160,175,180,185,240,300,410):
    row=raw['frames'][i];p=np.asarray(row['outputs']['pred_keypoints_2d']);q=np.asarray(row['outputs']['pred_keypoints_3d']);cam=np.asarray(row['outputs']['pred_cam_t'])
    print(i,'cam',cam.round(3).tolist(),'origin',np.mean(q[[9,10]],axis=0).round(3).tolist(),'pixelhip',p[[9,10]].mean(axis=0).round(1).tolist(),'bbox',np.asarray(row['person_bbox']).round(1).tolist())
