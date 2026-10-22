from pathlib import Path
import json,cv2,numpy as np
root=Path(__file__).resolve().parents[1]
p=json.loads((root/'validation/sam2/person-track-v0512/vivian/sam2-plan.json').read_text(encoding='utf-8'))
print(json.dumps(p['scene_cuts']))
cap=cv2.VideoCapture(str(root.parent.parent/'애니메이션추출/vivian.mp4'));images=[]
for index in (264,265,266):
    cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,im=cap.read();assert ok
    im=cv2.resize(im,(320,560));cv2.putText(im,str(index),(12,30),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,255),2);images.append(im)
cap.release();dest=root/'validation/sam2/person-track-v0512/vivian-cut.jpg'
dest.write_bytes(cv2.imencode('.jpg',np.hstack(images))[1].tobytes());print(str(dest))
