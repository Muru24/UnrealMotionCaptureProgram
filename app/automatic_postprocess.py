"""One automatic SAM postprocess path with resumable, explicit partial results."""
from pathlib import Path
from time import perf_counter
from app.completion_job import read
from app.knee_job import load_context
from app.candidate_job import latest_selection,run_candidates
from app.leg_reestimate_job import latest_leg_result,write
from app.part_reestimate_job import latest_part_result,run_part_reestimation
from app.fullbody_job import ensure_fullbody
from app.joint_review_job import ensure_joint_review
from app.reconnection_job import ensure_reconnection

def process_sam_result(folder,source,cancelled=lambda:False,progress=lambda *a:None,phase=lambda *a:None,*,candidate_inference_type='full'):
    if candidate_inference_type not in ('full','body'):raise ValueError('Unsupported candidate inference type.')
    if cancelled():raise KeyboardInterrupt
    folder=Path(folder);raw,source_hash,_=load_context(folder,source)
    report={'status':'running','source_sha256':source_hash,'stages':{},'errors':{}}
    result={};stage='candidate_selection';started=perf_counter();stage_started=started
    timings={}
    try:
        if cancelled():raise KeyboardInterrupt
        selected=(latest_selection(folder,source_hash,'body') if candidate_inference_type=='body' else latest_selection(folder,source_hash))
        if selected is None:
            phase('자세 후보 자동 추론·선택')
            if candidate_inference_type=='body':selected,_=run_candidates(folder,source,cancelled,progress,inference_type='body')
            else:selected,_=run_candidates(folder,source,cancelled,progress)
            report['stages'][stage]='computed'
        else:report['stages'][stage]='reused'
        result['candidate_selection_directory']=str(selected)
        timings[stage]=perf_counter()-stage_started;stage_started=perf_counter()
        if cancelled():raise KeyboardInterrupt
        stage='fullbody_candidates';phase('전신 후보·몸통 기준축 준비')
        packet,state=ensure_fullbody(folder,source,selected,raw,source_hash,cancelled,progress)
        report['stages'][stage]=state;result['fullbody_candidates_file']=str(packet)
        timings[stage]=perf_counter()-stage_started;stage_started=perf_counter()
        if cancelled():raise KeyboardInterrupt
        stage='joint_review';phase('관절별 움직임·본 길이·영상 근거 검사')
        review,state=ensure_joint_review(folder,source,packet,source_hash,cancelled,progress)
        report['stages'][stage]=state;result['joint_review_file']=str(review)
        timings[stage]=perf_counter()-stage_started;stage_started=perf_counter()
        if cancelled():raise KeyboardInterrupt
        stage='part_reestimation';parts=latest_part_result(folder,source_hash,selected,review)
        if parts is None:
            phase('팔·다리 선택 재추정 준비');parts,_=run_part_reestimation(folder,source,selected,review,cancelled,progress,phase)
            report['stages'][stage]='computed'
        else:report['stages'][stage]='reused'
        result['part_result_directory']=str(parts)
        timings[stage]=perf_counter()-stage_started;stage_started=perf_counter()
        if cancelled():raise KeyboardInterrupt
        stage='reconnection';phase('팔·다리 재관측 검사·연결')
        connected,state=ensure_reconnection(folder,source,selected,review,parts,cancelled,progress)
        report['stages'][stage]=state;result['reconnection_directory']=str(connected)
        timings[stage]=perf_counter()-stage_started
        leg=latest_leg_result(folder,source_hash,selected)
        if leg is not None:result['leg_result_directory']=str(leg.parent)
        report['status']='completed_with_estimates'
    except KeyboardInterrupt:
        report['status']='cancelled';report['stages'][stage]='cancelled';raise
    except Exception as error:
        # Keep the completed extraction/selection usable if the optional leg
        # estimate cannot initialize (e.g. feet outside the first frame).
        report['status']='partial';report['stages'][stage]='failed';report['errors'][stage]=str(error)
    finally:
        if stage not in timings:timings[stage]=perf_counter()-stage_started
        report['stage_seconds']=timings
        report['candidate_inference_type']=candidate_inference_type
        report['seconds']=perf_counter()-started
        report.update(result);write(folder/'automatic-report.json',report)
    result['automatic_postprocess']=report
    return result
