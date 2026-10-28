"""Measure first/reused body+finger exports and optionally a complete model job."""
import argparse,json,time
from pathlib import Path
from app.animation_job import export_animation
from app.finger_job import export_automatic_fingers

def run(folder,report,model=None):
    folder=Path(folder).resolve();report=Path(report).resolve();report.parent.mkdir(parents=True,exist_ok=True)
    measurements=[]
    for label in ('first','repeat'):
        start=time.perf_counter();body=export_animation(folder/'motion/motion.json');body_time=time.perf_counter()-start
        start=time.perf_counter();fingers=export_automatic_fingers(body,folder/'sam3d.json');finger_time=time.perf_counter()-start
        measurements.append({'pass':label,'body_seconds':body_time,'finger_seconds':finger_time,'body':str(body),'fingers':str(fingers)})
        print('BENCHMARK',json.dumps(measurements[-1]),flush=True)
    data={'exports':measurements,'identical_verified_results':all(measurements[0][k]==measurements[1][k] for k in ('body','fingers'))}
    if model:
        from app.user_models import apply_custom
        start=time.perf_counter();preview=apply_custom(folder,model);data.update(model_preview=str(preview),model_pipeline_seconds=time.perf_counter()-start)
    report.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print('BENCHMARK_DONE',report,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder');parser.add_argument('report');parser.add_argument('--model');args=parser.parse_args();run(args.folder,args.report,args.model)
