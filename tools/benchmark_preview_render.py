"""Compare preview intermediate formats on identical saved poses."""
import argparse,json,time,math
from pathlib import Path
import cv2,numpy as np
from app.builtin_models import blender_job

def run(source,out,count=40):
    source,out=Path(source).resolve(),Path(out).resolve();out.mkdir(parents=True,exist_ok=False);results={}
    for name,mode in [('png','all-png'),('jpg','all')]:
        start=time.perf_counter();blender_job('render_model_preview.py',[source,out/name,mode,count],out/(name+'.log'))
        results[name]={'seconds':time.perf_counter()-start,'bytes':sum(p.stat().st_size for p in (out/name).glob('*.'+name))}
    psnr=[]
    for i in range(int(count)):
        a=cv2.imdecode(np.fromfile(out/'png'/f'{i+1:05d}.png',dtype=np.uint8),cv2.IMREAD_COLOR)
        b=cv2.imdecode(np.fromfile(out/'jpg'/f'{i+1:05d}.jpg',dtype=np.uint8),cv2.IMREAD_COLOR)
        error=float(np.mean((a.astype(float)-b.astype(float))**2));psnr.append(99. if not error else 10*math.log10(255**2/error))
    results.update(frames=int(count),mean_psnr_db=float(np.mean(psnr)),min_psnr_db=min(psnr));(out/'benchmark.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print(json.dumps(results),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('out');parser.add_argument('--count',type=int,default=40);args=parser.parse_args();run(args.source,args.out,args.count)
