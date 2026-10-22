from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess,sys,json,re
root=Path(__file__).resolve().parents[1]
dest=root/'validation/sam2/person-track-v0512/test-split';dest.mkdir(parents=True,exist_ok=True)
exclude=' and '.join('not '+n for n in ('test_gui_drop_load_preview_seek_and_invalid_replacement','test_gui_cancels_active_job_before_destroy','test_gui_output_runs_automatic_pipeline_and_has_no_manual_controls','test_gui_existing_sam_automatically_resumes_and_opens_latest','test_gui_library_previews_without_inference_and_releases_before_delete'))
def run(p):
    result=subprocess.run([sys.executable,'-X','utf8','-m','pytest','-q',str(p),'-k',exclude,'--basetemp='+str(dest/p.stem)],cwd=root,capture_output=True,encoding='utf-8',errors='replace')
    (dest/(p.stem+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
    last=[s for s in result.stdout.splitlines() if re.search(r'\d+ passed|\d+ failed',s)]
    print(p.name,result.returncode,last[-1:] ,flush=True)
    return {'file':p.name,'exit':result.returncode,'summary':last[-1:]}
with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,sorted((root/'tests').glob('test_*.py'))))
(dest/'summary.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
assert all(r['exit']==0 for r in results)
