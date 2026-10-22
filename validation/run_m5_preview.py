import sys,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.engine_export_job import export_engine_fbx
E=ROOT/'validation/m5-preview';E.mkdir(exist_ok=True)
status=E/'status.json'
if status.exists():raise FileExistsError('Preserve prior M5 validation')
source=ROOT/'validation/all-except-norma-v079/01-LongSword/animation.blend'
out=export_engine_fbx(source)
status.write_text(json.dumps({'source':str(source),'export':str(out)},ensure_ascii=False,indent=2),encoding='utf-8')
project=E/'MotionPreview';project.mkdir()
(project/'MotionPreview.uproject').write_text(json.dumps({'FileVersion':3,'EngineAssociation':'5.8','Category':'Motion Preview','Plugins':[{'Name':'PythonScriptPlugin','Enabled':True},{'Name':'EditorScriptingUtilities','Enabled':True}]}),encoding='utf-8')
config=project/'Config';config.mkdir()
(config/'DefaultEngine.ini').write_text('[/Script/EngineSettings.GameMapsSettings]\nEditorStartupMap=/Game/MotionPreview/Preview\n[/Script/Engine.RendererSettings]\nr.DynamicGlobalIlluminationMethod=0\nr.ReflectionMethod=0\nr.RayTracing=False\n',encoding='utf-8')
request={'fbx':str(out/'Motion_Unreal.fbx'),'report':str(E/'unreal-report.json'),'project':str(project),'expected':json.loads((out/'export.json').read_text(encoding='utf-8'))}
(E/'unreal-request.json').write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8')
engine=Path('C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe')
with (E/'unreal.log').open('w',encoding='utf-8') as stream:
    subprocess.run([str(engine),str(project/'MotionPreview.uproject'),'-unattended','-nop4','-nosplash','-NullRHI','-run=pythonscript',f'-script={ROOT / "tools/unreal_import_preview.py"}',f'-MotionRequest={E / "unreal-request.json"}'],stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=900,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
report=json.loads((E/'unreal-report.json').read_text(encoding='utf-8'));assert report['passed'];print(json.dumps(report,ensure_ascii=False),flush=True)
