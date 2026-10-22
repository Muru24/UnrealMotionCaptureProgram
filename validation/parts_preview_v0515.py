from pathlib import Path
import json,cv2,numpy as np
root=Path(__file__).resolve().parents[1];dest=root/'validation/sam2/parts-v0515'
v=json.loads((dest/'verification.json').read_text(encoding='utf-8'));folder=root/'outputs'/v['folder'];out=folder/v['part_directory']
packet=json.loads((folder/v['selection']/'fullbody-candidates.json').read_text(encoding='utf-8'));data=json.loads((out/'part-joints.json').read_text(encoding='utf-8'))
for i in (58,59,60,61,62,65,66,70,74):print(i,data['frames'][i]['changed_parts'])
cap=cv2.VideoCapture(str(out/'part-overlay.mp4'));strips=[];w=packet['video']['width']
for index in (59,60,66):
    cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,frame=cap.read();assert ok
    x1,y1,x2,y2=np.asarray(packet['frames'][index]['roi']).astype(int);tiles=[]
    for side in (0,1):
        image=frame[max(0,y1):min(frame.shape[0],y2),side*w+max(0,x1):side*w+min(w,x2)]
        h,iw=image.shape[:2];scale=min(380/iw,410/h);image=cv2.resize(image,(round(iw*scale),round(h*scale)))
        tile=np.full((450,400,3),20,np.uint8);x=(400-image.shape[1])//2;tile[35:35+image.shape[0],x:x+image.shape[1]]=image
        cv2.putText(tile,f'Frame {index} '+('BASELINE' if side==0 else 'PART ESTIMATE'),(10,23),cv2.FONT_HERSHEY_SIMPLEX,.52,(230,230,230),1);tiles.append(tile)
    strips.append(np.hstack(tiles))
cap.release();path=dest/'overview.jpg';path.write_bytes(cv2.imencode('.jpg',np.vstack(strips))[1].tobytes());print(str(path))
