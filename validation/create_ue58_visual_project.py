"""Fresh user-visible UE5.8 project; never reuse/overwrite an earlier test project."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'UnrealProjects';base.mkdir(exist_ok=True)
name='MotionCaptureCheck_UE58';folder=base/name;number=1
while folder.exists():
    number+=1;folder=base/f'{name}_{number}'
folder.mkdir();name=folder.name
(folder/f'{name}.uproject').write_text(json.dumps({'FileVersion':3,'EngineAssociation':'5.8','Category':'Motion Capture','Description':'Independent MotionHumanoid22 animation visual check','Plugins':[{'Name':'PythonScriptPlugin','Enabled':True},{'Name':'EditorScriptingUtilities','Enabled':True}]},indent=2),encoding='utf-8')
config=folder/'Config';config.mkdir()
(config/'DefaultEngine.ini').write_text('[/Script/EngineSettings.GameMapsSettings]\nEditorStartupMap=/Game/MotionPreview/Preview\n[/Script/Engine.RendererSettings]\nr.DynamicGlobalIlluminationMethod=0\nr.ReflectionMethod=0\nr.RayTracing=False\n',encoding='utf-8')
exports=json.loads((ROOT/'validation/m5-release/exports.json').read_text(encoding='utf-8'))
export=Path(next(x['export'] for x in exports if x['label']=='LongSword'))
e=ROOT/'validation/ue58-visual';e.mkdir(exist_ok=True)
request={'fbx':str(export/'Motion_Unreal.fbx'),'report':str(e/'import-report.json'),'project':str(folder),'expected':json.loads((export/'export.json').read_text(encoding='utf-8'))}
(e/'request.json').write_text(json.dumps(request,ensure_ascii=False,indent=2),encoding='utf-8')
(e/'project.json').write_text(json.dumps({'project':str(folder/f'{name}.uproject'),'folder':str(folder),'engine':'5.8.1','source_export':str(export)},ensure_ascii=False,indent=2),encoding='utf-8')
print(str(folder/f'{name}.uproject'),flush=True)
