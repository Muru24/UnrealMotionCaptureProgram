"""Source/corrected joint contact sheets; does not claim ground-truth contact labels."""
import json
from pathlib import Path
import numpy as np,cv2
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
status=json.loads((ROOT/'validation/dance-v074/status.json').read_text(encoding='utf-8'))
old=json.loads((Path(status['blend']).parent/'corrected-motion.json').read_text(encoding='utf-8'))
new=json.loads((ROOT/'validation/ground-v076/dance-example/corrected-motion.json').read_text(encoding='utf-8'))
names=[b['name'] for b in new['skeleton']['bones']];bones=new['skeleton']['bones']
canvas=Image.new('RGB',(1080,990),'#101722');draw=ImageDraw.Draw(canvas)
capture=cv2.VideoCapture(status['source'])
for row,frame_index in enumerate((175,180,185)):
    top=row*330
    capture.set(cv2.CAP_PROP_POS_FRAMES,frame_index);ok,frame=capture.read();assert ok
    picture=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));picture.thumbnail((240,300));canvas.paste(picture,(10,top+25))
    draw.text((10,top+5),f'Frame {frame_index} / {frame_index/30:.2f}s',fill='white')
    for col,(label,data) in enumerate((('v0.7.4',old),('v0.7.6',new))):
        left=260+col*400;q=np.asarray(data['frames'][frame_index]['positions']);cx=q[names.index('pelvis'),0]
        def point(p):return (left+190+(p[0]-cx)*135,top+295-p[2]*145)
        draw.line((left,top+295,left+390,top+295),fill='#72907a',width=2)
        for j,bone in enumerate(bones):
            if bone['parent'] is None:continue
            parent=names.index(bone['parent']);color='#55b6ff' if bone['name'].endswith('_l') else '#ffa355' if bone['name'].endswith('_r') else '#78d48b'
            draw.line((*point(q[j]),*point(q[parent])),fill=color,width=3)
        draw.text((left+8,top+8),label+' / frontal joint view',fill='white')
        z=q[[names.index('foot_l'),names.index('foot_r')],2]
        draw.text((left+8,top+25),f'Ankles: {z[0]:.3f}, {z[1]:.3f} m',fill='#c6d5e5')
        draw.text((left+8,top+42),f'Pelvis: {q[names.index("pelvis"),2]:.3f} m',fill='#c6d5e5')
capture.release();canvas.save(ROOT/'validation/ground-v076/review.jpg')
