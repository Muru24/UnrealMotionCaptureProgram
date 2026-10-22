"""CPU-only standard skeleton conversion, preserving every inference artifact."""
from pathlib import Path
import json
from app.knee_job import load_context,digest
from app.fullbody_job import write
from core.motion.skeleton import convert,DEFINITION


def ensure_motion(folder,source,post=None,cancelled=lambda:False):
    if cancelled():raise KeyboardInterrupt
    folder=Path(folder).resolve();raw,source_hash,_=load_context(folder,source)
    post=post or {};selected=None;kind='raw_sam3d'
    for key,name,label in (
        ('reconnection_directory','reconnected-joints.json','checked_reconnection'),
        ('part_result_directory','part-joints.json','part_estimates'),
        ('candidate_selection_directory','selected-joints.json','selected_candidates')):
        if post.get(key):
            path=(Path(post[key])/name).resolve()
            if not path.is_relative_to(folder):raise ValueError('Motion input must belong to this result.')
            if path.is_file():selected=path;kind=label;break
    raw_hash=digest(folder/'sam3d.json')
    signature={'source_sha256':source_hash,'raw_sha256':raw_hash,
               'input_sha256':raw_hash if selected is None else digest(selected),
               'definition_sha256':digest(DEFINITION),'converter_revision':1,'source_kind':kind}
    out=folder/'motion';path=out/'motion.json';report_path=out/'report.json'
    if out.is_symlink() or (out.exists() and out.resolve().parent!=folder):raise ValueError('Motion output must stay inside the result.')
    if path.is_file() and report_path.is_file():
        try:
            report=json.loads(report_path.read_text(encoding='utf-8'))
            if report.get('status')=='completed' and all(report.get(k)==v for k,v in signature.items()) and report.get('motion_sha256')==digest(path):
                if cancelled():raise KeyboardInterrupt
                return path,'reused'
        except (OSError,ValueError):pass
    if cancelled():raise KeyboardInterrupt
    selected_data=None if selected is None else json.loads(selected.read_text(encoding='utf-8'))
    if selected_data is not None and (selected_data.get('source_sha256')!=source_hash or selected_data.get('raw_sha256')!=raw_hash):
        raise ValueError('Motion sidecar source/raw provenance differs.')
    rows=None if selected_data is None else selected_data['frames']
    data=convert(raw,rows,source_kind=kind,cancelled=cancelled)
    data.update(signature)
    if cancelled():raise KeyboardInterrupt
    if digest(source)!=source_hash or digest(folder/'sam3d.json')!=raw_hash or digest(DEFINITION)!=signature['definition_sha256'] or (selected is not None and digest(selected)!=signature['input_sha256']):
        raise ValueError('Motion conversion inputs changed.')
    out.mkdir(exist_ok=True)
    temporary=out/'motion.pending.json'
    write(temporary,data)
    if cancelled():
        temporary.unlink(missing_ok=True);raise KeyboardInterrupt
    temporary.replace(path)
    write(report_path,{'status':'completed',**signature,'frames':len(data['frames']),
        'frames_with_pose':sum(any(p is not None for p in row['positions']) for row in data['frames']),
        'motion_sha256':digest(path),'bone_rotations_generated':False})
    return path,'computed'


def add_motion_result(folder,source,post,cancelled=lambda:False):
    try:
        path,state=ensure_motion(folder,source,post,cancelled)
        return {'motion_file':str(path),'motion_status':state}
    except KeyboardInterrupt:raise
    except Exception as error:return {'motion_error':str(error)}
