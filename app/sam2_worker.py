"""SAM 2 runs in an isolated child using read-only shared CUDA packages."""
import os
os.environ['HF_HUB_OFFLINE']='1'
from pathlib import Path
import sys
import json
import tempfile
from collections import OrderedDict
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.validation/sam2/deps'),str(ROOT/'.validation/sam2/source')]

from core.video.limits import MAX_VIDEO_FRAMES
from core.pose2d.sam2_memory import trim_forward_memory

def main(output):
    import cv2
    import numpy as np
    import torch
    from PIL import Image
    from unittest.mock import patch
    from core.pose2d.mask_tracking import MaskTrack, waiting_for_target
    from core.pose2d.roi_envelope import RoiEnvelope
    from core.video.scene_cuts import SceneCutDetector, SceneTimeline
    from sam2.build_sam import build_sam2_video_predictor
    request=json.loads((output/'sam2-request.json').read_text(encoding='utf-8'))
    metadata=request['video'];width=metadata['width'];height=metadata['height'];fps=metadata['fps']
    if not torch.cuda.is_available():raise RuntimeError('SAM 2 시험에는 CUDA GPU가 필요합니다.')
    torch.set_num_threads(min(8,os.cpu_count() or 4))
    predictor=build_sam2_video_predictor('configs/sam2.1/sam2.1_hiera_s.yaml',
        str(ROOT/'models/sam2/sam2.1_hiera_small.pt'),device='cuda',apply_postprocessing=False,
        hydra_overrides_extra=['++model.fill_hole_area=0',
            '++model.sam_mask_decoder_extra_args.dynamic_multimask_via_stability=true',
            '++model.sam_mask_decoder_extra_args.dynamic_multimask_stability_delta=0.05',
            '++model.sam_mask_decoder_extra_args.dynamic_multimask_stability_thresh=0.98'])
    started=perf_counter();capture=cv2.VideoCapture(str(request['source']))
    if not capture.isOpened():raise ValueError('Cannot reopen SAM 2 input video.')
    writer=None;records=[]
    (output/'masks').mkdir(exist_ok=False)
    try:
        with tempfile.TemporaryDirectory(prefix='sam2-frames-',dir=output) as temporary:
            directory=Path(temporary);count=0;cut_detector=SceneCutDetector();scene_events=[]
            while True:
                ok,frame=capture.read()
                if not ok:break
                if count>=MAX_VIDEO_FRAMES or frame.shape[:2]!=(height,width):raise ValueError('SAM 2 input limits exceeded.')
                event=cut_detector.observe(frame,count)
                if event is not None:scene_events.append(event)
                encoded=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,95])[1]
                (directory/f'{count:06d}.jpg').write_bytes(encoded.tobytes());count+=1
                if count%15==0:(output/'sam2-progress.json').write_text(json.dumps({'phase':'decode','done':count}),encoding='utf-8')
            capture.release()
            if not count:raise ValueError('No decoded SAM 2 frames.')
            scene_events.append(cut_detector.finish())
            if len(scene_events)!=count:raise RuntimeError('Scene timeline alignment differs.')
            start=request.get('initial_frame_index',0)
            if type(start) is not int or not 0<=start<count:raise ValueError('Invalid target start frame.')
            class LazyFrames:
                # Official normalization, at most two resized frames cached.
                # Avoid allocating num_frames*3*1024*1024 floats up front.
                def __init__(self,size):self.size=size;self.cache=OrderedDict()
                def __len__(self):return count
                def __getitem__(self,index):
                    if not 0<=index<count:raise IndexError(index)
                    if index not in self.cache:
                        with Image.open(directory/f'{index:06d}.jpg') as image:
                            a=np.array(image.convert('RGB').resize((self.size,self.size)),dtype=np.float32)/255.
                        tensor=torch.from_numpy(a).permute(2,0,1)
                        tensor=(tensor-torch.tensor((.485,.456,.406))[:,None,None])/torch.tensor((.229,.224,.225))[:,None,None]
                        self.cache[index]=tensor
                        while len(self.cache)>2:self.cache.popitem(last=False)
                    return self.cache[index]
            def frames_loader(video_path,image_size,**kwargs):
                return LazyFrames(image_size),height,width
            # Adapter is child-local. Official model source stays unchanged.
            with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16),patch('sam2.sam2_video_predictor.load_video_frames',frames_loader):
                state=predictor.init_state(str(directory),offload_video_to_cpu=True,offload_state_to_cpu=True)
                predictor.add_new_points_or_box(state,frame_idx=start,obj_id=1,box=np.asarray(request['initial_box'],dtype=np.float32))
                person_motion_guard=not bool(request.get('boots'))
                policy=MaskTrack(width,height,fps,motion_guard=person_motion_guard,start_index=start)
                envelope=RoiEnvelope(fps)
                scene_timeline=SceneTimeline()
                writer=cv2.VideoWriter(str(output/'mask-tracking.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps,(width,height))
                if not writer.isOpened():raise RuntimeError('Cannot create mask preview.')
                def emit(row,mask,image):
                    index=row['frame_index']
                    row=envelope.update(scene_timeline.annotate(row,scene_events[index]))
                    (output/'masks'/f'{index:06d}.png').write_bytes(cv2.imencode('.png',mask)[1].tobytes())
                    row['mask']['file']=f'masks/{index:06d}.png';records.append(row)
                    color=(30,210,70) if row['roi'] is not None else (0,140,255)
                    foreground=mask>0;overlay=np.empty_like(image);overlay[:]=color
                    image[foreground]=cv2.addWeighted(image,.6,overlay,.4,0)[foreground]
                    if row['person_bbox']:
                        x1,y1,x2,y2=row['person_bbox'];cv2.rectangle(image,(x1,y1),(x2,y2),color,2)
                    elif row['motion'].get('predicted_bbox'):
                        x1,y1,x2,y2=map(int,row['motion']['predicted_bbox']);cv2.rectangle(image,(x1,y1),(x2,y2),(0,180,255),1)
                    cv2.putText(image,f'{index} SAM2 | scene {row["scene"]["index"]} | '+row['tracking']['reason'],(15,30),cv2.FONT_HERSHEY_SIMPLEX,.6,color,2)
                    writer.write(image)
                    (output/'sam2-progress.json').write_text(json.dumps({'phase':'mask','done':index+1,'total':count}),encoding='utf-8')
                for index in range(start):
                    image=cv2.imdecode(np.fromfile(directory/f'{index:06d}.jpg',np.uint8),cv2.IMREAD_COLOR)
                    emit(waiting_for_target(index,fps),np.zeros((height,width),np.uint8),image)
                for index,ids,logits in predictor.propagate_in_video(state,start_frame_idx=start):
                    if ids!=[1]:raise RuntimeError('SAM 2 target identity map changed.')
                    mask_logits=logits[0,0].float().cpu().numpy()
                    obj=state['output_dict_per_obj'][0]
                    current=obj['cond_frame_outputs'].get(index) or obj['non_cond_frame_outputs'].get(index)
                    object_logit=float(current['object_score_logits'].float().item())
                    image=cv2.imdecode(np.fromfile(directory/f'{index:06d}.jpg',np.uint8),cv2.IMREAD_COLOR)
                    row=policy.evaluate(mask_logits,object_logit,index,scene_cut=bool(scene_events[index]['cut']) if person_motion_guard and index!=start else False,frame=image if person_motion_guard else None)
                    mask=(mask_logits>0).astype(np.uint8)*255
                    emit(row,mask,image)
                    # Preserve the existing short-clip path; bound long forward passes.
                    if count>3600:
                        trim_forward_memory(predictor,state,index)
            if len(records)!=count:raise RuntimeError('Incomplete SAM 2 propagation.')
    finally:
        capture.release()
        if writer is not None:writer.release()
    plan={'version':1,'status':'completed','selection':'sam2_video_mask','target_id':1,
        'target_index':request['target_index'],'initial_frame_index':start,'detector':'YOLOX initial target frame search',
        'association_model':'SAM 2.1 Small video memory; no 2D keypoints',
        'elapsed_seconds':perf_counter()-started,'motion_prediction':person_motion_guard,
        'policy':{'appearance':'SAM2_visual_memory','per_frame_pose_association':False,
                  'identity_verified':False,'scene_cut_handling':'visual_confirmation_new_motion_segment' if person_motion_guard else 'hard_cut_segment_boundary',
                  'position_guard':{'enabled':person_motion_guard,'measurement':'visible_mask_centroid',
                      'prediction':'constant_velocity_kalman','max_prediction_seconds':.5,
                      'max_residual_in_previous_bbox_diagonals':.65,'reconnection_confirmations':2,
                      'long_loss':'requires_reselection','cut':'masked_HSV_reference_distance_and_two_observations',
                      'appearance_distance_limit':.55,'predicted_roi_sent_to_pose':False},
                  'scene_cut_limits':['heuristic_not_ground_truth','no_fade_or_dissolve_detection',
                                      'single_frame_insert_may_be_suppressed_as_flash',
                                      'SAM2_memory_retained_not_identity_reselection'],
                  'scene_cut_thresholds':{'mean_pixel_difference':.08,'changed_fraction':.20,
                                          'histogram_distance':.20,'changed_pixel_threshold':.12},
                  'roi_source':'mask_bbox_with_padding_and_conservative_envelope',
                  'roi_stabilization':{'tau_seconds':.12,'max_area_ratio':1.8,
                                       'expansion':'immediate','contraction':'exponential'},
                  'prediction_is_not_pose':True},
        'scene_cuts':[e for e in scene_events if e['cut']],
        'gpu_peak_allocated_bytes':torch.cuda.max_memory_allocated(),'frames':records}
    temporary=output/'sam2-plan.partial.json'
    temporary.write_text(json.dumps(plan,allow_nan=False),encoding='utf-8')
    temporary.replace(output/'sam2-plan.json')


if __name__=='__main__':
    main(Path(sys.argv[1]).resolve())
