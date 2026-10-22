"""Real detector and video timeline check; SAM2 is explicitly stubbed on CPU."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
E=ROOT/'validation/late-v0524'


def prepare():
    import cv2
    import numpy as np
    from app.gui_jobs import JobSettings,make_backend,read_source
    from app.target_start import find_target_start
    E.mkdir(exist_ok=True)
    source=E/'late-person.mp4'
    original=Path(r'C:\Users\user1\Desktop\애니메이션추출\LongSword.mp4')
    cap=cv2.VideoCapture(str(original));ok,image=cap.read();cap.release()
    assert ok
    image=cv2.resize(image,(360,640))
    writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*'mp4v'),30,(360,640))
    assert writer.isOpened()
    for i in range(20):writer.write(np.zeros_like(image) if i<10 else image)
    writer.release()
    metadata,_=read_source(source)
    index,frame,boxes=find_target_start(source,JobSettings(stage='sam3d',tracking_method='sam2'),lambda:False,make_backend)
    assert index==10 and len(boxes)==1
    out=E/'cpu-worker-stub';out.mkdir()
    (out/'sam2-request.json').write_text(json.dumps({'source':str(source),'target_index':0,
        'initial_box':boxes[0].tolist(),'initial_frame_index':index,'video':metadata.to_dict()}),encoding='utf-8')
    print('Real YOLOX detector first appearance:',index,flush=True)


def worker_check():
    from types import ModuleType
    from contextlib import nullcontext
    from unittest.mock import patch
    import numpy as np
    import cv2
    import torch
    import app.sam2_worker as worker
    out=E/'cpu-worker-stub';request=json.loads((out/'sam2-request.json').read_text(encoding='utf-8'))
    height=request['video']['height'];width=request['video']['width']
    class Predictor:
        def init_state(self,*a,**k):
            return {'output_dict_per_obj':{0:{'cond_frame_outputs':{},'non_cond_frame_outputs':{}}}}
        def add_new_points_or_box(self,state,frame_idx,**kwargs):
            assert frame_idx==10
        def propagate_in_video(self,state,start_frame_idx):
            assert start_frame_idx==10
            for i in range(start_frame_idx,20):
                a=np.full((height,width),-6.,np.float32)
                x1,y1,x2,y2=map(int,request['initial_box']);a[y1:y2,x1:x2]=6
                state['output_dict_per_obj'][0]['non_cond_frame_outputs'][i]={'object_score_logits':torch.tensor(4.)}
                yield i,[1],torch.from_numpy(a)[None,None]
    pkg=ModuleType('sam2');pkg.__path__=[]
    build=ModuleType('sam2.build_sam');build.build_sam2_video_predictor=lambda *a,**k:Predictor()
    video=ModuleType('sam2.sam2_video_predictor');video.load_video_frames=lambda *a,**k:None
    pkg.build_sam=build;pkg.sam2_video_predictor=video
    with patch.dict(sys.modules,{'sam2':pkg,'sam2.build_sam':build,'sam2.sam2_video_predictor':video}), \
         patch.object(torch.cuda,'is_available',return_value=True), \
         patch.object(torch.cuda,'max_memory_allocated',return_value=0), \
         patch.object(torch,'autocast',lambda *a,**k:nullcontext()):
        worker.main(out)
    plan=json.loads((out/'sam2-plan.json').read_text(encoding='utf-8'))
    assert len(plan['frames'])==20 and plan['initial_frame_index']==10
    assert [row['frame_index'] for row in plan['frames']]==list(range(20))
    for row in plan['frames'][:10]:
        assert row['roi'] is None and row['tracking']['state']=='uninitialized'
        mask=cv2.imdecode(np.fromfile(out/row['mask']['file'],np.uint8),cv2.IMREAD_GRAYSCALE)
        assert not mask.any()
    assert all(row['tracking']['state']=='tracked' for row in plan['frames'][10:])
    assert plan['frames'][10]['scene']['cut'] is True
    assert plan['frames'][10]['timestamp']==10/30
    cap=cv2.VideoCapture(str(out/'mask-tracking.mp4'));count=0
    while cap.read()[0]:count+=1
    cap.release();assert count==20
    report={'real_yolox_detector':True,'first_person_frame':10,'source_frames':20,'output_frames':20,
            'prefix_uninitialized_frames':10,'mask_inference_frames':10,'sam2_model_stubbed':True,
            'gpu_inference_executed':False,'sam3d_inference_executed':False,'mask_tracking_gpu_peak_bytes':0,
            'first_tracked_timestamp':10/30,'first_frame_scene_cut_handled':True}
    (E/'worker-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)


def sam3d_check():
    from types import ModuleType
    from unittest.mock import patch
    import torch
    import numpy as np
    import cv2
    import app.sam3d_worker as worker
    out=E/'cpu-worker-stub'
    request=json.loads((out/'sam2-request.json').read_text(encoding='utf-8'))
    (out/'sam-request.json').write_text(json.dumps(request),encoding='utf-8')
    (out/'sam-tracking.json').write_bytes((out/'sam2-plan.json').read_bytes())
    class Model:
        def to(self,*a):return self
        def eval(self):return self
    calls=[]
    class Estimator:
        def __init__(self,*a):pass
        def process_one_image(self,image,**kwargs):
            calls.append(kwargs)
            return [{'pred_keypoints_2d':np.full((70,2),50.),'pred_keypoints_3d':np.zeros((70,3)),
                     'pred_cam_t':np.zeros(3),'body_pose_params':np.zeros(1),'global_rot':np.zeros(3)}]
    pkg=ModuleType('sam_3d_body');pkg.__path__=[]
    pkg.load_sam_3d_body=lambda *a,**k:(Model(),None);pkg.SAM3DBodyEstimator=Estimator
    builders=ModuleType('sam_3d_body.build_models');builders.load_state_dict=lambda *a,**k:None
    metadata=ModuleType('sam_3d_body.metadata');metadata.__path__=[]
    names=ModuleType('sam_3d_body.metadata.mhr70');names.mhr_names=[f'stub_{i}' for i in range(70)]
    pkg.build_models=builders;pkg.metadata=metadata;metadata.mhr70=names
    with patch.dict(sys.modules,{'sam_3d_body':pkg,'sam_3d_body.build_models':builders,
        'sam_3d_body.metadata':metadata,'sam_3d_body.metadata.mhr70':names}), \
        patch.object(torch.cuda,'is_available',return_value=True):
        worker.main(out)
    raw=json.loads((out/'sam3d.json').read_text(encoding='utf-8'))
    assert len(calls)==10 and len(raw['frames'])==20
    assert all(row['outputs'] is None for row in raw['frames'][:10])
    assert all(row['outputs'] is not None for row in raw['frames'][10:])
    status=json.loads((out/'report.json').read_text(encoding='utf-8'))
    assert status['initial_frame_index']==status['frames_before_target_start']==10
    assert 'target_starts_after_frame_zero' in status['warnings']
    assert 'target_unavailable_in_some_frames' not in status['warnings']
    cap=cv2.VideoCapture(str(out/'overlay.mp4'));count=0
    while cap.read()[0]:count+=1
    cap.release();assert count==20
    report=json.loads((E/'worker-verification.json').read_text(encoding='utf-8'))
    report.update(sam3d_worker_executed_with_stub=True,sam3d_stub_calls=10,
                  sam3d_output_frames=20,prefix_raw_outputs_none=True)
    (E/'worker-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    {'prepare':prepare,'worker':worker_check,'sam3d':sam3d_check}[sys.argv[1]]()
