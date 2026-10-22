"""CPU reconnection sidecar with immutable upstream inputs and resumable cache."""
import copy
from pathlib import Path
from uuid import uuid4
from app.knee_job import load_context,digest
from app.completion_job import read
from app.fullbody_job import write
from app.part_reestimate_job import signatures,mask_support,render
from core.pose3d.reconnection import reconnect


def ensure_reconnection(folder,source,selection,review_path,parts,cancelled=lambda:False,progress=lambda *a:None):
    folder=Path(folder);selection=Path(selection);parts=Path(parts)
    _,source_hash,_=load_context(folder,source)
    expected=signatures(folder,source_hash,selection,review_path)
    data=read(parts/'part-joints.json');report=read(parts/'report.json')
    if report.get('status')!='completed_with_estimates' or any(data.get(k)!=v or report.get(k)!=v for k,v in expected.items()):
        raise ValueError('Reconnection part provenance differs.')
    packet=read(selection/'fullbody-candidates.json');review=read(review_path)
    support,manifest=mask_support(folder,packet,review,cancelled)
    inputs={**expected,'part_sha256':digest(parts/'part-joints.json'),'reconnection_revision':1}
    for out in sorted(folder.glob('reconnect_*'),key=lambda p:p.stat().st_mtime,reverse=True):
        try:
            cached=read(out/'report.json')
            if cached.get('status')=='completed_with_estimates' and all(cached.get(k)==v for k,v in inputs.items()) and cached.get('joints_sha256')==digest(out/'reconnected-joints.json') and cached.get('overlay_sha256')==digest(out/'reconnection-overlay.mp4'):
                return out,'reused'
        except (OSError,ValueError):pass
    if cancelled():raise KeyboardInterrupt
    rows,details=reconnect(packet,review,data,support,cancelled)
    out=folder/('reconnect_'+uuid4().hex[:8]);out.mkdir();status='failed'
    def unchanged():
        tracking=folder/'sam-tracking.json'
        tracking_hash=digest(tracking) if tracking.is_file() else None
        return signatures(folder,digest(source),selection,review_path)==expected and tracking_hash==review.get('tracking_sha256') and digest(parts/'part-joints.json')==inputs['part_sha256'] and all(h is None or digest(Path(p))==h for p,h in manifest)
    try:
        before=copy.deepcopy(packet)
        for frame,row in zip(before['frames'],data['frames']):
            frame['selected_candidate']='before_reconnection'
            frame['candidates']={'before_reconnection':row} if row['world_joints'] is not None else {}
        display=copy.deepcopy(rows)
        for row in display:row['changed_parts']=row['reconnected_parts']
        render(source,out/'reconnection-overlay.partial.mp4',before,display,cancelled,progress,
               titles=('PART ESTIMATES','CHECKED MODEL RECONNECTION'))
        if cancelled():raise KeyboardInterrupt
        if not unchanged():raise ValueError('Reconnection inputs changed.')
        write(out/'reconnected-joints.json',{'schema':'reconnected_mhr70_joints_v1',**inputs,'video':packet['video'],
            'coordinates':packet['coordinates'],'frames':rows,'details':details})
        (out/'reconnection-overlay.partial.mp4').replace(out/'reconnection-overlay.mp4')
        status='completed_with_estimates'
    except KeyboardInterrupt:status='cancelled';raise
    finally:
        (out/'reconnection-overlay.partial.mp4').unlink(missing_ok=True)
        final={'status':status,**inputs,**details}
        if status=='completed_with_estimates':final.update(joints_sha256=digest(out/'reconnected-joints.json'),overlay_sha256=digest(out/'reconnection-overlay.mp4'))
        write(out/'report.json',final)
    return out,'computed'
