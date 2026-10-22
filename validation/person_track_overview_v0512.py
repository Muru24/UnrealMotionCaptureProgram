from pathlib import Path
import json,cv2,numpy as np
root=Path(__file__).resolve().parents[1];folder=root/'validation/sam2/person-track-v0512/confirmed';strips=[]
for label,samples in [('Norma',(60,74)),('vivian',(265,266)),('kick',(104,105)),('LongSword',(120,300))]:
    cap=cv2.VideoCapture(str(folder/label/'mask-tracking.mp4'));tiles=[]
    for index in samples:
        cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,frame=cap.read();assert ok,(label,index)
        h,w=frame.shape[:2];scale=min(430/w,300/h);im=cv2.resize(frame,(round(w*scale),round(h*scale)))
        tile=np.full((330,450,3),20,np.uint8);x=(450-im.shape[1])//2;tile[30:30+im.shape[0],x:x+im.shape[1]]=im
        cv2.putText(tile,f'{label} frame {index}',(10,22),cv2.FONT_HERSHEY_SIMPLEX,.6,(235,235,235),1);tiles.append(tile)
    cap.release();strips.append(np.hstack(tiles))
out=folder/'overview.jpg';out.write_bytes(cv2.imencode('.jpg',np.vstack(strips))[1].tobytes());print(str(out))
