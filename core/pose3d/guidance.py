"""Explicit image-space anchors and bounded torso-relative joint prediction.

Never invent model world coordinates from a mouse click. Raw Pose3D stays intact.
"""
from core.video.limits import MAX_VIDEO_FRAMES
import math
import numpy as np

NAMES = ('pelvis', 'chest', 'left_wrist', 'right_wrist', 'left_ankle',
         'right_ankle', 'left_elbow', 'right_elbow', 'left_knee', 'right_knee')
INDICES = {'left_wrist': 15, 'right_wrist': 16, 'left_ankle': 27,
           'right_ankle': 28, 'left_elbow': 13, 'right_elbow': 14,
           'left_knee': 25, 'right_knee': 26}
CHAINS = {'left_wrist': (11, 13, 15), 'right_wrist': (12, 14, 16),
          'left_ankle': (23, 25, 27), 'right_ankle': (24, 26, 28)}


def validate_anchors(anchors, width, height, frames):
    if not isinstance(anchors, dict) or len(anchors) > MAX_VIDEO_FRAMES:
        raise ValueError('Invalid joint anchor frames.')
    result = {}
    for key, points in anchors.items():
        index = int(key)
        if str(index) != str(key) or not 0 <= index < frames or not isinstance(points, dict):
            raise ValueError('Anchor frame is outside the video.')
        if not points or any(n not in NAMES for n in points):
            raise ValueError('Unknown or empty joint anchors.')
        clean = {}
        for name, xy in points.items():
            if not isinstance(xy, (list, tuple)) or len(xy) != 2 or \
                    any(type(v) not in (int, float) or not math.isfinite(v) for v in xy):
                raise ValueError('Anchor coordinates must be finite pixel pairs.')
            if not (0 <= xy[0] < width and 0 <= xy[1] < height):
                raise ValueError('Anchor is outside the source image.')
            clean[name] = list(xy)
        if ('pelvis' in clean) != ('chest' in clean):
            raise ValueError('Specify pelvis and chest together.')
        if 'pelvis' in clean and np.linalg.norm(np.subtract(clean['chest'], clean['pelvis'])) < 12:
            raise ValueError('Torso axis must be at least 12 pixels long.')
        result[index] = clean
    return result


def torso(points):
    if not all(points[i].valid for i in (11, 12, 23, 24)):
        return None
    xy = lambda i: np.array([points[i].image_x, points[i].image_y], dtype=float)
    return (xy(23)+xy(24))/2, (xy(11)+xy(12))/2


class JointGuide:
    max_gap = .2

    def __init__(self, anchors, width, height, fps, frames):
        self.anchors = validate_anchors(anchors, width, height, frames)
        self.width, self.height, self.fps = width, height, fps
        self.history = {}
        self.pending = {}
        self.body = None
        self.body_time = None
        self.body_velocity = np.zeros(2)
        from .point_tracking import ImagePointTracker
        self.image_tracker = ImagePointTracker()

    def candidates(self, candidates, index):
        """Torso, not mask extent, gates identity before the existing tracker."""
        manual = self.anchors.get(index, {})
        if 'pelvis' in manual:
            expected = (np.array(manual['pelvis']), np.array(manual['chest']))
        else:
            # Model torso estimates fail during turns. Do not hard-reject an
            # identity from that same unreliable measurement (real regression).
            # Torso-relative coordinates still drive each joint's filter below.
            return candidates, False
        length = max(12., np.linalg.norm(expected[1]-expected[0]))
        kept = []
        for candidate in candidates:
            axis = torso(candidate[1])
            if axis is not None and max(np.linalg.norm(a-b) for a,b in zip(axis, expected))/length < .85:
                kept.append(candidate)
        # A manual torso point only authorizes an unambiguous observed candidate.
        if 'pelvis' in manual and len(kept) != 1:
            return [], False
        return kept, 'pelvis' in manual

    def process(self, pose, index, frame=None):
        now = index/self.fps
        manual = self.anchors.get(index, {})
        image_points = self.image_tracker.update(frame,manual) if frame is not None else {}
        axis = torso(pose.landmarks) if pose.pose2d.person_bbox is not None else None
        if pose.pose2d.person_bbox is not None and all(n in image_points for n in ('pelvis','chest')):
            axis = image_points['pelvis'], image_points['chest']
        if axis is not None and 'pelvis' in manual:
            axis = np.array(manual['pelvis']), np.array(manual['chest'])
            self.history.clear()
            self.pending.clear()
            self.body = None
        if axis is None:
            self.image_tracker.reset_motion()
            self.pending.clear()
            for old in self.history.values():
                old['gap'] = True
            return {'frame_index': index, 'timestamp': now, 'torso': None,
                    'joints': {n: {'state': 'uncertain', 'xy': None, 'reason': 'torso_unavailable'}
                               for n in INDICES}}
        pelvis, chest = axis
        length = float(np.linalg.norm(chest-pelvis))
        if length < 12:
            return {'frame_index': index, 'timestamp': now, 'torso': None, 'joints': {}}
        if self.body is not None and now > self.body_time:
            speed = (pelvis-self.body[0])/(now-self.body_time)
            self.body_velocity = speed if np.linalg.norm(speed) < length*8 else np.zeros(2)
        self.body, self.body_time = axis, now
        up = (chest-pelvis)/length
        basis = np.column_stack((np.array([-up[1], up[0]]), up))*length
        inverse = np.linalg.inv(basis)
        result = {}
        for name, joint in INDICES.items():
            p = pose.landmarks[joint]
            measurement = np.array([p.image_x, p.image_y]) if p.valid else None
            old = self.history.get(name)
            reason = 'observed'
            predicted = None
            if old is not None:
                dt = now-old['time']
                predicted = old['local']+old['velocity']*min(dt, self.max_gap)
            if name in manual:
                measurement = np.array(manual[name], dtype=float)
                reason = 'manual'
            elif name in image_points:
                measurement = image_points[name]
                reason = 'image_tracked'
            elif name in self.image_tracker.bound:
                # A failed image track must not jump to the model's hair/cloth point.
                previous = self.image_tracker.last_verified[name]
                if measurement is not None and np.linalg.norm(measurement-previous)>max(12,length*.25):
                    measurement = None
            local = inverse@(measurement-pelvis) if measurement is not None else None
            suspicious = False
            if local is not None and reason not in ('manual','image_tracked'):
                residual = np.linalg.norm(local-predicted) if predicted is not None else 0.
                chain = CHAINS.get(name)
                geometry = False
                if chain and all(pose.landmarks[k].valid for k in chain):
                    coords = [np.array([pose.landmarks[k].image_x,pose.landmarks[k].image_y]) for k in chain]
                    geometry = sum(np.linalg.norm(a-b) for a,b in zip(coords,coords[1:])) > length*3
                # Speed alone cannot reject a fast sword swing: require another cue.
                suspicious = (residual > .65 and (geometry or min(p.visibility or 0,p.presence or 0)<.75)) or residual > 1.8
                if old is not None and old.get('manual') and residual > .45:
                    suspicious = True
                if geometry and residual > .35:
                    suspicious = True
            if measurement is not None and not suspicious:
                reacquiring = old is not None and old['gap']
                if reacquiring and reason not in ('manual','image_tracked'):
                    pending = self.pending.get(name)
                    if pending is None or index-pending[0] != 1 or np.linalg.norm(local-pending[1]) > .45:
                        self.pending[name] = (index, local)
                        measurement = None
                        reason = 'awaiting_second_observation'
                    else:
                        reason = 'reacquired'
                if measurement is not None:
                    velocity = np.zeros(2)
                    if old is not None and not old['gap'] and reason != 'manual' and now > old['time']:
                        velocity = (local-old['local'])/(now-old['time'])
                        norm = np.linalg.norm(velocity)
                        velocity *= min(1., 6/max(norm, 1e-9))
                    self.history[name] = {'time':now,'local':local,'velocity':velocity,
                                          'gap':False,'manual':reason=='manual'}
                    self.pending.pop(name, None)
                    if reason == 'reacquired' and name in self.image_tracker.bound:
                        self.image_tracker.points[name] = measurement.copy()
                        self.image_tracker.last_verified[name] = measurement.copy()
                    result[name] = {'state':reason,'xy':measurement.tolist(),'reason':reason}
                    continue
            if old is not None:
                old['gap'] = True
            if old is not None and now-old['time'] <= self.max_gap and predicted is not None:
                xy = pelvis+basis@predicted
                if 0 <= xy[0] < self.width and 0 <= xy[1] < self.height:
                    result[name] = {'state':'predicted','xy':xy.tolist(),
                                    'reason':'outlier_rejected' if suspicious else reason if reason != 'observed' else 'missing'}
                    continue
            result[name] = {'state':'uncertain','xy':None,
                            'reason':'outlier_rejected' if suspicious else 'gap_expired_or_no_anchor'}
        return {'frame_index':index,'timestamp':now,
                'torso': {'pelvis':pelvis.tolist(),'chest':chest.tolist()},'joints':result}


def draw_guidance(frame, data):
    import cv2
    axis = data['torso']
    if axis:
        cv2.line(frame,tuple(map(round,axis['pelvis'])),tuple(map(round,axis['chest'])),(255,255,0),3)
        for side in ('left','right'):
            for base, middle, end in [('chest','elbow','wrist'),('pelvis','knee','ankle')]:
                a, b = data['joints'][side+'_'+middle], data['joints'][side+'_'+end]
                if a['xy'] is not None and b['xy'] is not None:
                    color = (0,180,255) if 'predicted' in (a['state'],b['state']) else (0,240,0)
                    cv2.line(frame,tuple(map(round,a['xy'])),tuple(map(round,b['xy'])),color,2)
    for name, p in data['joints'].items():
        if p['xy'] is None:
            continue
        xy = tuple(map(round,p['xy']))
        color = (0,180,255) if p['state']=='predicted' else (255,100,255) if p['state']=='manual' else (0,240,0)
        cv2.circle(frame,xy,6,color,2)
        cv2.putText(frame,name+':'+p['state'],xy,cv2.FONT_HERSHEY_SIMPLEX,.32,color,1)
    cv2.putText(frame,'2D guidance | green=observed orange=predicted pink=manual',
                (8,48),cv2.FONT_HERSHEY_SIMPLEX,.38,(255,255,255),1)
    return frame
