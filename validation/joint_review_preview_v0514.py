from pathlib import Path
import json,cv2,numpy as np
root=Path(__file__).resolve().parents[1];dest=root/'validation/sam2/joint-review-v0514'
verification=json.loads((dest/'verification.json').read_text(encoding='utf-8'));result=verification['results'][-1]
folder=root/'outputs'/result['folder']/result['selection'];packet=json.loads((folder/'fullbody-candidates.json').read_text(encoding='utf-8'))
cap=cv2.VideoCapture(str(folder/'joint-review.mp4'));tiles=[]
for index in (0,62,74):
    cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,image=cap.read();assert ok
    x1,y1,x2,y2=np.asarray(packet['frames'][index]['roi']).astype(int)
    image=image[max(0,y1):min(image.shape[0],y2),max(0,x1):min(image.shape[1],x2)]
    h,w=image.shape[:2];scale=min(380/w,500/h);image=cv2.resize(image,(round(w*scale),round(h*scale)))
    tile=np.full((550,400,3),20,np.uint8);x=(400-image.shape[1])//2;tile[45:45+image.shape[0],x:x+image.shape[1]]=image
    cv2.putText(tile,f'Frame {index} - REVIEW, NOT FIXED',(10,25),cv2.FONT_HERSHEY_SIMPLEX,.46,(230,230,230),1);tiles.append(tile)
cap.release();out=dest/'overview.jpg';out.write_bytes(cv2.imencode('.jpg',np.hstack(tiles))[1].tobytes());print(str(out))
