"""Copy installed Epic template assets into the isolated preview project only."""
from pathlib import Path
import shutil, json
ROOT=Path(__file__).resolve().parents[1]
project=ROOT/'UnrealProjects/MotionCheckUE58'
source=Path('C:/Program Files/Epic Games/UE_5.8/Templates/TemplateResources/High/Characters/Content')
target=project/'Content/Characters'
assert not target.exists(), 'Never overwrite existing character assets'
shutil.copytree(source,target)
(ROOT/'validation/manny').mkdir(exist_ok=True)
print('Copied template Characters:',len(list(target.rglob('*.uasset'))))
