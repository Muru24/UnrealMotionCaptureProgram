"""Optional local hand-only re-estimation comparison; never overwrites SAM joints."""
from pathlib import Path
from uuid import uuid4
import json,math,cv2,numpy as np
from app.knee_job import load_context,digest
from app.hand_preview_job import hand_chains,draw_hands
from core.motion.hand_crop import hand_roi,associate_hand,insert_hand

ROOT=Path(__file__).resolve().parents[1]


def reestimate_hands(folder,cancelled=lambda:False,progress=lambda *a:None,*,comparison=True):
    if cancelled():raise KeyboardInterrupt
    folder=Path(folder).resolve();request=json.loads((folder/'sam-request.json').read_text(encoding='utf-8'));source=Path(request['source'])
    raw,source_hash,_=load_context(folder,source);chains=hand_chains(raw['joint_names']);raw_hash=digest(folder/'sam3d.json')
    fps=float(raw['video']['fps'])
    if not math.isfinite(fps) or not 1<=fps<=240 or not 0<len(raw['frames'])<=18000:raise ValueError('Invalid hand crop timeline.')
    model=ROOT/'models/hand_landmarker/hand_landmarker.task';manifest=json.loads(model.with_name('manifest.json').read_text(encoding='utf-8'))
    if digest(model)!=manifest['sha256']:raise ValueError('손 전용 모델 파일이 변경되었습니다.')
    import mediapipe as mp
    options=mp.tasks.vision.HandLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_buffer=model.read_bytes(),delegate=mp.tasks.BaseOptions.Delegate.CPU),running_mode=mp.tasks.vision.RunningMode.IMAGE,num_hands=2,min_hand_detection_confidence=.5,min_hand_presence_confidence=.5)
    out=folder/('hand_crop_'+uuid4().hex[:8]);out.mkdir();path=out/'hand-crop-comparison.mp4'
    report={'status':'running','schema':'hand_crop_comparison_v1','source_sha256':source_hash,'raw_sha256':raw_hash,'model_sha256':manifest['sha256'],'crop_solver_sha256':digest(Path(__file__)),'automatic_animation_replacement':False,'world_coordinates':'independent_hand_model_frame_not_SAM_world','handedness_score_is_not_landmark_confidence':True,'frames':[]}
    cap=cv2.VideoCapture(str(source));writer=None;counts={'left':0,'right':0};fps=float(raw['video']['fps'])
    try:
        if not cap.isOpened():raise ValueError('Cannot decode source video.')
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as detector:
            for i,row in enumerate(raw['frames']):
                if cancelled():raise KeyboardInterrupt
                ok,image=cap.read()
                if not ok:raise ValueError('Hand comparison timeline differs.')
                points=(row.get('outputs') or {}).get('pred_keypoints_2d');q=None if points is None else np.asarray(points,float);entries={}
                tracked=row.get('tracking',{}).get('state')=='tracked' and row.get('roi') is not None
                for side in ['left','right']:
                    if cancelled():raise KeyboardInterrupt
                    roi=hand_roi(q,chains,side,image.shape[1],image.shape[0]) if tracked and q is not None else None
                    selected=None
                    if roi is not None:
                        x0,y0,x1,y1=roi;rgb=cv2.cvtColor(image[y0:y1,x0:x1],cv2.COLOR_BGR2RGB)
                        result=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=np.ascontiguousarray(rgb)));candidates=[]
                        for j,landmarks in enumerate(result.hand_landmarks):
                            xy=[[p.x*(x1-x0)+x0,p.y*(y1-y0)+y0] for p in landmarks];world=[[p.x,p.y,p.z] for p in result.hand_world_landmarks[j]];category=result.handedness[j][0]
                            candidates.append({'image_joints':xy,'world_joints':world,'handedness':category.category_name,'handedness_score':float(category.score)})
                        selected=associate_hand(candidates,q[chains[side][0][0]],roi)
                    entries[side]={'roi':roi,'status':'associated_model_candidate' if selected else 'no_reliable_candidate','candidate':selected}
                    if selected:
                        counts[side]+=1
                # Opposite ROIs must not claim the same physical wrist.
                if all(entries[s]['candidate'] for s in ['left','right']):
                    left,right=[entries[s]['candidate'] for s in ['left','right']]
                    if np.linalg.norm(np.subtract(left['image_joints'][0],right['image_joints'][0]))<8:
                        loser=max(['left','right'],key=lambda s:entries[s]['candidate']['wrist_distance_roi_fraction']);entries[loser]['candidate']=None;entries[loser]['status']='duplicate_wrist_rejected';counts[loser]-=1
                if not comparison:
                    report['frames'].append({'frame_index':i,'timestamp':i/fps,'tracking_segment':row.get('tracking_segment',0),'hands':entries});progress(i+1,len(raw['frames']));continue
                old,_=draw_hands(image,q,chains)
                # Missing candidates are blank instead of silently presenting the SAM baseline as re-estimation.
                candidate_points=np.full((70,2),np.nan)
                for side in ['left','right']:
                    if entries[side]['candidate']:candidate_points=insert_hand(candidate_points,chains,side,entries[side]['candidate'])
                new,_=draw_hands(image,candidate_points,chains)
                for rendered,title in [(old,'SAM baseline'),(new,'Hand-only crop candidates - comparison only')]:
                    cv2.rectangle(rendered,(0,0),(rendered.shape[1],32),(12,16,20),-1);cv2.putText(rendered,f'{title} | {i/fps:.2f}s',(8,22),cv2.FONT_HERSHEY_SIMPLEX,.5,(235,235,235),1,cv2.LINE_AA)
                rendered=np.concatenate([old,new],axis=1)
                if writer is None:
                    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),fps,(rendered.shape[1],rendered.shape[0]))
                    if not writer.isOpened():raise RuntimeError('Hand comparison encoder unavailable.')
                writer.write(rendered);report['frames'].append({'frame_index':i,'timestamp':i/fps,'tracking_segment':row.get('tracking_segment',0),'hands':entries});progress(i+1,len(raw['frames']))
        if cancelled():raise KeyboardInterrupt
        if digest(source)!=source_hash or digest(folder/'sam3d.json')!=raw_hash or digest(model)!=manifest['sha256']:raise ValueError('Hand comparison inputs changed.')
        report.update(status='completed',candidate_frames=counts)
    except KeyboardInterrupt:report['status']='cancelled';raise
    except Exception:report['status']='failed';raise
    finally:
        cap.release()
        if writer is not None:writer.release()
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    return path if comparison else out/'report.json'
