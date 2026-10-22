"""Isolated SAM2 prompted subregion experiment. No automatic semantic detection."""
import os
os.environ['HF_HUB_OFFLINE']='1'
from pathlib import Path
import sys,json,tempfile
from collections import OrderedDict
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.validation/sam2/deps'),str(ROOT/'.validation/sam2/source')]


def main(output):
    import cv2,numpy as np,torch
    from PIL import Image
    from unittest.mock import patch
    from sam2.build_sam import build_sam2_video_predictor
    from core.pose2d.internal_mask import validate_prompts
    request=json.loads((output/'request.json').read_text(encoding='utf-8'))
    start=request['start'];stop=request['end_exclusive'];seed=request['seed_frame']-start
    w=request['video']['width'];h=request['video']['height'];validate_prompts(request['objects'],w,h)
    if not 0<=start<=request['seed_frame']<stop or stop-start>180:raise ValueError('Invalid internal mask interval.')
    if not torch.cuda.is_available():raise RuntimeError('Internal mask experiment requires CUDA.')
    torch.set_num_threads(min(8,os.cpu_count() or 4))
    predictor=build_sam2_video_predictor('configs/sam2.1/sam2.1_hiera_s.yaml',str(ROOT/'models/sam2/sam2.1_hiera_small.pt'),device='cuda',apply_postprocessing=False,
        hydra_overrides_extra=['++model.fill_hole_area=0'])
    with tempfile.TemporaryDirectory(prefix='internal-frames-',dir=output) as temp:
        directory=Path(temp);cap=cv2.VideoCapture(request['source'])
        try:
            if not cap.isOpened():raise ValueError('Cannot reopen source.')
            # Sequential decode keeps seed coordinates tied to the source timeline.
            for i in range(stop):
                ok,image=cap.read()
                if not ok or image.shape[:2]!=(h,w):raise ValueError('Source timeline differs.')
                if i>=start:(directory/f'{i-start:06d}.jpg').write_bytes(cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,95])[1].tobytes())
        finally:cap.release()
        class LazyFrames:
            def __init__(self,size):self.size=size;self.cache=OrderedDict()
            def __len__(self):return stop-start
            def __getitem__(self,i):
                if not 0<=i<stop-start:raise IndexError(i)
                if i not in self.cache:
                    with Image.open(directory/f'{i:06d}.jpg') as image:a=np.array(image.convert('RGB').resize((self.size,self.size)),dtype=np.float32)/255.
                    t=torch.from_numpy(a).permute(2,0,1)
                    self.cache[i]=(t-torch.tensor((.485,.456,.406))[:,None,None])/torch.tensor((.229,.224,.225))[:,None,None]
                    while len(self.cache)>2:self.cache.popitem(last=False)
                return self.cache[i]
        def loader(video_path,image_size,**kwargs):return LazyFrames(image_size),h,w
        records={}
        with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16),patch('sam2.sam2_video_predictor.load_video_frames',loader):
            state=predictor.init_state(str(directory),offload_video_to_cpu=True,offload_state_to_cpu=True)
            for obj_id,obj in enumerate(request['objects'],1):
                predictor.add_new_points_or_box(state,frame_idx=seed,obj_id=obj_id,points=np.asarray(obj['points'],np.float32),labels=np.asarray(obj['labels'],np.int32))
                (output/obj['name']).mkdir()
            for reverse in (False,True):
                for index,ids,logits in predictor.propagate_in_video(state,start_frame_idx=seed,reverse=reverse):
                    if reverse and index==seed:continue
                    if ids!=list(range(1,len(request['objects'])+1)):raise ValueError('Internal region identity map changed.')
                    row={'frame_index':index+start,'objects':{}}
                    for k,obj_id in enumerate(ids):
                        obj=request['objects'][obj_id-1];mask=(logits[k,0].float().cpu().numpy()>0).astype(np.uint8)*255
                        p=Path(obj['name'])/f'{index+start:06d}.png';(output/p).write_bytes(cv2.imencode('.png',mask)[1].tobytes())
                        d=state['output_dict_per_obj'][k];current=d['cond_frame_outputs'].get(index) or d['non_cond_frame_outputs'].get(index)
                        row['objects'][obj['name']]={'file':p.as_posix(),'object_logit':float(current['object_score_logits'].float().item())}
                    records[index+start]=row
                    (output/'progress.json').write_text(json.dumps({'done':len(records),'total':stop-start}),encoding='utf-8')
        if sorted(records)!=list(range(start,stop)):raise ValueError('Incomplete internal mask propagation.')
        (output/'regions.json').write_text(json.dumps({'frames':[records[i] for i in sorted(records)],'gpu_peak_allocated_bytes':torch.cuda.max_memory_allocated()},allow_nan=False),encoding='utf-8')


if __name__=='__main__':main(Path(sys.argv[1]).resolve())
