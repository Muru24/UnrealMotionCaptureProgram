import copy,math
import numpy as np
import pytest
from core.motion.skeleton import definition
from core.motion.correction import prepare_motion,slerp,rotate,swing,smooth_quaternions,leg_ik


def fixture(count=40):
    spec=definition();names=[b['name'] for b in spec['bones']];q=np.array([b['head'] for b in spec['bones']])
    return {'schema':'standard_motion_positions_v1','skeleton':spec,'video':{'fps':30},'source_kind':'test',
      'frames':[{'frame_index':i,'tracking_segment':0,'scene_index':0,'positions':q.tolist()} for i in range(count)]},names


def test_slerp_short_path_179_to_minus179_and_antipodal_sign():
    a=np.r_[math.cos(math.radians(179)/2),0,0,math.sin(math.radians(179)/2)]
    b=np.r_[math.cos(math.radians(-179)/2),0,0,math.sin(math.radians(-179)/2)]
    q=slerp(a,b,.5)
    np.testing.assert_allclose(rotate(q,np.array([1.,0,0])),[-1,0,0],atol=1e-8)
    np.testing.assert_allclose(slerp(a,-a,.3),a,atol=1e-8)


def test_filter_reduces_static_tremor_but_preserves_fast_swing():
    angles=np.array([.035*(-1)**i for i in range(60)])
    quats=np.array([[math.cos(a/2),0,0,math.sin(a/2)] for a in angles])
    filtered=smooth_quaternions(quats,30)
    assert np.std(filtered[4:-4,3])<np.std(quats[4:-4,3])*.5
    fast=np.linspace(0,math.pi,8);values=np.array([[math.cos(a/2),0,0,math.sin(a/2)] for a in fast])
    out=smooth_quaternions(values,30)
    assert abs(np.dot(out[-1],values[-1]))>.995


def test_stance_locks_ground_feet_preserves_lengths_and_input():
    data,names=fixture();original=copy.deepcopy(data)
    # Hip-relative support drift simulates in-place root removal.
    for i,row in enumerate(data['frames']):
        q=np.array(row['positions'])
        for side in ('l','r'):
            for part in ('calf','foot','ball'):q[names.index(part+'_'+side),0]-=.001*i
        row['positions']=q.tolist()
    before=copy.deepcopy(data);out=prepare_motion(data);assert data==before
    q=np.array([r['positions'] for r in out['frames']])
    contacts=out['correction']['frames'];assert all(r['feet']==['inferred_contact']*2 for r in contacts)
    for side in ('l','r'):
        hip,knee,ankle,toe=[names.index(p+'_'+side) for p in ('thigh','calf','foot','ball')]
        np.testing.assert_allclose(q[:,ankle,2],.07,atol=1e-7);np.testing.assert_allclose(q[:,toe,2],.03,atol=1e-7)
        assert np.ptp(q[:,ankle,0])<1e-6 and np.ptp(q[:,ankle,1])<1e-6
        np.testing.assert_allclose(np.linalg.norm(q[:,knee]-q[:,hip],axis=1),.45,atol=1e-5)
        np.testing.assert_allclose(np.linalg.norm(q[:,ankle]-q[:,knee],axis=1),.45,atol=1e-5)
    assert abs(q[-1,0,0])>.01


def test_missing_and_scene_boundary_never_filter_or_lock_across():
    data,names=fixture(30)
    for i,row in enumerate(data['frames']):
        if i==10:row['positions']=[None]*22
        if i>=20:
            row['scene_index']=1;row['tracking_segment']=1
            row['positions'][names.index('foot_l')][0]+=.1
    out=prepare_motion(data)
    assert out['frames'][10]['positions']==[None]*22
    assert out['correction']['frames'][10]['feet']==['missing','missing']
    assert out['correction']['frames'][20]['root_offset_m'][0]==pytest.approx(0)


def test_lifted_kicking_foot_not_pinned_to_floor():
    data,names=fixture(60)
    for i in range(20,40):
        q=np.array(data['frames'][i]['positions']);hip=q[names.index('thigh_l')].copy()
        angle=.9;rot=np.array([[1,0,0],[0,math.cos(angle),-math.sin(angle)],[0,math.sin(angle),math.cos(angle)]])
        for part in ('calf','foot','ball'):
            j=names.index(part+'_l');q[j]=hip+rot@(q[j]-hip)
        data['frames'][i]['positions']=q.tolist()
    out=prepare_motion(data)
    assert out['correction']['frames'][30]['feet'][0]=='swing'
    assert out['frames'][30]['positions'][names.index('foot_l')][2]>.2
    points=np.array([r['positions'] for r in out['frames']])
    steps=np.linalg.norm(np.diff(points[:,names.index('foot_l')],axis=0),axis=1)
    # This fixture teleports into/out of the kick. The geometry guard must not
    # delay that observed movement just to satisfy a world-speed clamp.
    assert steps[~np.isin(np.arange(len(steps)),[19,39])].max()<.3
    source_steps=np.linalg.norm(np.diff(np.array([r['positions'] for r in data['frames']])[:,names.index('foot_l')],axis=0),axis=1)
    assert steps.max()<=source_steps.max()+.15*.9
    assert any(r['constraint_rejections'][0] is not None for r in out['correction']['frames'])


def test_two_link_ik_rejects_unreachable_target_and_keeps_bend_side():
    hip=np.array([0.,0.,1]);ankle=np.array([0.,0.,.2]);pole=np.array([0.,-.2,.5])
    knee,side=leg_ik(hip,ankle,pole,.45,.45)
    assert knee[1]<0
    knee2,_=leg_ik(hip,ankle,np.array([0.,.2,.5]),.45,.45,side)
    assert knee2[1]<0
    assert leg_ik(hip,np.array([2.,0,0]),pole,.45,.45)==(None,None)


def test_correction_cancellation_and_bad_input():
    data,_=fixture()
    with pytest.raises(KeyboardInterrupt):prepare_motion(data,lambda:True)
    data['frames'][2]['positions'][3]=[float('inf')]*3
    with pytest.raises(ValueError):prepare_motion(data)


def test_single_frame_angular_outlier_is_reduced_without_inventing_missing_points():
    data,names=fixture(60)
    hand=names.index('hand_l');elbow=names.index('lowerarm_l')
    data['frames'][30]['positions'][hand][2]+=.2
    data['frames'][15]['positions'][hand]=None
    out=prepare_motion(data)
    assert out['frames'][15]['positions'][hand] is None
    assert abs(out['frames'][30]['positions'][hand][2]-out['frames'][30]['positions'][elbow][2])<.12


def test_isolated_large_rotation_spike_is_removed():
    values=np.tile([1.,0,0,0],(61,1));a=math.radians(65)
    values[30]=[math.cos(a/2),0,0,math.sin(a/2)]
    filtered=smooth_quaternions(values,30)
    np.testing.assert_allclose(filtered,np.tile([1.,0,0,0],(61,1)),atol=1e-6)


def test_slow_deliberate_rotation_is_not_frozen_and_rates_are_consistent():
    outputs=[]
    for fps in (30,60):
        angles=np.linspace(0,math.radians(20),3*fps+1)
        values=np.array([[math.cos(a/2),0,0,math.sin(a/2)] for a in angles])
        out=smooth_quaternions(values,fps);outputs.append(out[::fps//30])
        assert 2*math.acos(float(np.clip(abs(np.dot(out[-1],values[-1])),0,1)))<math.radians(3)
    assert np.max(np.linalg.norm(outputs[0]-outputs[1],axis=1))<.02


def test_ik_pole_filter_reduces_noise_without_changing_bone_lengths():
    hip=np.array([0.,0.,1.]);ankle=np.array([0.,0.,.2]);previous=None;raw=[];filtered=[]
    for i in range(60):
        pole=np.array([.05*(-1)**i,-.2,.5])
        a,_=leg_ik(hip,ankle,pole,.45,.45)
        b,previous=leg_ik(hip,ankle,pole,.45,.45,previous,1/30)
        raw.append(a);filtered.append(b)
        assert np.linalg.norm(b-hip)==pytest.approx(.45)
        assert np.linalg.norm(b-ankle)==pytest.approx(.45)
    assert np.std(np.array(filtered)[10:,0])<np.std(np.array(raw)[10:,0])*.6


def crouch_fixture():
    data,names=fixture(90);data['video'].update(width=1000,height=1000)
    evidence=np.tile([[400,900],[600,900],[400,930],[600,930],[500,650]],(90,1,1)).astype(float)
    for i in range(20,65):
        q=np.array(data['frames'][i]['positions'])
        for side in ('l','r'):
            hip,knee,ankle,toe=[names.index(p+'_'+side) for p in ('thigh','calf','foot','ball')]
            target=q[ankle].copy();target[2]=.4
            q[knee],_=leg_ik(q[hip],target,q[knee]+[0,-.3,0],.45,.45)
            delta=target-q[ankle];q[ankle]=target;q[toe]+=delta
        data['frames'][i]['positions']=q.tolist();evidence[i,4,1]=790
    return data,names,evidence


def test_image_crouch_support_lowers_pelvis_without_xy_foot_lock():
    data,names,evidence=crouch_fixture()
    for i in range(20,65):
        for side in ('l','r'):
            for part in ('calf','foot','ball'):data['frames'][i]['positions'][names.index(part+'_'+side)][0]+=(i-20)*.001
    before=copy.deepcopy(data);out=prepare_motion(data,ground_evidence=evidence)
    q=np.array([r['positions'] for r in out['frames']]);feet=[names.index('foot_'+s) for s in ('l','r')]
    assert data==before and out['correction']['frames'][40]['image_ground_support']==[True,True]
    assert out['correction']['frames'][40]['feet']==['inferred_ground_support']*2
    np.testing.assert_allclose(q[35:55,feet,2],.07,atol=1e-6)
    assert q[40,names.index('pelvis'),2]<.8
    assert np.ptp(q[35:55,feet[0],0])>.005
    for s in ('l','r'):
        h,k,a=[names.index(p+'_'+s) for p in ('thigh','calf','foot')]
        np.testing.assert_allclose(np.linalg.norm(q[:,h]-q[:,k],axis=1),.45,atol=1e-5)
        np.testing.assert_allclose(np.linalg.norm(q[:,a]-q[:,k],axis=1),.45,atol=1e-5)


def test_bent_airborne_feet_are_not_mistaken_for_crouch():
    data,names,evidence=crouch_fixture()
    evidence[20:65,:4,1]-=160;evidence[20:65,4,1]=590
    out=prepare_motion(data,ground_evidence=evidence)
    assert out['correction']['frames'][40]['image_ground_support']==[False,False]
    assert all(out['frames'][40]['positions'][names.index('foot_'+s)][2]>.3 for s in ('l','r'))


def test_crouch_offset_releases_before_airborne_tuck():
    data,names,evidence=crouch_fixture()
    evidence[45:65,:4,1]-=160;evidence[45:65,4,1]=590
    out=prepare_motion(data,ground_evidence=evidence)
    assert out['correction']['frames'][40]['image_ground_support']==[True,True]
    assert out['correction']['frames'][60]['image_ground_support']==[False,False]
    assert all(out['frames'][60]['positions'][names.index('foot_'+s)][2]>.3 for s in ('l','r'))


def test_missing_or_new_scene_has_no_image_support_from_another_span():
    data,names,evidence=crouch_fixture()
    data['frames'][40]['positions']=[None]*22
    for row in data['frames'][45:]:row['scene_index']=1
    evidence[55,0]=[float('nan')]*2
    out=prepare_motion(data,ground_evidence=evidence)
    assert out['frames'][40]['positions']==[None]*22
    assert out['correction']['frames'][40]['image_ground_support']==[False,False]
    assert out['correction']['frames'][50]['image_ground_support']==[False,False]
    assert out['correction']['frames'][55]['image_ground_support']==[False,False]


def test_cropped_feet_do_not_supply_ground_evidence():
    data,_,evidence=crouch_fixture();evidence[20:65,:4,1]=1050
    out=prepare_motion(data,ground_evidence=evidence)
    assert not any(any(r['image_ground_support']) for r in out['correction']['frames'])

def test_leg_guard_is_translation_invariant_and_rejects_shape_changes():
    from core.motion.correction import leg_constraint_violation
    p=np.array([[0,0,1],[0,-.2,.6],[0,0,.2],[0,-.18,.16]],float)
    assert leg_constraint_violation(p,p+[4,2,-1]) is None
    candidate=p.copy();candidate[2:,0]+=.2
    assert leg_constraint_violation(p,candidate)=='joint_displacement'
    # A small absolute change in a deeply bent short limb can reverse its plane.
    a=np.array([[0,0,0],[0,-.03,-.05],[0,0,-.1],[0,-.01,-.11]],float)
    b=a.copy();b[1,1]=.03
    assert leg_constraint_violation(a,b) is not None


def test_guard_rejects_false_contact_preserves_lengths_and_clears_lock():
    data,names=fixture(60)
    for i in range(20,40):
        q=np.array(data['frames'][i]['positions']);hip=q[names.index('thigh_l')].copy()
        angle=.9;rot=np.array([[1,0,0],[0,math.cos(angle),-math.sin(angle)],[0,math.sin(angle),math.cos(angle)]])
        for part in ('calf','foot','ball'):
            j=names.index(part+'_l');q[j]=hip+rot@(q[j]-hip)
        data['frames'][i]['positions']=q.tolist()
    before=copy.deepcopy(data);out=prepare_motion(data);assert data==before
    # Liftoff must not carry the new kick displacement as an old lock offset.
    assert out['correction']['frames'][20]['feet'][0]=='swing'
    assert out['correction']['frames'][30]['feet'][0]=='swing'
    q=np.array([r['positions'] for r in out['frames']])
    for side in ('l','r'):
        ids=[names.index(p+'_'+side) for p in ('thigh','calf','foot')]
        for a,b in zip(ids,ids[1:]):
            np.testing.assert_allclose(np.linalg.norm(q[:,b]-q[:,a],axis=1),.45,atol=1e-5)

def test_leg_guard_checks_bend_and_plane_even_with_small_displacement():
    from core.motion.correction import leg_constraint_violation
    straight=np.array([[0,0,0],[0,0,-.45],[0,0,-.9],[0,-.18,-.94]],float)
    angle=math.radians(11);bent=straight.copy()
    bent[1]=[0,-.45*math.sin(angle),-.45*math.cos(angle)]
    bent[2]=[0,0,-.9*math.cos(angle)];bent[3]=bent[2]+[0,-.18,-.04]
    assert leg_constraint_violation(straight,bent)=='knee_bend'
    angle=math.radians(9);a=straight.copy()
    a[1]=[0,-.45*math.sin(angle),-.45*math.cos(angle)];a[2]=[0,0,-.9*math.cos(angle)];a[3]=a[2]+[0,-.18,-.04]
    b=a.copy();b[1,:2]=[.45*math.sin(angle)*math.sin(math.pi/3),-.45*math.sin(angle)*math.cos(math.pi/3)]
    assert leg_constraint_violation(a,b)=='knee_plane'

def test_contact_gate_rejects_horizontal_foot_swing_without_height_change():
    from core.motion.correction import contact_motion_gate
    p=np.tile([[0,0,.1],[0,-.18,.06]],(12,1,1)).astype(float)
    assert contact_motion_gate(p,30,.9).all()
    p[5:,:,0]+=.1
    gate=contact_motion_gate(p,30,.9)
    assert not gate[4] and not gate[5]
    assert gate[:4].all() and gate[6:].all()


def test_contact_gate_camera_translation_cancels_and_missing_image_is_optional():
    from core.motion.correction import contact_motion_gate
    p=np.tile([[0,0,.1],[0,-.18,.06]],(12,1,1)).astype(float)
    image=np.tile([[400,900],[400,900],[400,930],[400,930],[500,650]],(12,1,1)).astype(float)
    image+=np.arange(12)[:,None,None]*3
    assert contact_motion_gate(p,30,.9,image).all()
    image[5:,:4,0]+=50
    gate=contact_motion_gate(p,30,.9,image)
    assert not gate[4] and not gate[5]
    image[:]=np.nan
    assert contact_motion_gate(p,30,.9,image).all()

def test_release_error_fades_by_time_at_30_and_60_fps():
    from core.motion.correction import release_offset
    seed=np.array([.08,-.04,.02]);before=seed.copy()
    np.testing.assert_allclose(release_offset(seed,0),seed)
    np.testing.assert_allclose(release_offset(seed,.06),seed*.5)
    for fps in [30,60]:
        values=[np.linalg.norm(release_offset(seed,i/fps)) for i in range(1,round(.3*fps))]
        assert np.all(np.diff(values)<=1e-12)
        np.testing.assert_allclose(release_offset(seed,math.ceil(.12*fps)/fps),0)
    np.testing.assert_array_equal(seed,before)
