"""Child-local SAM2 three-object experiment; production worker stays unchanged."""
from pathlib import Path
import sys
import json
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.validation/sam2/deps'),str(ROOT/'.validation/sam2/source')]


def main(output):
    import cv2
    import numpy as np
    import sam2.build_sam as build
    import app.sam2_worker as worker
    request=json.loads((output/'sam2-request.json').read_text(encoding='utf-8'))
    capture_factory=cv2.VideoCapture;original_builder=build.build_sam2_video_predictor
    class LimitedCapture:
        def __init__(self,*a,**kw):self.capture=capture_factory(*a,**kw);self.index=0
        def isOpened(self):return self.capture.isOpened()
        def release(self):self.capture.release()
        def read(self):
            if self.index>=request['video']['frame_count']:return False,None
            self.index+=1;return self.capture.read()
    def builder(*args,**kwargs):
        inner=original_builder(*args,**kwargs)
        class Proxy:
            def __getattr__(self,name):return getattr(inner,name)
            def add_new_points_or_box(self,state,**kw):
                result=inner.add_new_points_or_box(state,**kw)
                for boot in request['boots']:inner.add_new_points_or_box(state,frame_idx=0,obj_id=boot['id'],box=np.array(boot['box'],np.float32))
                return result
            def propagate_in_video(self,state):
                cap=capture_factory(request['source']);records=[];initial={}
                metadata=request['video'];writer=cv2.VideoWriter(str(output/'boots-preview.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),metadata['fps'],(metadata['width'],metadata['height']))
                assert writer.isOpened()
                try:
                    for index,ids,logits in inner.propagate_in_video(state):
                        assert ids==[1,2,3]
                        ok,image=cap.read();assert ok;boots=[]
                        for obj,boot in enumerate(request['boots'],1):
                            a=logits[obj,0].float().cpu().numpy();mask=(a>0).astype(np.uint8)
                            _,_,stats,_=cv2.connectedComponentsWithStats(mask,8);areas=stats[1:,cv2.CC_STAT_AREA];area=int(areas.sum())
                            dominance=float(areas.max()/area) if area else 0
                            stability=float(np.count_nonzero(a>1)/max(1,np.count_nonzero(a>-1)))
                            data=state['output_dict_per_obj'][obj]
                            current=data['cond_frame_outputs'].get(index) or data['non_cond_frame_outputs'].get(index)
                            score=float(current['object_score_logits'].float().item())
                            if index==0:initial[obj]=max(area,1)
                            ratio=area/initial[obj];ys,xs=np.nonzero(mask)
                            box=[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)] if area else None
                            accepted=bool(score>0 and area>=32 and dominance>.7 and stability>.55 and .2<=ratio<=4)
                            folder=output/f'boot-{boot["id"]}';folder.mkdir(exist_ok=True)
                            (folder/f'{index:06d}.png').write_bytes(cv2.imencode('.png',mask*255)[1].tobytes())
                            boots.append({'joint':boot['joint'],'id':boot['id'],'bbox':box,'area':area,'accepted':accepted,
                                          'stability':stability,'dominance':dominance,'object_score':score,'area_ratio':ratio})
                            color=(0,220,255) if obj==1 else (255,100,100)
                            overlay=np.full_like(image,color);image[mask>0]=cv2.addWeighted(image,.5,overlay,.5,0)[mask>0]
                            if box:cv2.rectangle(image,tuple(box[:2]),tuple(box[2:]),color,2)
                        records.append({'frame_index':index,'boots':boots})
                        cv2.putText(image,f'{index} | shoe masks - identity unverified',(15,35),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),2);writer.write(image)
                        yield index,[1],logits[:1]
                finally:
                    cap.release();writer.release()
                    (output/'boot-records.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
        return Proxy()
    with patch.object(build,'build_sam2_video_predictor',builder),patch.object(cv2,'VideoCapture',LimitedCapture):worker.main(output)


if __name__=='__main__':main(Path(sys.argv[1]).resolve())
