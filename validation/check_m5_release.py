import sys,json,subprocess,compileall
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.animation_job import find_blender
E=ROOT/'validation/m5-release';exports=json.loads((E/'exports.json').read_text(encoding='utf-8'))
for item in exports:
    label=item['label']
    with (E/f'{label}-roundtrip.log').open('w',encoding='utf-8') as log:
        subprocess.run([find_blender(),'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'validation/verify_engine_fbx_blender.py'),'--',item['source'],item['export'],str(E/f'{label}-roundtrip.json')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
for i,test in enumerate(['tests/test_engine_export_job.py::test_gui_engine_button_worker','tests/test_animation_job.py::test_gui_animation_export_wires_current_result_and_busy_state','tests/test_motion_skeleton.py::test_gui_paired_skeleton_seek_clear_and_orbit','tests/test_motion_skeleton.py::test_gui_output_automatically_builds_and_loads_motion']):
    with (E/f'gui-{i}.log').open('w',encoding='utf-8') as log:
        subprocess.run([sys.executable,'-X','utf8','-m','pytest',test,'-q',f'--basetemp=validation/m5-release-gui-{i}'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
assert all(compileall.compile_file(str(ROOT/p),quiet=1) for p in ('app/gui.py','app/engine_export_job.py','tools/export_engine_fbx.py','tools/unreal_import_preview.py','tools/unreal_verify_preview.py'))
print('6 FBX reimports / 4 isolated GUI / compileall PASS',flush=True)
