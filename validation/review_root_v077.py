"""Source and world-aligned skeleton sheets for jump and crouch review."""
import json
from pathlib import Path
import numpy as np,cv2
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
status=json.loads((ROOT/'validation/dance-v074/status.json').read_text(encoding='utf-8'))
old=json.loads((ROOT/'validation/ground-v076/dance-example/corrected-motion.json').read_text(encoding='utf-8'))
new=json.loads((ROOT/'validation/root-v077-release/dance-example/corrected-motion.json').read_text(encoding='utf-8'))
names=[b['name'] for b in new['skeleton']['bones']];bones=new['skeleton']['bones']
canvas=Image.new('RGB',(1100,990),'#101722');draw=ImageDraw.Draw(canvas);capture=cv2.VideoCapture(status['source'])
for row,frame_index in enumerate((150,175,185)):
    top=row*330;capture.set(cv2.CAP_PROP_POS_FRAMES,frame_index);ok,frame=capture.read();assert ok
    picture=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));picture.thumbnail((240,300));canvas.paste(picture,(10,top+25))
    draw.text((10,top+5),f'Frame {frame_index} / {frame_index/30:.2f}s',fill='white')
    for col,(label,data) in enumerate((('v0.7.6 contact',old),('v0.7.7 image + contact',new))):
        left=250+col*420;q=np.asarray(data['frames'][frame_index]['positions'])
        def point(p):return (left+205+p[0]*130,top+300-p[2]*135)
        draw.line((left,top+300,left+405,top+300),fill='#72907a',width=2)
        for j,bone in enumerate(bones):
            if bone['parent'] is None:continue
            parent=names.index(bone['parent']);color='#55b6ff' if bone['name'].endswith('_l') else '#ffa355' if bone['name'].endswith('_r') else '#78d48b'
            draw.line((*point(q[j]),*point(q[parent])),fill=color,width=3)
        draw.text((left+5,top+5),label+' / world XZ',fill='white')
        draw.text((left+5,top+22),'Root XYZ: '+', '.join(f'{v:.2f}' for v in q[0]),fill='#c6d5e5')
        draw.text((left+5,top+39),'Feet: '+', '.join(f'{q[names.index("foot_"+s),2]:.2f}' for s in ('l','r')),fill='#c6d5e5')
capture.release();canvas.save(ROOT/'validation/root-v077-release/review.jpg')
