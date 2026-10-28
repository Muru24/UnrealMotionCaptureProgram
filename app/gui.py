"""Small local desktop prototype around the existing M1/M2 processors."""

from pathlib import Path
from dataclasses import replace
import json
import logging
import os
from queue import Empty, Queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2
from PIL import Image, ImageTk
from tkinterdnd2 import COPY, DND_FILES, REFUSE_DROP, TkinterDnD

from app.gui_jobs import (JobSettings, ROOT, inspect_candidates, new_output,
                          parse_drop, read_source, run_job)


class PrototypeApp:
    def __init__(self, root):
        self.root = root
        self.source = self.result_dir = None
        self.saved_preview_path=None
        self.candidate_dir=None
        self.leg_result_path=None;self.part_result_path=None;self.reconnection_path=None;self.leg_phase=None
        self.worker = None
        self.events = Queue()
        self.cancel_event = threading.Event()
        self.closing = False
        self.busy = False
        self.pending_model_apply=False
        self.capture = None
        self.tracking_capture=None
        self.model_capture=None;self.model_frame=None;self.preview_is_model=False
        self.tracking_frame=self.tracking_photo=None
        self.requested_preview_path=None
        self.original_preview_override=None
        self.preview_is_original=False;self.preview_is_tracking=False
        self.candidate_preview_frame=None;self.candidate_preview_index=None
        self.playing = False
        self.play_timer = None
        self.frame = self.photo = None
        self.video_count = 0
        self.video_fps = 30.
        self.position = 0
        self.target_frame = None
        self.run_output = None
        self.was_playing = False
        self.mode = tk.StringVar(value='SAM 3D + SAM 2 마스크 (시험)')
        self.single = tk.BooleanVar(value=True)
        self.fast_candidates = tk.BooleanVar(value=False)
        self.target = tk.StringVar(value='자동 선택')
        self.file_text = tk.StringVar(value='MP4 영상을 이곳에 드래그하세요')
        self.info_text = tk.StringVar(value='로컬 MP4 · 최대 5분')
        self.status_text = tk.StringVar(value='준비 · 영상을 넣어 주세요')
        self.detail_text = tk.StringVar(value='결과는 새 폴더에 자동 저장됩니다.')
        self.result_kind = tk.StringVar(value='3D 미리보기')
        self.use_refined_hands=tk.BooleanVar(value=True)
        self.time_text = tk.StringVar(value='00:00 / 00:00')
        self.seek_var = tk.DoubleVar(value=0)
        root.title('Video to Motion · MVP5 v0.8.0')
        root.geometry('1400x850')
        root.minsize(1200, 700)
        root.configure(bg='#101722')
        root.protocol('WM_DELETE_WINDOW', self.close)
        self._build()
        self.settings_changed()
        for widget in (root, self.drop_area, self.file_label, self.canvas,self.tracking_canvas):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind('<<Drop>>', self.drop)
        root.after(80, self.poll)

    def _build(self):
        from app.studio_layout import StudioLayout
        self.studio = StudioLayout(self)

    def preview_saved_result(self,folder,path):
        if self.busy:return
        self.stop_video()
        self.original_preview_override=None
        self.candidate_preview_frame=None;self.candidate_preview_index=None
        self.source=None;self.run_output=None;self.candidate_dir=None;self.leg_result_path=None;self.part_result_path=None;self.reconnection_path=None
        self.result_dir=Path(folder);self.saved_preview_path=Path(path)
        self.file_text.set(self.display_name(self.result_dir.name))
        self.info_text.set(str(self.saved_preview_path.relative_to(self.result_dir)))
        self.result_kind.set('저장 영상');self.kind_box.configure(values=('저장 영상',),state='readonly')
        self.folder_button.configure(state='normal');self.set_busy(False)
        self.status_text.set('저장된 결과 미리보기')
        self.open_video(self.saved_preview_path)

    def before_result_delete(self,folder):
        if self.busy:raise ValueError('작업 중에는 결과를 삭제할 수 없습니다.')
        folder=Path(folder).resolve()
        self.studio.final_panel.close_if_folder(folder)
        if any(p and Path(p).resolve().is_relative_to(folder) for p in (self.result_dir,self.saved_preview_path,self.run_output,self.source)):
            self.stop_video();self.skeleton_panel.clear();self.frame=None;self.render_frame()
            if self.source and Path(self.source).resolve().is_relative_to(folder):self.source=None
            self.result_dir=None;self.saved_preview_path=None;self.run_output=None
            self.candidate_dir=None;self.leg_result_path=None;self.part_result_path=None;self.reconnection_path=None
            self.kind_box.configure(values=('원본 영상',),state='disabled');self.result_kind.set('원본 영상')
            self.folder_button.configure(state='disabled');self.set_busy(False)
            self.status_text.set('결과 미리보기를 닫았습니다.')






    def open_sam_result(self):
        if self.busy:return
        path=filedialog.askopenfilename(parent=self.root,title='기존 SAM 결과의 sam3d.json 선택',filetypes=[('SAM 결과','sam3d.json')])
        if not path:return
        folder=Path(path).parent
        post_options={'candidate_inference_type':'body'} if self.fast_candidates.get() else {}
        def operation():
            from app.completion_job import read
            from app.knee_job import load_context
            from app.automatic_postprocess import process_sam_result
            source=Path(read(folder/'sam-request.json')['source']);raw,source_hash,_=load_context(folder,source)
            post=process_sam_result(folder,source,self.cancel_event.is_set,
                lambda done,total:self.events.put(('progress',(done,total))),lambda text:self.events.put(('legphase',text)),**post_options)
            from app.motion_job import add_motion_result
            post.update(add_motion_result(folder,source,post,self.cancel_event.is_set))
            return folder,source,raw['video'],post,raw.get('selection')
        self.launch_worker('samopened',operation)

    def settings(self):
        stage=('sam3d' if self.mode.get().startswith('SAM') else
               'pose3d' if self.mode.get().startswith('3D') else 'pose2d')
        selected=self.target.get()
        index=None if selected=='자동 선택' else int(selected.split()[-1])
        return JobSettings(stage,self.single.get(),index,None,
                           tracking_method='sam2' if 'SAM 2' in self.mode.get() else 'pose',
                           target_frame=getattr(self,'target_frame',None) if stage=='sam3d' and 'SAM 2' in self.mode.get() else None)

    def show_automatic_status(self,result):
        auto=result['automatic_postprocess']
        if auto['status']=='partial':
            self.status_text.set('기본 결과 생성 · 자동 후처리 일부 실패')
            self.detail_text.set('원시/완료된 후보 결과는 보존됩니다. '+ ' / '.join(auto['errors'].values()))
        else:
            self.status_text.set('자동 처리 완료 · 재관측 연결 결과를 확인하세요')
            self.detail_text.set('후보·관절 검사 → 팔·다리 선택 재추정 완료 · 주황색은 교체 추정 · 원시 결과 보존 · 정확도 미검증')
            if result.get('joint_review_file'):
                self.detail_text.set('재관측 연결 비교: 왼쪽 부위 추정 / 오른쪽 검사 후 연결. 모델 추정이며 정답 보장은 아닙니다. 관절 검사는 교체 전 진단입니다. · 원시 결과 보존')


    def settings_changed(self,event=None):
        self.target_frame=None;self.target.set('자동 선택');self.target_box.configure(values=('자동 선택',))
        self.detail_text.set('전체 추출 한 번으로 트래킹·본·손 보정·선택 모델·파일 저장까지 진행합니다.')

    def choose(self):
        if self.busy:return
        name=filedialog.askopenfilename(parent=self.root,title='MP4 영상 선택',filetypes=[('MP4 영상','*.mp4')])
        if name:self.load_source(Path(name))

    def drop(self,event):
        if self.busy or self.closing:return REFUSE_DROP
        try:
            path=parse_drop(self.root.tk,event.data)
        except (ValueError,tk.TclError) as exc:
            self.status_text.set(str(exc));return REFUSE_DROP
        self.load_source(path)
        return COPY

    def launch_worker(self,kind,operation):
        if self.busy:return
        self.busy=True
        self.cancel_event.clear()
        self.set_busy(True)
        def work():
            try:
                result=operation()
                if kind!='completed' and self.cancel_event.is_set():
                    raise KeyboardInterrupt
                self.events.put((kind,result))
            except KeyboardInterrupt:
                self.events.put(('cancelled',None))
            except Exception as exc:
                logging.exception('Prototype worker failed: %s',kind)
                self.events.put(('error',str(exc)))
            finally:
                self.events.put(('finished',None))
        self.worker=threading.Thread(target=work,name='motion-worker',daemon=False)
        self.worker.start()

    def set_busy(self,value):
        if self.studio.active_stage==4:
            self.studio.status.grid() if value else self.studio.status.grid_remove()
        self.studio.editor.set_busy(value)
        self.studio.final_panel.set_busy(value)
        self.studio.reconnect_button.configure(state='disabled' if value else 'normal')
        self.studio.refresh_builtin_status()
        self.result_panel.set_busy(value)
        for widget in (self.choose_button,self.candidate_button,self.start_button):
            widget.configure(state='disabled' if value else 'normal' if self.source or widget is self.choose_button else 'disabled')
        self.target_box.configure(state='disabled' if value else 'readonly')
        self.cancel_button.configure(state='normal' if value else 'disabled')

    def load_source(self,path):
        if self.busy:return
        self.original_preview_override=None
        self.candidate_preview_frame=None;self.candidate_preview_index=None
        self.skeleton_panel.clear()
        self.target_frame=None
        self.saved_preview_path=None
        self.stop_video()
        self.frame=None
        self.render_frame()
        self.time_text.set('00:00 / 00:00')
        # Clear the previous input before validating the replacement, so an invalid
        # drop can never leave the Output button pointing at a stale source.
        self.source=None
        self.candidate_dir=None
        self.leg_result_path=None
        self.part_result_path=None;self.reconnection_path=None
        self.result_dir=None
        self.run_output=None
        self.folder_button.configure(state='disabled')
        self.kind_box.configure(state='disabled',values=('원본 영상',))
        self.result_kind.set('원본 영상')
        self.target.set('자동 선택')
        self.target_box.configure(values=('자동 선택',))
        self.file_text.set(self.display_name(path.name))
        self.info_text.set('영상 확인 중…')
        self.status_text.set('영상 정보를 읽는 중')
        self.progress.configure(value=0)
        self.launch_worker('loaded',lambda:(path,*read_source(path)))

    def find_candidates(self):
        if not self.source or self.busy:return
        self.pause()
        source,settings=self.source,self.settings()
        if settings.tracking_method=='sam2':
            settings=replace(settings,target_frame=self.position if self.position>0 else None)
        self.status_text.set('대상 후보 확인 중 · 시작 위치가 비어 있으면 등장 프레임을 찾습니다…')
        self.launch_worker('candidates',lambda:inspect_candidates(source,settings,self.cancel_event.is_set,include_frame_index=True))

    def start(self):
        if not self.source or self.busy:return
        self.candidate_preview_frame=None;self.candidate_preview_index=None
        post_options={'candidate_inference_type':'body'} if self.fast_candidates.get() else {}
        self.stop_video()
        self.candidate_dir=None
        self.leg_result_path=None
        self.part_result_path=None;self.reconnection_path=None
        source,settings=self.source,self.settings()
        output=new_output(source,settings.stage)
        self.run_output=output
        self.result_dir=None
        self.folder_button.configure(state='disabled')
        self.kind_box.configure(state='disabled')
        self.status_text.set('출력 중 · 로컬 모델을 준비하는 중…')
        self.detail_text.set('완료되면 이 창에서 결과를 재생할 수 있습니다.')
        self.progress.configure(value=0)
        def operation():
            progress=lambda done,total:self.events.put(('progress',(done,total)))
            report=run_job(source,output,settings,self.cancel_event.is_set,progress)
            if settings.stage=='sam3d':
                # The worker has finalized the tracking video. Show it before
                # the slower candidate/re-estimation passes, without releasing
                # the busy guard or changing the active extraction input.
                self.events.put(('trackingready',output))
                from app.automatic_postprocess import process_sam_result
                report.update(process_sam_result(output,source,self.cancel_event.is_set,progress,
                              lambda text:self.events.put(('legphase',text)),**post_options))
                from app.motion_job import add_motion_result
                self.events.put(('legphase','표준 스켈레톤 변환'))
                report.update(add_motion_result(output,source,report,self.cancel_event.is_set))
                if self.cancel_event.is_set():raise KeyboardInterrupt
                from app.builtin_models import automatic_preview
                self.events.put(('legphase','선택 모델 자동 적용·미리보기 렌더링'))
                report.update(automatic_preview(output,self.cancel_event.is_set,progress))
            return output,settings,report
        self.launch_worker('completed',operation)

    def cancel(self):
        if self.busy:
            self.cancel_event.set()
            self.status_text.set('취소 중 · 현재 프레임 처리가 끝나면 중단합니다')
            self.cancel_button.configure(state='disabled')

    def poll(self):
        try:
            while True:
                kind,data=self.events.get_nowait()
                if self.closing:
                    if kind=='finished':self.busy=False
                    continue
                if kind=='loaded':
                    path,metadata,frame=data
                    self.source=path.resolve()
                    self.file_text.set(self.display_name(path.name))
                    self.info_text.set(f'{metadata.width} × {metadata.height}  ·  {metadata.fps:.2f} fps  ·  약 {metadata.duration_seconds_estimate:.1f}초')
                    self.status_text.set('준비 · 출력 버튼을 누르세요')
                    self.detail_text.set('전체 추출을 누르세요. 여러 인물 중 직접 고를 때만 대상 선택을 사용하세요.')
                    self.frame=frame;self.render_frame()
                    self.open_video(self.source)
                elif kind=='candidates':
                    frame,count,index=data
                    self.target_frame=index if count and self.settings().tracking_method=='sam2' else None
                    self.position=index;self.seek_var.set(index)
                    if self.capture is not None:self.capture.set(cv2.CAP_PROP_POS_FRAMES,index+1)
                    self.time_text.set(f'{self.clock(index/self.video_fps)} / {self.clock(self.video_count/self.video_fps)}')
                    if self.studio.active_stage==0 and self.capture is not None and self.preview_is_original:
                        self.candidate_preview_frame=frame;self.candidate_preview_index=index
                        self.capture.set(cv2.CAP_PROP_POS_FRAMES,index);self.read_video_frame()
                    else:self.frame=frame;self.render_frame()
                    self.target_box.configure(values=('자동 선택',)+tuple(f'대상 {i}' for i in range(count)))
                    self.target.set('대상 0' if count==1 else '자동 선택')
                    self.status_text.set(f'{index}프레임 · 후보 {count}명 · 번호를 선택한 뒤 출력하세요' if count else f'{index}프레임에 후보 없음 · 인물이 보이는 위치에서 다시 확인하세요')
                elif kind=='trackingready':
                    self.result_dir=Path(data)
                    self.result_kind.set('원본 뼈대')
                    self.kind_box.configure(values=('원본 뼈대','원본 영상'),state='disabled')
                    self.open_video(self.result_dir/'overlay.mp4')
                    self.status_text.set('트래킹 미리보기 준비됨 · 본 생성을 위한 자동 후처리 중')
                    self.detail_text.set('1번 화면에서 재생·탐색할 수 있습니다. 2번 본 생성 후 3번 선택 모델 미리보기까지 자동 생성합니다.')
                    if self.skeleton_panel.points is None:
                        self.skeleton_panel.clear('본 생성 대기 · 자동 후처리가 끝나면 표시됩니다')
                elif kind=='samopened':
                    folder,source,video,post,selection_kind=data;self.source=source;self.result_dir=folder
                    self.run_output=None
                    self.candidate_dir=Path(post['candidate_selection_directory']) if post.get('candidate_selection_directory') else None
                    self.leg_result_path=Path(post['leg_result_directory'])/'leg-overlay.mp4' if post.get('leg_result_directory') else None
                    self.part_result_path=Path(post['part_result_directory'])/'part-overlay.mp4' if post.get('part_result_directory') else None
                    self.mode.set('SAM 3D + SAM 2 마스크 (시험)' if selection_kind=='sam2_video_mask' else 'SAM 3D Body (GPU 시험)')
                    self.file_text.set(self.display_name(source.name));self.info_text.set(f'{video["width"]} × {video["height"]} · {video["fps"]:.2f} fps')
                    values=('원본 뼈대','원본 영상') if self.candidate_dir is None else ('후보 선택 비교','원본 뼈대','원본 영상')
                    if self.candidate_dir and (self.candidate_dir/'fullbody-reference.mp4').is_file():values=('전신 기준축',)+values
                    if self.candidate_dir and (self.candidate_dir/'joint-review.mp4').is_file():values=('관절 검사',)+values
                    if self.leg_result_path is not None:values=('다리 재추정 비교',)+values
                    if self.part_result_path is not None:values=('부위 재추정 비교',)+values
                    self.reconnection_path=Path(post['reconnection_directory'])/'reconnection-overlay.mp4' if post.get('reconnection_directory') else None
                    if self.reconnection_path is not None:values=('재관측 연결 비교',)+values
                    self.kind_box.configure(state='readonly',values=values)
                    self.result_kind.set(values[0]);self.change_view();self.folder_button.configure(state='normal')
                    self.show_automatic_status(post)
                    if post.get('motion_error'):self.skeleton_panel.clear('변환 실패: '+post['motion_error'])
                elif kind in ('handpreviewready','handrefineready'):
                    self.saved_preview_path=Path(data)
                    self.kind_box.configure(values=('저장 영상',),state='readonly');self.result_kind.set('저장 영상')
                    self.open_video(self.saved_preview_path)
                    self.status_text.set('손 재추정 비교 완료 · 오른쪽은 손 전용 후보 · 애니메이션에는 아직 미적용' if kind=='handrefineready' else '손 관절 미리보기 완료 · SAM 추정 투영값 확인용')
                    self.folder_button.configure(state='normal')
                elif kind=='editorloaded':
                    try:
                        self.studio.editor.loaded(*data)
                        self.status_text.set('4번 편집 준비 완료 · 본 선택 후 위치·회전을 조절하세요')
                    except (OSError,ValueError,KeyError) as exc:
                        self.status_text.set('편집 모델을 불러올 수 없습니다');self.detail_text.set(str(exc))
                elif kind=='editorapplied':
                    self.saved_preview_path=Path(data);self.requested_preview_path=self.saved_preview_path
                    self.studio.editor.last_output=self.saved_preview_path
                    self.result_dir=ROOT/'outputs'/self.saved_preview_path.resolve().relative_to((ROOT/'outputs').resolve()).parts[0]
                    self.status_text.set('편집 결과 출력 완료 · 3번에서 수정된 모델 애니메이션 확인 가능')
                    self.studio.editor.message.set('출력 완료: '+str(self.saved_preview_path.parent)+' · animation.blend / Edited_Manny.fbx / model-preview.mp4')
                    self.progress.configure(value=100)
                elif kind=='finalexported':
                    self.studio.final_panel.exported_to(data)
                    self.progress.configure(value=100);self.status_text.set('최종 결과 내보내기 완료')
                    self.detail_text.set(str(data))
                elif kind=='builtininstalled':
                    self.studio.refresh_builtin_status()
                    self.progress.configure(value=100)
                    self.status_text.set('기본 모델 파일 연결 완료')
                elif kind=='usermodelinstalled':
                    self.studio.refresh_models();self.progress.configure(value=100)
                    self.status_text.set('모델 추가 완료 · 본·손가락 연결 준비됨')
                    self.pending_model_apply=bool(self.result_dir and (self.result_dir/'sam3d.json').is_file())
                elif kind in ('modelpreviewready','builtinpreviewready'):
                    self.progress.configure(value=100)
                    self.saved_preview_path=Path(data)
                    if self.capture is not None:
                        self.requested_preview_path=self.saved_preview_path;self.stage_preview_changed()
                    else:self.open_video(self.saved_preview_path)
                    self.status_text.set('모델 전용 미리보기 준비 완료 · 원본과 동기 재생')
                elif kind=='motionready':
                    self.load_standard_motion(Path(data));self.skeleton_panel.set_time(self.position/self.video_fps)
                    self.status_text.set('표준 스켈레톤 준비 완료 · 영상과 동기화')
                elif kind=='engineexportready':
                    output=Path(data)
                    corrected=output.parent/'corrected-motion.json'
                    if corrected.is_file():self.load_standard_motion(corrected);self.skeleton_panel.set_time(self.position/self.video_fps)
                    self.status_text.set('엔진용 FBX 저장 완료 · '+str(output))
                    messagebox.showinfo('엔진용 FBX 저장 완료','Motion_Unreal.fbx / Motion_Unity.fbx\n30fps · 기준 스켈레톤 애니메이션\n가림 구간 정보: export.json\n'+str(output))
                elif kind in ('animationready','fingeranimationready'):
                    corrected=Path(data).parent/'corrected-motion.json'
                    if corrected.is_file():self.load_standard_motion(corrected);self.skeleton_panel.set_time(self.position/self.video_fps)
                    self.status_text.set(('손가락 포함 52본 애니메이션 저장 완료 · ' if kind=='fingeranimationready' else 'Blender 애니메이션 저장 완료 · ')+str(data))
                    messagebox.showinfo('애니메이션 저장 완료',('52본 Blender와 Unreal·Unity FBX를 저장했습니다. 창의 몸 미리보기는 22본이며 손가락은 Blender에서 확인하세요.\n' if kind=='fingeranimationready' else 'Blender에서 열고 Space로 재생하세요.\n')+str(data))
                elif kind=='legphase':
                    self.leg_phase=data;self.status_text.set(data)
                elif kind=='progress':
                    if self.cancel_event.is_set():continue
                    done,total=data
                    self.progress.configure(value=min(99.,done/max(total,1)*100))
                    self.status_text.set(f'{self.leg_phase} · {done} / {total}' if self.leg_phase else f'추적·SAM 처리 중 · {done} / 약 {total} 단계' if self.settings().stage=='sam3d' else f'출력 중 · {done} / 약 {total} 프레임')
                elif kind=='completed':
                    output,settings,report=data
                    self.result_dir=output
                    warnings=report.get('warnings',[])
                    self.progress.configure(value=100)
                    count=report['frames_processed']; tracked=report['frames_with_target']
                    self.status_text.set('출력 생성됨 · 대상 유지가 부족하여 확인이 필요합니다' if tracked<count*.5 else
                                         '출력 완료 · 확인할 경고가 있습니다' if warnings else '출력 완료')
                    labels={'target_reselection_required':'대상 분실·모호성으로 재선택 필요',
                            'target_starts_after_frame_zero':'대상 등장 전 구간은 비어 있는 상태로 보존',
                            'target_unavailable_in_some_frames':'일부 프레임의 대상 추정 누락',
                            'unreliable_joints_in_some_frames':'일부 관절 신뢰도 낮음',
                            'multiple_people_detected':'여러 대상 후보 검출',
                            'duplicate_candidates_suppressed':'중복 후보 통합 구간 확인 필요',
                            'local_crop_recovery_used':'인물 영역 재검출 구간 확인 필요',
                            'decoded_frame_count_differs_from_metadata':'영상 표기·실제 프레임 수 차이'}
                    warning_text=' / '.join(labels.get(w,w) for w in warnings)
                    self.detail_text.set(f'총 {count}프레임 / 대상 유지 {tracked}프레임 · 추적률은 관절 정확도가 아닙니다.\n'+
                                         (warning_text+'\n' if warning_text else '')+f'저장: {output.name}')
                    if settings.stage=='sam3d':
                        metrics=report.get('tracking_metrics')
                        continuity=('' if not metrics else
                            f'최대 끊김 {metrics["max_gap_seconds"]:.2f}초 · 박스 점프 {len(metrics["box_jump_events"])} · 몸 중심 점프 {len(metrics["body_jump_events"])} · 대상 변경 검토 {len(metrics["identity_review_events"])}개(확정 아님)\n')
                        self.detail_text.set(f'SAM {count}프레임 / 대상 추적 {tracked}프레임 · 관절 정확도 미검증\n'+
                                             continuity+
                                             (warning_text+'\n' if warnings else '')+
                                             f'후보 선택·다리 재추정 자동 실행 · 저장: {output.name}')
                    self.folder_button.configure(state='normal')
                    values=('3D 미리보기','원본 뼈대','원본 영상') if settings.stage=='pose3d' else ('원본 뼈대','원본 영상')
                    if (output/'mask-tracking.mp4').is_file():values+=('대상 마스크',)
                    if report.get('candidate_selection_directory'):
                        self.candidate_dir=Path(report['candidate_selection_directory']);values=('후보 선택 비교',)+values
                        if (self.candidate_dir/'fullbody-reference.mp4').is_file():values=('전신 기준축',)+values
                        if (self.candidate_dir/'joint-review.mp4').is_file():values=('관절 검사',)+values
                        self.status_text.set('출력·후보 선택 완료 · 후보 선택 비교를 표시합니다')
                        self.detail_text.set(f'왼쪽 원시 / 오른쪽 후보 선택 · 저장: {self.candidate_dir.name}')
                    if report.get('leg_result_directory'):
                        self.leg_result_path=Path(report['leg_result_directory'])/'leg-overlay.mp4';values=('다리 재추정 비교',)+values
                    if report.get('part_result_directory'):
                        self.part_result_path=Path(report['part_result_directory'])/'part-overlay.mp4';values=('부위 재추정 비교',)+values
                    if report.get('reconnection_directory'):
                        self.reconnection_path=Path(report['reconnection_directory'])/'reconnection-overlay.mp4';values=('재관측 연결 비교',)+values
                    if report.get('automatic_postprocess'):self.show_automatic_status(report)
                    self.kind_box.configure(state='readonly',values=values)
                    self.result_kind.set(values[0])
                    self.change_view()
                    self.play()
                    if report.get('model_preview'):
                        self.saved_preview_path=Path(report['model_preview'])
                        self.requested_preview_path=self.saved_preview_path
                        self.stage_preview_changed()
                        self.status_text.set('전체 추출 완료 · 본·모델·손 보정·파일 자동 저장됨')
                        if report.get('model_quality_warnings'):
                            self.status_text.set('추출 저장됨 · 자동 검수에서 확인할 항목이 있습니다')
                            self.detail_text.set(' / '.join(report['model_quality_warnings']))
                    elif report.get('model_preview_error'):
                        self.status_text.set('트래킹·본 저장됨 · 모델 미리보기 생성 실패')
                        self.detail_text.set(report['model_preview_error']+' · 3번의 누락된 모델 결과 복구로 다시 시도할 수 있습니다.')
                    if report.get('motion_error'):self.skeleton_panel.clear('변환 실패: '+report['motion_error'])
                elif kind in ('error','cancelled'):
                    if self.leg_phase=='최종 결과 내보내기':self.studio.final_panel.message.set('내보내기 취소됨' if kind=='cancelled' else '내보내기 실패: '+str(data))
                    self.status_text.set('취소됨 · 저장된 부분 결과가 있으면 cancelled로 표시됩니다' if kind=='cancelled' else '처리 실패 · 입력과 설정을 확인해 주세요')
                    self.detail_text.set('새로 출력하면 기존 결과를 덮어쓰지 않습니다.' if kind=='cancelled' else data)
                    if self.source is None:self.info_text.set('유효한 로컬 MP4 파일 하나를 다시 넣어 주세요.')
                    if self.run_output and self.run_output.is_dir():
                        self.result_dir=self.run_output
                        self.folder_button.configure(state='normal')
                elif kind=='finished':
                    self.busy=False
                    self.leg_phase=None
                    self.set_busy(False)
                    self.result_panel.refresh(selected=self.result_dir)
                    if self.studio.active_stage==2:self.studio.refresh_models()
                    if self.studio.active_stage==4:self.studio.final_panel.refresh()
                    if self.pending_model_apply:
                        self.pending_model_apply=False;self.root.after(0,self.apply_builtin_model)
        except Empty:
            pass
        if self.closing and not self.busy and not (self.worker and self.worker.is_alive()):
            self.stop_video();self.root.destroy();return
        self.root.after(80,self.poll)

    def open_video(self,path):
        self.stop_video()
        self.frame=None;self.requested_preview_path=Path(path)
        from app.tracking_preview import tracking_assets,CompanionVideo
        from app.model_preview import model_asset,prepare_model_preview
        paired=self.studio.active_stage==0
        model=model_asset(self.result_dir,path)
        model_path=model.path if model and not model.legacy else None
        original,tracking=tracking_assets(self.result_dir,self.original_preview_override or (model.source if model else None) or self.source)
        if tracking is None and model and model.tracking and model.tracking.is_file():tracking=model.tracking
        actual=original or (model_path if self.studio.active_stage==2 else None) or tracking or Path(path)
        self.preview_is_original=bool(original and actual.resolve()==original.resolve())
        self.preview_is_tracking=bool(tracking and actual.resolve()==tracking.resolve() and not self.preview_is_original)
        self.preview_is_model=bool(model_path and actual.resolve()==model_path.resolve() and not self.preview_is_original)
        cap=cv2.VideoCapture()
        if not cap.open(str(actual),cv2.CAP_FFMPEG,[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,5000,
                                                 cv2.CAP_PROP_READ_TIMEOUT_MSEC,5000]):
            cap.release();self.status_text.set('미리보기 영상을 열 수 없습니다');self.render_frame();return
        self.capture=cap
        self.video_fps=max(1.,cap.get(cv2.CAP_PROP_FPS))
        self.video_count=max(1,int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        self.preview_path=actual
        if paired and tracking and tracking.resolve()!=actual.resolve():
            try:self.tracking_capture=CompanionVideo(tracking)
            except (ValueError,cv2.error) as exc:self.detail_text.set(str(exc))
        if self.studio.active_stage==2 and model_path and model_path.resolve()!=actual.resolve():
            try:self.model_capture=CompanionVideo(model_path,'모델')
            except (ValueError,cv2.error) as exc:self.detail_text.set(str(exc))
        if not original and self.result_dir:
            self.detail_text.set('원본 경로를 찾을 수 없습니다. 원본 영상을 다시 연결해 주세요. 결과는 오른쪽에 표시됩니다.')
        motion=self.result_dir/'motion/motion.json' if self.result_dir else None
        if motion is not None and motion.is_file():self.load_standard_motion(motion)
        elif self.busy and self.run_output is not None and self.result_dir==self.run_output:
            self.skeleton_panel.clear('본 생성 대기 · 자동 후처리가 끝나면 표시됩니다')
        else:self.skeleton_panel.clear('본 데이터 없음 · 새 영상 추출 시 자동 생성됩니다.')
        self.seek.configure(to=self.video_count-1,state='normal')
        self.play_button.configure(state='normal')
        self.read_video_frame()
        if self.studio.active_stage==2 and model and model.legacy and not self.busy:
            self.status_text.set('모델 전용 미리보기 분리 중 · 기존 합본은 보존됩니다')
            self.launch_worker('modelpreviewready',lambda:prepare_model_preview(model.path,self.cancel_event.is_set,
                lambda done,total:self.events.put(('progress',(done,total)))))

    def stage_preview_changed(self):
        if self.requested_preview_path is None:
            self.render_frame();return
        if self.capture is None:
            self.open_video(self.requested_preview_path);return
        seconds=self.position/self.video_fps;playing=self.playing
        self.open_video(self.requested_preview_path)
        if self.capture is not None:
            self.seek_var.set(min(self.video_count-1,round(seconds*self.video_fps)));self.seek_end()
            if playing:self.play()

    def reconnect_original(self):
        if self.busy:return
        name=filedialog.askopenfilename(parent=self.root,title='이 결과의 원본 MP4 다시 연결',filetypes=[('MP4 영상','*.mp4')])
        if not name:return
        # Preview-only link: do not replace extraction input or allow accidental reruns.
        self.original_preview_override=Path(name)
        self.stage_preview_changed()

    def load_standard_motion(self,path):
        try:
            if path.name=='motion.json':
                from app.animation_job import latest_corrected_motion
                path=latest_corrected_motion(path)
            self.skeleton_panel.load(path)
            self.skeleton_panel.set_time(self.position/self.video_fps)
            original=self.preview_is_original
            if len(self.skeleton_panel.points)!=self.video_count and not original:
                self.skeleton_panel.clear('표본/구간 영상은 원본 타임라인과 달라 동기 표시하지 않습니다')
        except (OSError,ValueError,KeyError) as exc:self.skeleton_panel.clear(f'스켈레톤 읽기 실패: {exc}')

    def change_view(self,event=None):
        if self.result_kind.get()=='저장 영상' and self.saved_preview_path:
            self.open_video(self.saved_preview_path);return
        kind=self.result_kind.get()
        if kind=='재관측 연결 비교' and self.reconnection_path:
            self.open_video(self.reconnection_path);return
        if kind=='부위 재추정 비교' and self.part_result_path:
            self.open_video(self.part_result_path);return
        if kind=='관절 검사' and self.candidate_dir:
            self.open_video(self.candidate_dir/'joint-review.mp4');return
        if kind=='전신 기준축' and self.candidate_dir:
            self.open_video(self.candidate_dir/'fullbody-reference.mp4');return
        if kind=='다리 재추정 비교' and self.leg_result_path:
            self.open_video(self.leg_result_path);return
        if kind=='후보 선택 비교' and self.candidate_dir:
            self.open_video(self.candidate_dir/'candidate-overlay.mp4');return
        if kind=='대상 마스크' and self.result_dir:
            path=self.result_dir/'mask-tracking.mp4'
            if path.is_file():self.open_video(path)
            return
        path=self.source if kind=='원본 영상' else self.result_dir/('preview3d.mp4' if kind.startswith('3D') else 'overlay.mp4') if self.result_dir else None
        if path and path.is_file():self.open_video(path)


    def render_frame(self):
        if hasattr(self,'skeleton_panel'):self.skeleton_panel.set_time(self.position/self.video_fps)
        stage=getattr(getattr(self,'studio',None),'active_stage',0)
        left=self.frame if self.preview_is_original else None
        self.photo=self.draw_preview(self.canvas,left,'원본 영상을 업로드하거나 다시 연결하세요')
        if stage in (0,2):
            if stage==2:
                right=self.model_frame if self.model_capture else self.frame if self.preview_is_model else None
                live=self.studio.editor.live_frame(self.position/self.video_fps,max(1,self.tracking_canvas.winfo_width()),max(1,self.tracking_canvas.winfo_height()))
                if live is not None:right=live
                self.studio.tracking_title.configure(text='모델 애니메이션 · 실시간 편집' if live is not None else '모델 애니메이션')
                missing='이 시점의 모델 프레임이 없습니다' if self.model_capture else '모델 결과 없음\n새 추출 시 선택 모델 자동 적용 · 기존 결과는 모델 적용'
            else:
                right=self.tracking_frame if self.tracking_capture else self.frame if self.preview_is_tracking else None
                missing='이 시점의 트래킹 프레임이 없습니다' if self.tracking_capture else '트래킹을 시작하면 결과가 표시됩니다'
            if stage==0 and right is None and not self.tracking_capture and self.candidate_preview_index==self.position:
                right=self.candidate_preview_frame
            self.tracking_photo=self.draw_preview(self.tracking_canvas,right,missing)

    def draw_preview(self,canvas,frame,placeholder):
        w,h=max(1,canvas.winfo_width()),max(1,canvas.winfo_height())
        canvas.delete('all')
        if frame is None:
            canvas.create_text(w//2,h//2,text=placeholder,fill='#7690ab',font=('맑은 고딕',11),
                               justify='center',width=max(1,w-32),tags='placeholder')
            return None
        image=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
        image.thumbnail((w,h),Image.Resampling.LANCZOS)
        photo=ImageTk.PhotoImage(image,master=self.root)
        canvas.create_image(w//2,h//2,image=photo,anchor='center')
        return photo

    def generate_hand_preview(self,refine=False):
        if self.busy or not self.result_dir:return
        folder=Path(self.result_dir)
        if not (folder/'sam3d.json').is_file():
            self.status_text.set('완료된 SAM3D 결과를 선택해 주세요');return
        self.pause();self.status_text.set('손 부분 확대 재추정 비교 생성 중 · CPU 처리' if refine else '손 관절 미리보기 생성 중 · 기존 SAM 데이터 사용')
        def operation():
            if refine:
                from app.hand_refine_job import reestimate_hands
                return str(reestimate_hands(folder,self.cancel_event.is_set,lambda a,b:self.events.put(('progress',(a,b)))))
            from app.hand_preview_job import generate_hand_preview
            return str(generate_hand_preview(folder,self.cancel_event.is_set,lambda a,b:self.events.put(('progress',(a,b)))))
        self.launch_worker('handrefineready' if refine else 'handpreviewready',operation)

    def add_user_model(self):
        if self.busy:return
        path=filedialog.askopenfilename(parent=self.root,title='모델 추가 · 본이 없으면 기본 본 생성',
            filetypes=[('3D 모델','*.fbx *.glb *.gltf *.obj *.blend')])
        if not path:return
        from app.user_models import import_model
        self.pause();self.status_text.set('모델 확인·본 준비 중 · 원본 파일 보존')
        self.leg_phase='사용자 모델 추가';self.progress.configure(value=0)
        self.launch_worker('usermodelinstalled',lambda:import_model(path,self.cancel_event.is_set,
            lambda done,total:self.events.put(('progress',(done,total)))))

    def install_builtin_model(self):
        if self.busy:return
        key=self.studio.selected_builtin()
        path=filedialog.askopenfilename(parent=self.root,title='Unreal Manny FBX 선택',
            filetypes=[('모델 파일','*.fbx')])
        if not path:return
        from app.builtin_models import install_model
        self.status_text.set('기본 모델 불러오는 중 · 원본 파일은 보존됩니다')
        self.progress.configure(value=0)
        self.launch_worker('builtininstalled',lambda:install_model(key,path,self.cancel_event.is_set))

    def apply_builtin_model(self):
        if self.busy:return
        if not self.result_dir or not (self.result_dir/'sam3d.json').is_file():
            self.status_text.set('완료된 SAM3D 결과를 먼저 선택해 주세요');return
        from app.builtin_models import apply_model
        folder=self.result_dir;key=self.studio.selected_builtin()
        self.pause();self.status_text.set('기본 모델 적용 · 본 변환 및 미리보기 생성 중')
        self.leg_phase='기본 모델 적용·미리보기 렌더링';self.progress.configure(value=0)
        self.launch_worker('builtinpreviewready',lambda:apply_model(folder,key,self.cancel_event.is_set,
            lambda a,b:self.events.put(('progress',(a,b)))))

    def generate_animation(self,engine=False,fingers=False):
        if self.busy or not self.result_dir:return
        use_refinement=bool(fingers and self.use_refined_hands.get())
        folder=Path(self.result_dir)
        if not (folder/'sam3d.json').is_file():
            self.status_text.set('완료된 SAM3D 결과를 선택해 주세요');return
        self.pause();self.status_text.set('접지·SLERP 떨림 보정 후 Blender 애니메이션 생성 중 · CPU 처리')
        def operation():
            from app.motion_job import ensure_motion
            from app.animation_job import export_animation
            source=Path(json.loads((folder/'sam-request.json').read_text(encoding='utf-8'))['source'])
            report=folder/'automatic-report.json'
            post=json.loads(report.read_text(encoding='utf-8')) if report.is_file() else {}
            motion,_=ensure_motion(folder,source,post,self.cancel_event.is_set)
            blend=export_animation(motion,self.cancel_event.is_set)
            if fingers:
                from app.finger_job import export_fingers,latest_hand_crop
                from app.engine_export_job import export_engine_fbx
                crop=latest_hand_crop(folder) if use_refinement else None
                blend=export_fingers(blend,folder/'sam3d.json',self.cancel_event.is_set,**({} if crop is None else {'crop_report':crop}))
                export_engine_fbx(blend,self.cancel_event.is_set)
            if engine:
                from app.engine_export_job import export_engine_fbx
                return str(export_engine_fbx(blend,self.cancel_event.is_set))
            return str(blend)
        self.launch_worker('fingeranimationready' if fingers else 'engineexportready' if engine else 'animationready',operation)

    def generate_motion(self):
        if self.busy or not self.result_dir:return
        folder=Path(self.result_dir)
        if not (folder/'sam3d.json').is_file():
            self.skeleton_panel.clear('완료된 SAM3D 결과를 선택해 주세요');return
        self.pause();self.status_text.set('기존 추출에서 표준 스켈레톤 변환 중 · 모델 재추론 없음')
        def operation():
            from app.motion_job import ensure_motion
            source=Path(json.loads((folder/'sam-request.json').read_text(encoding='utf-8'))['source'])
            report=folder/'automatic-report.json'
            post=json.loads(report.read_text(encoding='utf-8')) if report.is_file() else {}
            path,_=ensure_motion(folder,source,post,self.cancel_event.is_set)
            return str(path)
        self.launch_worker('motionready',operation)

    @staticmethod
    def display_name(name):
        return name if len(name)<=50 else name[:28]+'…'+name[-18:]

    @staticmethod
    def clock(seconds):
        seconds=max(0,int(seconds));return f'{seconds//60:02d}:{seconds%60:02d}'

    def read_video_frame(self):
        if self.capture is None:return False
        ok,frame=self.capture.read()
        if not ok:return False
        self.position=max(0,int(self.capture.get(cv2.CAP_PROP_POS_FRAMES))-1)
        if self.tracking_capture is not None:
            self.tracking_frame=self.tracking_capture.frame_at(self.position/self.video_fps)
        if self.model_capture is not None:
            self.model_frame=self.model_capture.frame_at(self.position/self.video_fps)
        self.frame=frame;self.render_frame()
        self.seek_var.set(self.position)
        self.time_text.set(f'{self.clock(self.position/self.video_fps)} / {self.clock(self.video_count/self.video_fps)}')
        return True

    def play(self):
        if self.capture is None:return
        if self.position>=self.video_count-1:
            self.capture.set(cv2.CAP_PROP_POS_FRAMES,0)
        if self.playing:return
        self.playing=True;self.play_button.configure(text='일시정지')
        self.tick()

    def tick(self):
        self.play_timer=None
        if not self.playing:return
        start=time.perf_counter()
        if not self.read_video_frame():self.pause();return
        delay=max(1,round(1000/self.video_fps-(time.perf_counter()-start)*1000))
        self.play_timer=self.root.after(delay,self.tick)

    def pause(self):
        self.playing=False
        if self.play_timer is not None:
            self.root.after_cancel(self.play_timer);self.play_timer=None
        self.play_button.configure(text='재생')

    def toggle_play(self):
        if self.playing:self.pause()
        else:self.play()

    def seek_begin(self,event=None):
        self.was_playing=self.playing;self.pause()

    def seek_end(self,event=None):
        if self.capture is None:return
        self.capture.set(cv2.CAP_PROP_POS_FRAMES,max(0,min(self.video_count-1,round(self.seek_var.get()))))
        self.read_video_frame()
        if self.was_playing:self.play()
        self.was_playing=False

    def stop_video(self):
        self.pause()
        if self.tracking_capture is not None:self.tracking_capture.close();self.tracking_capture=None
        self.tracking_frame=None
        if self.model_capture is not None:self.model_capture.close();self.model_capture=None
        self.model_frame=None
        if self.capture is not None:self.capture.release();self.capture=None
        self.play_button.configure(state='disabled')
        self.seek.configure(state='disabled')

    def open_folder(self):
        if self.result_dir and self.result_dir.is_dir():
            try:os.startfile(str(self.result_dir))
            except OSError:self.status_text.set('결과 폴더를 열 수 없습니다')

    def close(self):
        if self.studio.editor.clip and (self.studio.editor.clip.dirty or self.studio.editor.draft):
            if not messagebox.askyesno('편집 종료','저장하지 않은 애니메이션 편집을 버리고 종료할까요?',parent=self.root):return
        self.studio.editor.pause()
        self.studio.final_panel.clear()
        self.closing=True
        self.stop_video()
        if self.busy:
            self.cancel_event.set();self.set_busy(True)
            self.status_text.set('처리를 취소하고 종료하는 중…')
        else:self.root.destroy()


def main():
    root=TkinterDnD.Tk()
    PrototypeApp(root)
    root.mainloop()


if __name__=='__main__':
    main()
