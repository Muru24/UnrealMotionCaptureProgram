from pathlib import Path
import json,cv2,numpy as np
root=Path(__file__).resolve().parents[1];dest=root/'validation/sam2/fullbody-v0513'
verification=json.loads((dest/'verification.json').read_text(encoding='utf-8'))
baseline=root/'outputs'/verification['existing_full_sequences'][0]['folder']/verification['existing_full_sequences'][0]['selection']
tiles=[]
for folder,index in ((baseline,60),(baseline,74),(dest/'fresh-window',62)):
    packet=json.loads((folder/'fullbody-candidates.json').read_text(encoding='utf-8'));row=packet['frames'][index]
    cap=cv2.VideoCapture(str(folder/'fullbody-reference.mp4'));cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,image=cap.read();cap.release();assert ok
    box=np.array(row['roi'] or row['person_bbox']).astype(int);x1,y1,x2,y2=box
    image=image[max(0,y1):min(image.shape[0],y2),max(0,x1):min(image.shape[1],x2)]
    h,w=image.shape[:2];scale=min(380/w,500/h);image=cv2.resize(image,(round(w*scale),round(h*scale)))
    tile=np.full((550,400,3),20,np.uint8);x=(400-image.shape[1])//2;tile[45:45+image.shape[0],x:x+image.shape[1]]=image
    title=('Fresh GPU' if folder==dest/'fresh-window' else 'Saved candidates')+f' frame {index}'
    cv2.putText(tile,title,(10,25),cv2.FONT_HERSHEY_SIMPLEX,.56,(230,230,230),1);tiles.append(tile)
out=dest/'overview.jpg';out.write_bytes(cv2.imencode('.jpg',np.hstack(tiles))[1].tobytes());print(str(out))
