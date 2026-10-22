import sys,json,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.engine_export_job import export_engine_fbx
from app.animation_job import find_blender
E=ROOT/'validation/m5-release';E.mkdir(exist_ok=True)
exports=[]
for label,source in [('LongSword',ROOT/'validation/all-except-norma-v079/01-LongSword/animation.blend'),('dance',ROOT/'validation/all-except-norma-v079/05-dance/animation.blend'),('gaps',ROOT/'validation/twist-v079/gaps-example/animation.blend')]:
    out=export_engine_fbx(source)
    with (E/f'{label}-roundtrip.log').open('w',encoding='utf-8') as log:
        subprocess.run([find_blender(),'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'validation/verify_engine_fbx_blender.py'),'--',str(source),str(out),str(E/f'{label}-roundtrip.json')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    exports.append({'label':label,'source':str(source),'export':str(out)})
    print(label,str(out),flush=True)
(E/'exports.json').write_text(json.dumps(exports,ensure_ascii=False,indent=2),encoding='utf-8')
project=E/'MotionPreview';project.mkdir(exist_ok=True)
shutil.copyfile(ROOT/'validation/m5-preview/MotionPreview/MotionPreview.uproject',project/'MotionPreview.uproject')
shutil.copytree(ROOT/'validation/m5-preview/MotionPreview/Config',project/'Config',dirs_exist_ok=True)
out=Path(exports[0]['export'])
(E/'unreal-request.json').write_text(json.dumps({'fbx':str(out/'Motion_Unreal.fbx'),'report':str(E/'unreal-report.json'),'project':str(project),'expected':json.loads((out/'export.json').read_text(encoding='utf-8'))},ensure_ascii=False),encoding='utf-8')
