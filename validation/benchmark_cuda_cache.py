"""Bounded same-process cache benchmark; does not alter existing results."""
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['WANDB_MODE']='disabled'
os.environ['MOMENTUM_ENABLED']='0'
import sys,json,time,argparse
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.validation/sam3d/source_cuda')]
import cv2,numpy as np,torch
from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
torch.set_num_threads(8)
parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=('cache','batch','threads','tf32','body'),default='threads')
parser.add_argument('--spread',action='store_true')
args=parser.parse_args();mode=args.mode
out=ROOT/('validation/performance-'+mode+('-spread' if args.spread else ''))
out.mkdir(exist_ok=True)
status=json.loads((ROOT/'validation/dance-v074/status.json').read_text(encoding='utf-8'))
folder=Path(status['output'])
raw=json.loads((folder/'sam3d.json').read_text(encoding='utf-8'))
source=raw.get('source',status.get('source'))
if isinstance(source,dict):source=source['path']
cap=cv2.VideoCapture(str(source));frames=[]
indices=np.linspace(0,len(raw['frames'])-1,8,dtype=int).tolist() if args.spread else list(range(4))
for i in indices:
    cap.set(cv2.CAP_PROP_POS_FRAMES,i)
    ok,frame=cap.read()
    if not ok:raise RuntimeError('Missing benchmark frame')
    bbox=np.asarray(raw['frames'][i]['person_bbox'],float);size=bbox[2:]-bbox[:2]
    boxes=[np.r_[bbox[:2]-size*pad,bbox[2:]+size*pad] for pad in (np.array([.25,.15]),np.array([.05,.05]))]
    boxes=np.clip(boxes,[0,0,0,0],[frame.shape[1],frame.shape[0],frame.shape[1],frame.shape[0]])
    frames.append((cv2.cvtColor(frame,cv2.COLOR_BGR2RGB),np.asarray(boxes,dtype=np.float32)))
cap.release()
weights=ROOT/'models/sam3d_body_vith'
with patch('torch.cuda.is_available',return_value=False):
    model,cfg=load_sam_3d_body(str(weights/'model.ckpt'),device='cpu',mhr_path=str(weights/'assets/mhr_model.pt'))
estimator=SAM3DBodyEstimator(model.to('cuda').eval(),cfg)
def run(keep):
    torch.set_num_threads(1 if keep and mode=='threads' else 8)
    torch.backends.cuda.matmul.allow_tf32=keep and mode=='tf32'
    values=[];torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();start=time.perf_counter()
    for frame,box in frames:
        with torch.inference_mode():
            if keep and mode=='batch':p=estimator.process_one_image(frame,bboxes=box,inference_type='full')
            else:
                with patch('torch.cuda.empty_cache') if keep and mode=='cache' else __import__('contextlib').nullcontext():
                    p=[estimator.process_one_image(frame,bboxes=b[None],inference_type='body' if keep and mode=='body' else 'full')[0] for b in box]
        values.extend({k:np.asarray(row[k]).copy() for k in ('pred_keypoints_2d','pred_keypoints_3d')} for row in p)
    torch.cuda.synchronize()
    return values,{'seconds':time.perf_counter()-start,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved()}
run(False)
baseline,a=run(False)
optimized,b=run(True)
repeat,c=run(False)
delta=max(float(np.max(np.abs(x[k]-y[k]))) for x,y in zip(baseline,optimized) for k in x)
noise=max(float(np.max(np.abs(x[k]-y[k]))) for x,y in zip(baseline,repeat) for k in x)
report={'mode':mode,'frames':len(frames),'baseline':a,'optimized':b,'baseline_repeat':c,'max_output_delta':delta,'baseline_repeat_delta':noise,'speedup':((a['seconds']+c['seconds'])/2)/b['seconds']}
report['per_output_max_delta']={k:max(float(np.max(np.abs(x[k]-y[k]))) for x,y in zip(baseline,optimized)) for k in baseline[0]}
(out/'benchmark.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
