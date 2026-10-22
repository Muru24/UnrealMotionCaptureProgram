"""Discover source-bound, precomputed leg experiments for explicit review."""
from pathlib import Path
from app.completion_job import read,local
from app.knee_job import digest
from app.gui_jobs import ROOT


def find_leg_trial(source, directory=None):
    directory=Path(directory) if directory is not None else ROOT/'outputs'
    source_hash=digest(local(source));trials=sorted(directory.glob('leg_trial_*'),key=lambda p:p.stat().st_mtime,reverse=True)
    for folder in trials:
        try:
            report=read(folder/'report.json');video=local(folder/'comparison.mp4')
            if report.get('schema')!='precomputed_leg_trial_v1' or report.get('status')!='completed_for_review' or report.get('source_sha256')!=source_hash:continue
            start=report.get('start_frame');end=report.get('end_frame_exclusive')
            if type(start) is not int or type(end) is not int or not 0<=start<end:continue
            if not video.is_file() or digest(video)!=report.get('video_sha256'):continue
            return video,report
        except (OSError,ValueError,TypeError):continue
    raise ValueError('이 영상의 다리 추정 시험 결과가 없습니다. 현재는 Norma의 저장된 시험 결과만 연결되어 있습니다.')
