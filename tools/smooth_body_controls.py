"""Conservative offline torso smoothing, preserving legs and relative hand grip."""
import sys, json, math, hashlib
from pathlib import Path
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parent))
from grip_stability import smooth_quaternions


def run(source, output):
    source = Path(source).resolve()
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    signature = hashlib.sha256(source.read_bytes()).hexdigest()
    report = json.loads(source.with_name('report.json').read_text(encoding='utf-8'))
    bpy.ops.wm.open_mainfile(filepath=str(source))
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    scene = bpy.context.scene
    times = [r['frame'] for r in report['baked_sample_results']]
    # Both arms share these ancestors; do not independently smooth shoulders,
    # wrists, pelvis or legs, which would disturb grip or floor contact.
    names = ['上半身', '上半身2', '首', '頭']
    values = {n: [] for n in names}
    feet = []
    for f in times:
        scene.frame_set(int(f), subframe=f % 1)
        for n in names:
            values[n].append(arm.pose.bones[n].rotation_quaternion.copy())
        feet.append([arm.pose.bones[n].matrix.copy() for n in ['左足首D', '右足首D']])
    filtered = {n: smooth_quaternions(v, report['fps'] * 4, .055, 10000) for n, v in values.items()}
    metrics = {}
    for n in names:
        def acceleration(v):
            # Quaternion velocity difference, sampled at original video frames.
            v = v[::4]
            speeds = [(a.rotation_difference(b)).to_exponential_map() for a, b in zip(v, v[1:])]
            return math.sqrt(sum((b-a).length_squared for a,b in zip(speeds,speeds[1:])) / max(1,len(speeds)-1)) * 180 / math.pi
        metrics[n] = {'before_angular_acceleration_rms_deg_per_frame2': acceleration(values[n]),
                      'after_angular_acceleration_rms_deg_per_frame2': acceleration(filtered[n]),
                      'max_local_pose_change_deg': max(math.degrees(a.rotation_difference(b).angle) for a,b in zip(values[n],filtered[n]))}
    for i, f in enumerate(times):
        for n in names:
            pb = arm.pose.bones[n]
            pb.rotation_quaternion = filtered[n][i]
            pb.keyframe_insert('rotation_quaternion', frame=f, group=n)
    foot_error = 0.
    for i,f in enumerate(times):
        scene.frame_set(int(f), subframe=f % 1)
        for j,n in enumerate(['左足首D','右足首D']):
            foot_error = max(foot_error, max(abs(arm.pose.bones[n].matrix[a][b]-feet[i][j][a][b]) for a in range(4) for b in range(4)))
    assert foot_error < 1e-6, foot_error
    assert all(m['after_angular_acceleration_rms_deg_per_frame2'] <= m['before_angular_acceleration_rms_deg_per_frame2'] + 1e-5 for m in metrics.values())
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'animation.blend'))
    assert hashlib.sha256(source.read_bytes()).hexdigest() == signature
    report['input_sha256'][str(source)] = signature
    report['policy']['body_smoothing'] = {'bones': names, 'gaussian_seconds': .055, 'feet_matrix_max_change': foot_error}
    report['body_smoothing_metrics'] = metrics
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('BODY_SMOOTHED', json.dumps(metrics,ensure_ascii=False), flush=True)


if __name__ == '__main__':
    run(*sys.argv[sys.argv.index('--')+1:])
