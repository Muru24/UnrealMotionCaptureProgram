"""Conservative single-target association; ambiguity requires explicit reselection."""

from dataclasses import dataclass

import cv2
import numpy as np

from .interface import Pose2DError, TrackingInfo


def box_iou(a, b) -> float:
    left = np.maximum(a[:2], b[:2])
    right = np.minimum(a[2:], b[2:])
    intersection = float(np.maximum(right - left, 0).prod())
    area_a = float(np.prod(a[2:] - a[:2]))
    area_b = float(np.prod(b[2:] - b[:2]))
    return intersection / max(area_a + area_b - intersection, 1e-6)


def suppress_duplicate_boxes(boxes: np.ndarray, frame=None) -> np.ndarray:
    """Remove tightly overlapping nested detections before identity association.

    RTMPose's person detector can emit a torso/full-body pair for one person,
    particularly when an arm or accessory extends the wider detection.
    Partial overlaps remain separate candidates for the crossing guard.
    """
    kept = []
    for box in sorted(boxes, key=lambda b: float(np.prod(b[2:] - b[:2])), reverse=True):
        duplicate = False
        for other in kept:
            intersection = float(np.maximum(np.minimum(box[2:], other[2:]) -
                                             np.maximum(box[:2], other[:2]), 0).prod())
            smaller_area = min(float(np.prod(box[2:] - box[:2])),
                               float(np.prod(other[2:] - other[:2])))
            overlap=box_iou(box,other)
            same_height=min(box[3]-box[1],other[3]-other[1])/max(box[3]-box[1],other[3]-other[1])>.9
            sam_nested=(frame is not None and overlap>.45 and same_height and
                        appearance_distance(appearance(frame,box),appearance(frame,other))<.35)
            if (overlap > .6 or sam_nested) and intersection / max(smaller_area, 1e-6) > .95:
                duplicate = True
                break
        if not duplicate:
            kept.append(box)
    result = np.asarray(kept, dtype=np.float32).reshape(-1, 4)
    return result[np.lexsort((result[:, 1], result[:, 0]))]


def appearance(frame, box):
    x1, y1, x2, y2 = box
    width, height = x2 - x1, y2 - y1
    # Central torso avoids much of the background and swinging hands.
    crop = frame[int(y1 + height * .2):max(int(y1 + height * .7), int(y1 + height * .2) + 1),
                 int(x1 + width * .2):max(int(x1 + width * .8), int(x1 + width * .2) + 1)]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    chroma = cv2.calcHist([hsv], [0, 1], None, [12, 8], [0, 180, 0, 256])
    value = cv2.calcHist([hsv], [2], None, [16], [0, 256])
    return tuple(h / max(float(h.sum()), 1) for h in (chroma, value))


def appearance_distance(a, b) -> float:
    return max(cv2.compareHist(x, y, cv2.HISTCMP_BHATTACHARYYA)
               for x, y in zip(a, b))


@dataclass(frozen=True)
class TrackingDecision:
    bbox: tuple[float, float, float, float] | None
    info: TrackingInfo


class TargetTracker:
    """Single-target association; optional conservative long-gap reference matching.

    Default callers retain sticky loss. Reference matching is not biometric ReID
    and cannot resume a gap containing observed overlapping-person ambiguity.
    """

    def __init__(self, target_index=None, target_box=None, max_missing=5, *,
                 reconnection_iou=.5, reconnect_confirmations=1, gap_appearance_limit=.35,
                 multi_cue=False, motion_fps=None, fast_reconnect=False, long_reidentify=False, rival_guard=False, reconnect_identity_guard=False):
        if target_index is not None and (not isinstance(target_index, int) or target_index < 0):
            raise Pose2DError("Target index must be a non-negative integer.")
        if target_index is not None and target_box is not None:
            raise Pose2DError("Choose target-index or target-box, not both.")
        if target_box is not None:
            values = np.asarray(target_box, dtype=float)
            if values.shape != (4,) or not np.isfinite(values).all() or \
                    min(values) < 0 or values[2] <= values[0] or values[3] <= values[1]:
                raise Pose2DError("Target box must be finite x1 y1 x2 y2 with positive size.")
        self.target_index = target_index
        self.target_box = target_box
        self.max_missing = max_missing
        self.reconnection_iou=reconnection_iou
        self.reconnect_confirmations=reconnect_confirmations
        self.gap_appearance_limit=gap_appearance_limit
        self.pending_box=None
        self.pending_hits=0
        self.box = None
        self.velocity = np.zeros(2, dtype=float)
        self.anchor = self.recent = None
        self.missing = 0
        self.latched = False
        self.reconnect_identity_guard = reconnect_identity_guard
        self.lock_reason = None
        self.first_frame = True
        self.multi_cue=multi_cue
        self.skeleton=None
        self.association_diagnostics=[]
        from .motion import BodyMotion
        self.motion=None if motion_fps is None else BodyMotion(motion_fps)
        self.motion_diagnostics={}
        self.fast_reconnect=fast_reconnect
        self.gap_ambiguous=False
        self.long_reidentify=long_reidentify
        self.segment=0
        from .reidentify import TargetReferences
        self.references=TargetReferences()
        from .rivals import OtherPeople
        self.other_people=OtherPeople(motion_fps) if rival_guard and motion_fps is not None else None

    @property
    def can_reidentify(self):
        return (self.long_reidentify and self.motion is not None and not self.gap_ambiguous and
                self.lock_reason=='gap_too_long' and self.missing*self.motion.dt<=5 and
                bool(self.references.gallery))

    def _decision(self, state, reason, box=None):
        return TrackingDecision(None if box is None else tuple(float(v) for v in box),
                                TrackingInfo(state, reason, 1 if self.box is not None else None,
                                             self.missing, self.latched or state == "lost"))

    def _miss(self, reason, latch=False, keep_pending=False):
        if reason in ('ambiguous_candidates','overlapping_people'):
            self.gap_ambiguous=True
        if self.motion is not None and reason in ('ambiguous_candidates','overlapping_people'):
            latch=False
        if not keep_pending:
            self.pending_box=None;self.pending_hits=0
        self.missing += 1
        if latch:
            self.latched = True
            self.lock_reason = reason
        state = "lost" if self.missing > self.max_missing else "uncertain"
        if state == "lost":
            self.latched = True
            self.lock_reason = self.lock_reason or "gap_too_long"
        return self._decision(state, self.lock_reason or reason)

    def select(self, frame, boxes: np.ndarray, keypoints=None) -> TrackingDecision:
        if self.other_people is not None:self.other_people.advance()
        decision=self._select(frame,boxes,keypoints)
        if self.other_people is not None:self.other_people.observe(frame,boxes,decision.bbox,allow_follow=not self.latched,keypoints=keypoints)
        return decision

    def _select(self, frame, boxes: np.ndarray, keypoints=None) -> TrackingDecision:
        self.association_diagnostics=[]
        self.motion_diagnostics={}
        if keypoints is not None and (np.shape(keypoints[0])!=(len(boxes),17,2) or np.shape(keypoints[1])!=(len(boxes),17)):
            raise Pose2DError('Association keypoints do not match detector candidates.')
        first_frame = self.first_frame
        self.first_frame = False
        if first_frame and self.target_box is not None:
            height, width = frame.shape[:2]
            if self.target_box[2] > width or self.target_box[3] > height:
                raise Pose2DError("Target box exceeds the video dimensions.")
        if self.box is None:
            if len(boxes) == 0:
                if first_frame and (self.target_index is not None or self.target_box is not None):
                    raise Pose2DError("No target candidates on the first frame. Selection cannot be applied.")
                return self._decision("uninitialized", "no_initial_detection")
            if self.target_index is not None:
                if self.target_index >= len(boxes):
                    raise Pose2DError("Target index is outside the first-frame candidate list.")
                selected = self.target_index
            elif self.target_box is not None:
                overlaps = sorted(((box_iou(np.asarray(self.target_box), b), i)
                                   for i, b in enumerate(boxes)), reverse=True)
                if overlaps[0][0] < .25 or (len(overlaps) > 1 and
                                                          overlaps[0][0] - overlaps[1][0] < .15):
                    raise Pose2DError("Target box does not select one unambiguous person.")
                selected = overlaps[0][1]
            elif len(boxes) == 1:
                selected = 0
            else:
                raise Pose2DError("Multiple initial people. Use --list-targets then --target-index or --target-box.")
            self.box = boxes[selected].copy()
            self.anchor = self.recent = appearance(frame, self.box)
            if keypoints is not None:self.skeleton=tuple(v[selected].copy() for v in keypoints)
            if self.long_reidentify:self.references.remember(frame,self.box,self.skeleton)
            if self.motion is not None:
                z,kind=self.motion.initialize(self.box,None if keypoints is None else tuple(v[selected] for v in keypoints))
                self.motion_diagnostics={'predicted_center':z.tolist(),'observed_center':z.tolist(),
                    'filtered_center':z.tolist(),'observation_kind':kind,'prediction_only':False,
                    'observation_quality':getattr(self.motion,'observation_quality',{})}
            return self._decision("tracked", "initial_selection", self.box)

        if self.latched:
            if self.motion is not None:self.motion_diagnostics={'prediction_expired':True,'prediction_only':True}
            if self.can_reidentify:
                index,review=self.references.consider(frame,boxes,keypoints,self.box)
                self.motion_diagnostics['reidentification']=review
                if index is not None:
                    if self.other_people is not None:
                        descriptor=appearance(frame,boxes[index])
                        color=min(appearance_distance(descriptor,self.anchor),appearance_distance(descriptor,self.recent))
                        guard=self.other_people.check(boxes[index],descriptor,self.box,color,
                            None if keypoints is None else tuple(v[index] for v in keypoints),self.skeleton)
                        if guard['rejected']:
                            self.references.clear_pending();self.association_diagnostics.append({'candidate_index':index,**guard})
                            return self._miss('matches_recent_other_person')
                    from .motion import BodyMotion
                    gap=self.missing
                    self.box=boxes[index].copy();self.skeleton=tuple(v[index].copy() for v in keypoints)
                    self.motion=BodyMotion(1/self.motion.dt)
                    z,kind=self.motion.initialize(self.box,self.skeleton)
                    self.velocity=np.zeros(2);self.recent=appearance(frame,self.box)
                    self.latched=False;self.lock_reason=None;self.missing=0
                    self.pending_box=None;self.pending_hits=0;self.references.clear_pending();self.segment+=1
                    self.motion_diagnostics={'observed_center':z.tolist(),'filtered_center':z.tolist(),
                        'observation_kind':kind,'observation_quality':self.motion.observation_quality,
                        'prediction_only':False,'long_reidentified':True,'gap_before_frames':gap,
                        'reidentification':review,'filter_reset':True}
                    return self._decision('tracked','long_gap_reidentified',self.box)
            else:self.references.clear_pending()
            return self._miss(self.lock_reason or "reselection_required")
        if self.motion is not None:
            prediction=self.motion.predict()
            self.motion_diagnostics={'predicted_center':prediction.tolist(),
                'predicted_std_pixels':np.sqrt(np.diag(self.motion.P)[:2]).tolist(),
                'prediction_only':True,'observed_center':None}
        if len(boxes) == 0:
            return self._miss("no_person_detections")
        predicted = self.box + np.tile(self.velocity * (self.missing + 1), 2)
        if self.motion is not None:
            predicted=self.box+np.tile(prediction-self.motion.box_offset-(self.box[:2]+self.box[2:])/2,2)
        diagonal = max(float(np.linalg.norm(self.box[2:] - self.box[:2])), 1)
        candidates = []
        for index, box in enumerate(boxes):
            ratio = float(np.prod(box[2:] - box[:2]) / np.prod(self.box[2:] - self.box[:2]))
            overlap = box_iou(predicted, box)
            distance = float(np.linalg.norm((box[:2] + box[2:] - predicted[:2] - predicted[2:]) / 2)) / diagonal
            innovation=None;observed_kind=None
            if self.motion is not None:
                z,observed_kind,std,_,_=self.motion.measurement(box,None if keypoints is None else tuple(v[index] for v in keypoints))
                innovation=self.motion.innovation(z,std)
                physical_distance=float(np.linalg.norm(z-prediction))/diagonal
                distance=float(np.sqrt(max(innovation,0)/9.21))*.65
                if innovation>9.21 or physical_distance>.65:
                    self.association_diagnostics.append({'candidate_index':index,'rejected':True,'reason':'motion_gate',
                        'mahalanobis_squared':innovation,'physical_distance_normalized':physical_distance,
                        'observation_quality':getattr(self.motion,'observation_quality',{})})
                    continue
            if not .35 <= ratio <= 2.8 or (not self.multi_cue and overlap < .1) or distance > .65:
                if self.multi_cue:self.association_diagnostics.append({'candidate_index':index,'rejected':True,'reason':'geometry_gate','predicted_center_distance':distance,'area_ratio':ratio})
                continue
            descriptor = appearance(frame, box)
            color_distance = min(appearance_distance(descriptor, self.anchor),
                                 appearance_distance(descriptor, self.recent))
            if self.missing and self.other_people is not None:
                guard=self.other_people.check(box,descriptor,predicted,color_distance,
                    None if keypoints is None else tuple(v[index] for v in keypoints),self.skeleton)
                if guard['rejected']:
                    self.association_diagnostics.append({'candidate_index':index,**guard});continue
            motion_support=(self.motion is not None and observed_kind in ('hip','shoulder_with_hip_offset') and
                            innovation<2.5 and physical_distance<.15 and color_distance<.8)
            if color_distance > (self.gap_appearance_limit if self.missing else .65) and not motion_support:
                if self.multi_cue:self.association_diagnostics.append({'candidate_index':index,'rejected':True,'reason':'appearance_gate','appearance_distance':color_distance})
                continue
            if self.multi_cue:
                from .association import skeleton_similarity,tracking_score
                current=None if keypoints is None else tuple(v[index] for v in keypoints)
                similarity=skeleton_similarity(self.skeleton,current)
                score,components,weights=tracking_score(overlap,distance,similarity,1-color_distance)
                body_motion_evidence=(self.motion is not None and observed_kind in ('hip','shoulder_with_hip_offset') and
                                      innovation<2.5 and color_distance<.35)
                # A spatially convenient box alone cannot establish identity
                # after a dropout, particularly across a cut with similar clothes.
                if self.reconnect_identity_guard and self.missing and (similarity is None or similarity<.25) and color_distance>.3:
                    self.association_diagnostics.append({'candidate_index':index,'rejected':True,
                        'reason':'weak_reconnection_identity','skeleton_similarity':similarity,
                        'appearance_distance':color_distance})
                    continue
                rejected=(overlap<.1 and not body_motion_evidence and
                          (similarity is None or similarity<.7 or color_distance>.35)) or score<.45
                self.association_diagnostics.append({'candidate_index':index,'score':score,'components':components,
                    'effective_weights':weights,'rejected':rejected,'appearance_kind':'HSV_histograms_not_learned_ReID',
                    'mahalanobis_squared':innovation,'center_observation_kind':observed_kind,
                    'observation_quality':getattr(self.motion,'observation_quality',{}),
                    'appearance_gate_relaxed_by_body_motion':motion_support and color_distance>(self.gap_appearance_limit if self.missing else .65)})
                if rejected:continue
            else:
                score = .65 * overlap + .20 * (1 - color_distance) + .15 * max(0, 1 - distance)
            candidates.append((score, index, descriptor))
        if not candidates:
            return self._miss("target_not_matched")
        candidates.sort(key=lambda candidate: candidate[0], reverse=True)
        score, selected, descriptor = candidates[0]
        chosen = boxes[selected]
        if len(candidates) > 1 and score - candidates[1][0] < .12:
            return self._miss("ambiguous_candidates", latch=True)
        # Two overlapping, similarly sized boxes can conceal an identity swap.
        # Very small background detections cannot represent this full-body target.
        overlapping=False
        for index, other in enumerate(boxes):
            if index == selected:
                continue
            ratio = float(np.prod(other[2:] - other[:2]) / np.prod(chosen[2:] - chosen[:2]))
            overlap = box_iou(chosen, other)
            if .4 <= ratio <= 2.5 and overlap > .2:
                if self.motion is None:return self._miss("overlapping_people", latch=True)
                overlapping=True
        if overlapping:
            self.gap_ambiguous=True
            cue=next((r for r in self.association_diagnostics if r['candidate_index']==selected and 'components' in r),None)
            margin=score-candidates[1][0] if len(candidates)>1 else score
            strong=(cue is not None and margin>=.18 and cue['components']['center']>.65 and
                    cue['components']['appearance']>.75 and cue['components']['skeleton'] is not None and
                    cue['components']['skeleton']>.7)
            if not strong:return self._miss('overlapping_people')
        if self.missing and box_iou(predicted, chosen) < self.reconnection_iou:
            cue=next((r for r in self.association_diagnostics if r['candidate_index']==selected and 'components' in r),None)
            strong=(cue is not None and cue['components']['skeleton'] is not None and
                    cue['components']['skeleton']>.8 and cue['components']['appearance']>.75 and
                    cue['components']['center']>.65 and cue['score']>.65)
            if not strong:return self._miss("weak_reconnection")
        cue=next((r for r in self.association_diagnostics if r['candidate_index']==selected and 'components' in r),None)
        # Bypass one confirmation only for a very short, unambiguous dropout
        # with independent body, appearance, skeleton and geometric evidence.
        fast=(self.fast_reconnect and self.motion is not None and self.missing>0 and
              self.missing*self.motion.dt<=.1 and not overlapping and not self.gap_ambiguous and
              cue is not None and cue['center_observation_kind'] in ('hip','shoulder_with_hip_offset') and
              (len(candidates)==1 or score-candidates[1][0]>=.18) and
              cue['components']['iou']>=.5 and cue['components']['center']>.65 and
              cue['components']['appearance']>.7 and cue['components']['skeleton'] is not None and
              cue['components']['skeleton']>.8 and score>.7)
        if self.missing and self.motion is not None:
            self.motion_diagnostics['reconnection']={'fast_path':bool(fast),
                'gap_ambiguous':self.gap_ambiguous,'missing_before_candidate':self.missing}
        if (self.missing or overlapping) and self.reconnect_confirmations>1 and not fast:
            self.pending_hits=(self.pending_hits+1 if self.pending_box is not None and
                               box_iou(self.pending_box,chosen)>.35 else 1)
            self.pending_box=chosen.copy()
            if self.pending_hits<self.reconnect_confirmations:
                return self._miss('reconnection_pending',keep_pending=True)
        old_center = (self.box[:2] + self.box[2:]) / 2
        center = (chosen[:2] + chosen[2:]) / 2
        self.velocity = .5 * self.velocity + .5 * (center - old_center) / (self.missing + 1)
        reason = "short_gap_reconnected" if self.missing else "matched"
        self.box = chosen.copy()
        if self.motion is not None:
            z,kind=self.motion.update(chosen,None if keypoints is None else tuple(v[selected] for v in keypoints))
            self.motion_diagnostics.update(observed_center=z.tolist(),filtered_center=self.motion.x[:2].tolist(),
                observation_kind=kind,prediction_only=False,
                observation_quality=getattr(self.motion,'observation_quality',{}))
        self.recent = tuple(.9 * a + .1 * b for a, b in zip(self.recent, descriptor))
        if keypoints is not None:
            from .association import common_joints
            candidate=tuple(v[selected].copy() for v in keypoints)
            if common_joints(candidate,candidate) is not None:self.skeleton=candidate
        self.missing = 0
        self.pending_box=None;self.pending_hits=0
        self.gap_ambiguous=False
        if (self.long_reidentify and not overlapping and cue is not None and cue['score']>.7 and
                cue['components']['appearance']>.7 and cue['components']['center']>.65 and
                self.motion_diagnostics.get('observation_kind') in ('hip','shoulder_with_hip_offset')):
            self.references.remember(frame,self.box,None if keypoints is None else tuple(v[selected] for v in keypoints))
        return self._decision("tracked", reason, self.box)
