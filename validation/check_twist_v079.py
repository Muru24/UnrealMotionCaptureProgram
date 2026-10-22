"""Isolated GUI regressions and independent Blender metric comparison."""
import sys,subprocess,json,compileall
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.animation_job import find_blender
folder=ROOT/'validation/twist-v079'
checks=['tests/test_animation_job.py::test_gui_animation_export_wires_current_result_and_busy_state',
        'tests/test_motion_skeleton.py::test_gui_paired_skeleton_seek_clear_and_orbit',
        'tests/test_motion_skeleton.py::test_gui_output_automatically_builds_and_loads_motion']
for i,test in enumerate(checks):
    with (folder/f'gui-{i}.log').open('w',encoding='utf-8') as stream:
        subprocess.run([sys.executable,'-X','utf8','-m','pytest',test,'-q',f'--basetemp=validation/pytest-v079-gui-{i}'],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=90,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
with (folder/'twist-comparison.log').open('w',encoding='utf-8') as stream:
    subprocess.run([find_blender(),'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'validation/compare_twist_v079_blender.py')],stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
assert compileall.compile_file(str(ROOT/'tools/animate_reference_rig.py'),quiet=1)
assert compileall.compile_file(str(ROOT/'app/gui.py'),quiet=1)
print('GUI 3 PASS / compileall PASS / Blender twist comparison PASS',flush=True)
