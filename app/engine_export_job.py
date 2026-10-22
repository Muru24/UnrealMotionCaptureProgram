"""Cancellable engine FBX export from immutable saved animation, without GPU inference."""
import json,subprocess,time,uuid
from pathlib import Path
from app.animation_job import ROOT,find_blender
from app.knee_job import digest

def export_engine_fbx(blend,cancelled=lambda:False,*,executable=None):
    blend=Path(blend).resolve()
    if cancelled():raise KeyboardInterrupt
    if blend.name!='animation.blend':raise ValueError('Blender animation output required')
    data=json.loads((blend.parent/'animation.json').read_text(encoding='utf-8'))
    if data.get('schema')!='standard_bone_animation_v1':raise ValueError('Unsupported animation')
    script=ROOT/'tools/export_engine_fbx.py'
    inputs={p:digest(p) for p in (blend,blend.parent/'animation.json',script)}
    out=blend.parent/('engine-'+uuid.uuid4().hex[:12]);start=time.monotonic()
    with (blend.parent/(out.name+'.log')).open('w',encoding='utf-8') as log:
        process=subprocess.Popen([executable or find_blender(),'--background','--factory-startup','--python-exit-code','1','--python',str(script),'--',str(blend),str(out)],stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            while process.poll() is None:
                if cancelled():raise KeyboardInterrupt
                if time.monotonic()-start>1800:raise TimeoutError('FBX export timed out')
                time.sleep(.1)
            if process.returncode:raise RuntimeError('FBX export failed; see '+str(log.name))
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
    if cancelled():raise KeyboardInterrupt
    if any(digest(p)!=h for p,h in inputs.items()):raise ValueError('Export input changed')
    report=json.loads((out/'export.json').read_text(encoding='utf-8'))
    if report.get('status')!='exported':raise ValueError('FBX exporter did not complete')
    files=[out/'Motion_Unreal.fbx',out/'Motion_Unity.fbx']
    if not all(p.is_file() and p.stat().st_size>1000 for p in files):raise ValueError('Incomplete FBX files')
    report.update(status='completed',source_blend_sha256=inputs[blend],source_animation_sha256=inputs[blend.parent/'animation.json'],
                  exporter_sha256=inputs[script],file_sha256={p.name:digest(p) for p in files})
    (out/'export.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return out
