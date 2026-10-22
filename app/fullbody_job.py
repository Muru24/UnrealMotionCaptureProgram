"""Build a reusable full-body handoff and preview without rerunning any model."""
from pathlib import Path
import json,cv2,numpy as np
from app.knee_job import digest
from app.completion_job import read
from core.pose3d.fullbody_candidates import build_packet,LIMB_BONES

def write(path,data):
    path=Path(path);temporary=path.with_suffix('.partial.json')
    temporary.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False),encoding='utf-8');temporary.replace(path)

def render_reference(source,path,packet,cancelled,progress):
    video=packet['video'];cap=cv2.VideoCapture(str(source));writer=None
    try:
        writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),video['fps'],(video['width'],video['height']))
        if not cap.isOpened() or not writer.isOpened():raise ValueError('Cannot open full-body reference preview.')
        for row in packet['frames']:
            if cancelled():raise KeyboardInterrupt
            ok,image=cap.read()
            if not ok:raise ValueError('Full-body source timeline mismatch.')
            candidate=row['candidates'].get(row['selected_candidate']);label='TARGET UNAVAILABLE' if row['status']=='target_unavailable' else 'NO MATCHED SELECTED HYPOTHESIS'
            if candidate:
                p=np.asarray(candidate['image_joints']);xy=lambda j:tuple(np.clip(p[j],-10000,10000).round().astype(int))
                for a,b in LIMB_BONES+((5,6),(9,10),(5,9),(6,10)):
                    visible,u,v=cv2.clipLine((0,0,video['width'],video['height']),xy(a),xy(b))
                    if visible:cv2.line(image,u,v,(70,220,100),2,cv2.LINE_AA)
                refs=candidate['references_image'];a,b=[tuple(np.clip(v,-10000,10000).round().astype(int)) for v in refs['spine_axis_proxy']]
                cv2.line(image,a,b,(0,200,255),3,cv2.LINE_AA)
                for point in (a,b):cv2.circle(image,point,5,(255,160,40),-1)
                label='FULL BODY '+row['selected_candidate']+' | DERIVED TORSO AXIS'
            cv2.putText(image,label,(12,28),cv2.FONT_HERSHEY_SIMPLEX,.52,(0,200,255),1)
            writer.write(image);progress(row['frame_index']+1,len(packet['frames']))
    finally:
        cap.release()
        if writer is not None:writer.release()

def ensure_fullbody(folder,source,selection,raw,source_hash,cancelled=lambda:False,progress=lambda *a:None):
    if cancelled():raise KeyboardInterrupt
    if digest(source)!=source_hash:raise ValueError('Full-body source changed before export.')
    folder=Path(folder);selection=Path(selection);path=selection/'fullbody-candidates.json'
    hashes={'source_sha256':source_hash,'raw_sha256':digest(folder/'sam3d.json'),
            'selection_sha256':digest(selection/'selected-joints.json'),
            'candidates_sha256':digest(selection/'candidates.json') if (selection/'candidates.json').is_file() else None}
    selected=read(selection/'selected-joints.json')
    if selected.get('source_sha256')!=source_hash or selected.get('raw_sha256')!=hashes['raw_sha256']:
        raise ValueError('Full-body source/selection differs.')
    try:
        old=read(path)
        if isinstance(old,dict) and old.get('schema')=='fullbody_hypotheses_mhr70_v1' and old.get('exporter_revision')==1 and all(old.get(k)==v for k,v in hashes.items()) and (selection/'fullbody-reference.mp4').is_file():return path,'reused'
    except (OSError,ValueError):pass
    data=read(selection/'candidates.json') if hashes['candidates_sha256'] else {'frames':[]}
    variants={}
    for row in data['frames']:
        index=row['frame_index']
        if index in variants or not 0<=index<len(raw['frames']):raise ValueError('Full-body hypothesis timeline differs.')
        variants[index]=row['candidates']
    packet=build_packet(raw,variants,selected['frames'],cancelled);packet.update(hashes)
    packet['summary']={'frames':len(packet['frames']),
        'frames_with_four_candidates':sum(len(r['candidates'])==4 for r in packet['frames']),
        'target_unavailable_frames':sum(r['status']=='target_unavailable' for r in packet['frames']),
        'candidate_count':sum(len(r['candidates']) for r in packet['frames'])}
    temporary=selection/'fullbody-reference.partial.mp4'
    try:
        render_reference(source,temporary,packet,cancelled,progress)
        if cancelled():raise KeyboardInterrupt
        if digest(source)!=source_hash or digest(selection/'selected-joints.json')!=hashes['selection_sha256'] or digest(folder/'sam3d.json')!=hashes['raw_sha256'] or (hashes['candidates_sha256'] and digest(selection/'candidates.json')!=hashes['candidates_sha256']):
            raise ValueError('Full-body inputs changed during export.')
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(selection/'fullbody-reference.mp4');write(path,packet)
    return path,'computed'
