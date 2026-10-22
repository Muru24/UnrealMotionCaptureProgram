"""Fresh tracking-only validation, with comparison against saved tracking plans."""
from pathlib import Path
import subprocess,sys,json,hashlib
from collections import Counter
from core.pose2d.metrics import tracking_metrics
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'validation/sam2/person-track-v0512'
if len(sys.argv)>1:DEST=DEST/sys.argv[1]
VIDEOS=ROOT.parent.parent/'애니메이션추출'

def main():
    kick=next(VIDEOS.glob('뒤차기 종류 4가지*.mp4'))
    sources=[VIDEOS/'Norma.mp4',VIDEOS/'vivian.mp4',kick,VIDEOS/'LongSword.mp4']
    results=[]
    for source,label in zip(sources,('Norma','vivian','kick','LongSword')):
        out=DEST/label
        if not (out/'sam2-plan.json').is_file():
            print('START '+label,flush=True)
            subprocess.run([sys.executable,'-X','utf8','-m','app.sam2_job',str(source),'--target-index','0','--output',str(out)],cwd=ROOT,check=True)
        plan=json.loads((out/'sam2-plan.json').read_text(encoding='utf-8'))
        request=json.loads((out/'sam2-request.json').read_text(encoding='utf-8'))
        baselines=[]
        for base in (ROOT/'outputs').iterdir():
            if base.name.startswith('.') or not base.is_dir():continue
            try:
                old_req=json.loads((base/'sam2-request.json').read_text(encoding='utf-8'))
                if Path(old_req['source']).name!=source.name or old_req['initial_box']!=request['initial_box']:continue
                old=json.loads((base/'sam2-plan.json').read_text(encoding='utf-8'))
                if len(old['frames'])!=len(plan['frames']):continue
                metrics=tracking_metrics(old,request['video']['fps'])
                baselines.append({'folder':base.name,'missing_frames':metrics['missing_frames'],'max_gap_seconds':metrics['max_gap_seconds'],'box_jump_events':len(metrics['box_jump_events'])})
            except (OSError,ValueError,KeyError):continue
        m=tracking_metrics(plan,request['video']['fps'])
        result={'video':label,'frames':len(plan['frames']),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'missing_frames':m['missing_frames'],'max_gap_seconds':m['max_gap_seconds'],'box_jump_events':len(m['box_jump_events']),
            'reason_counts':dict(Counter(r['tracking']['reason'] for r in plan['frames'])),
            'prediction_only_frames':sum(r['motion']['prediction_only'] for r in plan['frames']),
            'predictions_passed_as_pose_roi':sum(r['motion']['prediction_only'] and r['roi'] is not None for r in plan['frames']),
            'target_ids':sorted(set(r['tracking']['track_id'] for r in plan['frames'])),
            'baselines':baselines,'identity_ground_truth_available':False,'sam3d_inferred':False}
        assert result['predictions_passed_as_pose_roi']==0
        results.append(result)
        (DEST/'comparison.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
