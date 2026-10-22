"""Read the saved UE asset again; compare pose sampling without repeating the import."""
import unreal,json,re
from pathlib import Path
match=re.search(r'-MotionRequest=(?:"([^"]+)"|(.*?)(?=\s+-|$))',unreal.SystemLibrary.get_command_line())
request=json.loads(Path(match.group(1) or match.group(2)).read_text(encoding='utf-8'))
path=Path(request['report']);report=json.loads(path.read_text(encoding='utf-8'))
clip=unreal.load_asset(report['animation']);intervals=unreal.AnimationLibrary.get_num_frames(clip)
assert intervals+1==request['expected']['fbx_frames']
names=report['bone_names'];samples=[]
for frame in sorted(set((1,request['expected']['fbx_frames']//3,request['expected']['fbx_frames']//2,request['expected']['fbx_frames']))):
    pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(clip,(frame-1)/30,unreal.AnimPoseEvaluationOptions())
    positions={}
    for name in names:
        v=unreal.AnimPoseExtensions.get_bone_pose(pose,name,unreal.AnimPoseSpaces.WORLD).translation
        positions[name]=[v.x,v.y,v.z]
    samples.append({'frame':frame,'positions_cm':positions})
report.update(pose_samples=samples,sample_intervals=intervals,sample_keys=intervals+1,reopened_asset_verified=True)
path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
