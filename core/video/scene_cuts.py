"""Conservative hard-cut candidates. No target identity or pose inference."""
import cv2
import numpy as np


class SceneCutDetector:
    """One-frame lookahead rejects a single-frame flash returning to the old view."""

    def __init__(self):
        self.previous = None
        self.pending_previous = None
        self.pending = None
        self.count = 0

    @staticmethod
    def describe(frame):
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError('Expected a uint8 BGR frame.')
        small = cv2.resize(frame, (160, 240), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        histogram = cv2.calcHist([hsv], [0, 1, 2], None, [12, 8, 8],
                                 [0, 180, 0, 256, 0, 256])
        cv2.normalize(histogram, histogram, 1, 0, cv2.NORM_L1)
        return small.astype(np.float32) / 255, histogram

    @staticmethod
    def difference(a, b):
        delta = np.abs(a[0] - b[0]).mean(axis=2)
        return {'mean_pixel_difference': float(delta.mean()),
                'changed_fraction': float(np.mean(delta > .12)),
                'histogram_distance': float(cv2.compareHist(a[1], b[1], cv2.HISTCMP_BHATTACHARYYA))}

    def observe(self, frame, index):
        if index != self.count:
            raise ValueError('Scene frames must be consecutive from zero.')
        current = self.describe(frame)
        event = {'frame_index': index, 'cut': False, 'reason': 'initial' if index == 0 else 'continuous'}
        if self.previous is not None:
            scores = self.difference(self.previous, current)
            event.update(scores)
            event['cut'] = (scores['mean_pixel_difference'] >= .08
                            and scores['changed_fraction'] >= .20
                            and scores['histogram_distance'] >= .20)
            if event['cut']:
                event['reason'] = 'hard_cut_candidate'
            if self.pending['cut'] and event['cut'] and self.pending_previous is not None:
                returning = self.difference(self.pending_previous, current)
                if returning['mean_pixel_difference'] < .04 and returning['histogram_distance'] < .10:
                    self.pending['cut'] = event['cut'] = False
                    self.pending['reason'] = event['reason'] = 'single_frame_flash_suppressed'
        completed = self.pending
        self.pending_previous = self.previous
        self.previous = current
        self.pending = event
        self.count += 1
        return completed

    def finish(self):
        completed = self.pending
        self.pending = None
        return completed


class SceneTimeline:
    def __init__(self):
        self.index = 0

    def annotate(self, row, event):
        if row['frame_index'] != event['frame_index']:
            raise ValueError('Scene/tracking alignment differs.')
        if event['cut']:
            self.index += 1
        result = dict(row)
        result['tracking_segment'] = row.get('tracking_segment', 0) + self.index
        result['scene'] = dict(event, index=self.index, identity_verified=False)
        return result
