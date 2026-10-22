import json,copy
import cv2,numpy as np,pytest
from app.knee_job import digest
from app.root_motion_job import root_observations
from core.motion.correction import prepare_motion
from core.motion.root_motion import background_step
from test_motion_correction import fixture,crouch_fixture


def observations(data,dx=None,jump=None):
    n=len(data['frames']);names=[b['name'] for b in data['skeleton']['bones']]
    ground=data['skeleton']['bones'][1]['head'][2]+.07-data['skeleton']['bones'][names.index('foot_l')]['head'][2]
    p=np.tile([0,3,ground],(n,1)).astype(float)
    if dx is not None:p[:,0]=dx
    foot=np.tile([.07,.07,.03,.03],(n,1))
    if jump is not None:p[:,2]+=jump;foot+=np.asarray(jump)[:,None]
    return {'pelvis_camera_m':p,'feet_camera_z_m':foot,'feet_camera_x_m':np.full((n,4),np.nan),'epochs':[0]*n}


def test_image_jump_releases_false_stance_and_restores_landing_without_input_mutation():
    data,names=fixture(90);jump=np.zeros(90);jump[20:60]=.3
    obs=observations(data,jump=jump);before=copy.deepcopy(data)
    out=prepare_motion(data,root_observations=obs);q=np.array([r['positions'] for r in out['frames']])
    assert data==before
    assert out['correction']['frames'][40]['feet']==['estimated_airborne']*2
    assert q[40,0,2]==pytest.approx(.3,abs=.01)
    assert q[40,names.index('foot_l'),2]>.3
    assert out['correction']['frames'][80]['feet']==['inferred_contact']*2
    assert q[80,0,2]==0
    np.testing.assert_allclose(q[80,[names.index('foot_l'),names.index('foot_r')],2],.07,atol=1e-6)
    assert np.max(np.abs(np.diff(q[:,0,2])))<=.101


def test_one_raised_foot_and_crouch_are_not_whole_body_jump():
    data,names,pixels=crouch_fixture();obs=observations(data)
    obs['pelvis_camera_m'][20:65,2]-=.3
    obs['feet_camera_z_m'][30:45,0]+=.2
    out=prepare_motion(data,ground_evidence=pixels,root_observations=obs)
    assert not any(r['estimated_airborne'] for r in out['correction']['frames'])
    assert out['correction']['frames'][40]['image_ground_support']==[True,True]


def test_camera_epoch_and_scene_gaps_do_not_teleport_root():
    data,_=fixture(80);obs=observations(data,dx=np.linspace(0,.6,80))
    obs['pelvis_camera_m'][40:,0]+=20;obs['epochs'][40:]=[1]*40
    data['frames'][30]['positions']=[None]*22
    out=prepare_motion(data,root_observations=obs)
    assert out['frames'][30]['positions']==[None]*22
    q=np.array([[[np.nan]*3 if p is None else p for p in r['positions']] for r in out['frames']])
    assert np.nanmax(np.abs(np.diff(q[:,0,0])))<.15
    for row in data['frames'][60:]:row['scene_index']=1
    out=prepare_motion(data,root_observations=obs)
    assert out['frames'][60]['positions'][0][:2]==pytest.approx([0,0])


def test_lateral_image_slide_moves_root_without_pin_and_keeps_lengths():
    data,names=fixture(90);x=np.linspace(0,1.8,90);obs=observations(data,dx=x)
    obs['feet_camera_x_m']=np.tile(np.array([-.2,.2,-.2,.2]),(90,1))+x[:,None]
    out=prepare_motion(data,root_observations=obs);q=np.array([r['positions'] for r in out['frames']])
    assert q[-1,0,0]>1.4
    assert any(any(r['image_moving_support']) for r in out['correction']['frames'])
    h,k,a=[names.index(p+'_l') for p in ('thigh','calf','foot')]
    np.testing.assert_allclose(np.linalg.norm(q[:,h]-q[:,k],axis=1),.45,atol=1e-5)
    np.testing.assert_allclose(np.linalg.norm(q[:,a]-q[:,k],axis=1),.45,atol=1e-5)


def test_inconsistent_airborne_projection_cannot_push_feet_below_ground():
    data,names=fixture(90);jump=np.zeros(90);jump[20:60]=.3
    obs=observations(data,jump=jump);obs['feet_camera_z_m']+=1.5
    out=prepare_motion(data,root_observations=obs)
    assert out['correction']['frames'][40]['estimated_airborne']
    assert all(out['frames'][40]['positions'][names.index('foot_'+s)][2]>=.07 for s in ('l','r'))


def video_fixture(tmp_path,mode='pan',count=36):
    data,names=fixture(count);data['video'].update(width=640,height=480)
    source=tmp_path/'source.mp4';writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*'mp4v'),30,(640,480))
    rng=np.random.default_rng(9);base=rng.integers(0,256,(480,640,3),dtype=np.uint8)
    base=cv2.GaussianBlur(base,(5,5),0)
    points=np.array([[280,400],[360,400],[280,420],[360,420],[320,160]],float)
    rows=[];pixels=[]
    for i in range(count):
        scale=1+.002*i if mode=='zoom' else 1.
        tx=1.5*i if mode=='pan' else .12*i if mode=='slow_pan' else 0.
        affine=cv2.getRotationMatrix2D((320,240),0,scale);affine[:,2]+=[tx,-.8*i if mode=='vertical_pan' else 0]
        image=base.copy();cv2.rectangle(image,(250,90),(390,430),(150,70,40),-1)
        image=cv2.warpAffine(image,affine,(640,480))
        p=np.c_[points,np.ones(5)]@affine.T
        box=np.c_[np.array([[250,90],[390,430]]),np.ones(2)]@affine.T
        if mode=='actor':
            image=base.copy();shift=1.5*i;cv2.rectangle(image,(int(250+shift),90),(int(390+shift),430),(150,70,40),-1)
            p[:,0]+=shift;box[:,0]+=shift
        writer.write(image);pixels.append(p.tolist())
        rows.append({'frame_index':i,'person_bbox':box.reshape(-1).tolist(),'outputs':{'pred_cam_t':[0,0,3/scale]}})
    writer.release();raw=tmp_path/'sam3d.json';raw.write_text(json.dumps({'frames':rows}))
    (tmp_path/'sam-request.json').write_text(json.dumps({'source':str(source)}))
    data.update(source_sha256=digest(source),raw_sha256=digest(raw))
    motion=tmp_path/'motion/motion.json';motion.parent.mkdir();motion.write_text(json.dumps(data))
    return motion,data,pixels


@pytest.mark.parametrize('mode',['pan','vertical_pan','zoom','actor'])
def test_real_video_camera_pan_zoom_and_subject_translation_are_separated(tmp_path,mode):
    motion,data,pixels=video_fixture(tmp_path,mode)
    obs,info=root_observations(motion,data,pixels)
    assert info['valid_frames']>=32
    p=obs['pelvis_camera_m'];delta=p[-1]-p[0]
    if mode=='actor':assert delta[0]==pytest.approx(1.5*35*3/800,abs=.012)
    else:
        assert np.linalg.norm(delta)<.02
        out=prepare_motion(data,root_observations=obs)
        assert not any(r['estimated_airborne'] for r in out['correction']['frames'])


def test_unknown_background_and_wrong_source_do_not_invent_camera_motion(tmp_path):
    image=np.zeros((100,100),np.uint8)
    assert background_step(image,image,[30,20,70,90],[30,20,70,90]) is None
    motion,data,pixels=video_fixture(tmp_path)
    (tmp_path/'source.mp4').write_bytes(b'changed')
    obs,info=root_observations(motion,data,pixels)
    assert obs is None and info['reason']=='source_video_hash_differs'


def test_slow_camera_pan_is_not_accumulated_as_subject_walk(tmp_path):
    motion,data,pixels=video_fixture(tmp_path,'slow_pan',count=120)
    obs,info=root_observations(motion,data,pixels)
    assert info['valid_frames']>=110
    p=obs['pelvis_camera_m'];assert np.linalg.norm(p[-1]-p[0])<.02


def test_root_video_analysis_cancels_and_bad_timeline_is_rejected(tmp_path):
    motion,data,pixels=video_fixture(tmp_path)
    with pytest.raises(KeyboardInterrupt):root_observations(motion,data,pixels,lambda:True)
    obs=observations(data);obs['feet_camera_z_m']=np.zeros((2,4))
    with pytest.raises(ValueError):prepare_motion(data,root_observations=obs)
