import json,numpy as np
from pathlib import Path
E=Path(__file__).resolve().parent/'m5-release'
source=json.loads((E/'LongSword-roundtrip.json').read_text(encoding='utf-8'))['expected_source_heads_m']
ue=json.loads((E/'unreal-report.json').read_text(encoding='utf-8'));samples=ue['pose_samples'];names=ue['bone_names']
a=np.asarray([source[str(samples[0]['frame'])][name] for name in names])*100
b=np.asarray([samples[0]['positions_cm'][name] for name in names])
conversion=np.linalg.lstsq(a,b,rcond=None)[0]
assert np.max(np.abs(conversion@conversion.T-np.eye(3)))<1e-3,conversion
assert np.max(np.abs(conversion[2]-[0,0,1]))<1e-3,conversion
errors=[]
for row in samples:
    a=np.asarray([source[str(row['frame'])][name] for name in names])*100
    b=np.asarray([row['positions_cm'][name] for name in names])
    errors.append(float(np.linalg.norm(a@conversion-b,axis=1).max()))
assert max(errors)<.1,errors
result={'passed':True,'bones':len(names),'source_to_ue_axes':conversion.tolist(),'maximum_position_error_cm':max(errors),
        'sample_frames':[s['frame'] for s in samples],'source_meters_to_engine_centimeters':100,'upright_z_preserved':True,
        'limits':['axis_basis_fitted_once_from_first_pose_then_checked_other_times','not_visual_quality_or_target_retarget_verification']}
(E/'pose-comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
