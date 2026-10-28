"""Read-only Unreal commandlet export of the installed Epic Manny mesh."""
from pathlib import Path
import json,hashlib
import unreal as u

root=Path(__file__).resolve().parents[1]
out=root/'assets/builtin_models/unreal_manny'
out.mkdir(parents=True,exist_ok=True)
target=out/'Manny.fbx'
if target.exists():raise FileExistsError(target)
mesh=u.load_asset('/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple')
if mesh is None:raise ValueError('Installed template Manny asset is missing')
task=u.AssetExportTask()
for key,value in {'object':mesh,'filename':str(target),'automated':True,'prompt':False,
                  'replace_identical':False,'options':u.FbxExportOption()}.items():task.set_editor_property(key,value)
if not u.Exporter.run_asset_export_task(task):raise RuntimeError('Manny FBX export failed')
if not target.is_file() or target.stat().st_size<10000:raise ValueError('Incomplete Manny export')
(out/'origin.json').write_text(json.dumps({'name':'Unreal Manny','source':'Installed Epic UE5.8 Third Person template',
    'asset':mesh.get_path_name(),'fbx_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
    'material_preview':'neutral studio material; Unreal shaders are not copied'},indent=2),encoding='utf-8')
print('MANNY_EXPORTED',str(target))
