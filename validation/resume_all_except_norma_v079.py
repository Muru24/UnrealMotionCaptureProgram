"""Wait for this batch's first pass, then retry its explicit target-selection failure once."""
import sys,json,time,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];e=ROOT/'validation/all-except-norma-v079'
owner=e/'resume-owner.json'
with owner.open('x',encoding='utf-8') as stream:json.dump({'pid':os.getpid(),'status':'waiting_for_first_pass'},stream)
started=time.monotonic()
while True:
    if (e/'CANCEL').exists():raise SystemExit('Batch canceled; retry not started')
    state=json.loads((e/'batch.json').read_text(encoding='utf-8'))
    if state['status']=='completed':print('Already complete',flush=True);break
    if state['status']=='completed_with_errors' and state.get('md_archive'):
        print('Retrying incomplete videos with inspected Sword target1',flush=True)
        subprocess.run([sys.executable,'-X','utf8',str(ROOT/'validation/export_all_except_norma_v079.py')],cwd=ROOT,check=True)
        result=json.loads((e/'batch.json').read_text(encoding='utf-8'))
        if result['status']!='completed':raise RuntimeError('Retry has remaining errors: inspect batch.json')
        print('ALL SIX COMPLETED',flush=True);break
    if time.monotonic()-started>8*3600:raise TimeoutError('Batch did not finish within eight hours')
    time.sleep(5)
owner.write_text(json.dumps({'pid':os.getpid(),'status':'completed'}),encoding='utf-8')
