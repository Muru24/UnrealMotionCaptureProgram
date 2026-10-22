"""Fixed-scale orthographic preview; no inferred global translation or smoothing."""

import cv2
import numpy as np

from .interface import CONNECTIONS33


def draw_landmarks(frame, pose):
    for a, b in CONNECTIONS33:
        p, q = pose.landmarks[a], pose.landmarks[b]
        if p.valid and q.valid:
            cv2.line(frame, (round(p.image_x), round(p.image_y)),
                     (round(q.image_x), round(q.image_y)), (0, 240, 0), 2, cv2.LINE_AA)
    for p in pose.landmarks:
        if p.valid:
            cv2.circle(frame, (round(p.image_x), round(p.image_y)), 3, (0, 140, 255), -1)
    state = pose.pose2d.tracking
    cv2.putText(frame, f'Target: {state.state} / {state.reason}', (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 220, 255), 1, cv2.LINE_AA)
    return frame


def render_preview(overlay, pose, frame_index, fps):
    canvas = np.full((720, 1280, 3), 24, np.uint8)
    h, w = overlay.shape[:2]
    scale = min(640 / w, 670 / h)
    view = cv2.resize(overlay, (round(w * scale), round(h * scale)))
    x, y = (640-view.shape[1])//2, 45+(670-view.shape[0])//2
    canvas[y:y+view.shape[0], x:x+view.shape[1]] = view
    cv2.putText(canvas, f'Frame {frame_index} | {frame_index/fps:.3f}s', (15, 25),
                cv2.FONT_HERSHEY_SIMPLEX, .6, (235, 235, 235), 1, cv2.LINE_AA)
    for row, (axis, label) in enumerate(((0, 'Native X/Y'), (2, 'Native Z/Y (depth)'))):
        top = row*360
        cv2.putText(canvas, label + ' | fixed 140 px/m', (655, top+25),
                    cv2.FONT_HERSHEY_SIMPLEX, .6, (235, 235, 235), 1, cv2.LINE_AA)
        origin = np.asarray([960., top+190.])
        cv2.line(canvas, (650, top+190), (1270, top+190), (60, 60, 60), 1)
        cv2.line(canvas, (960, top+45), (960, top+345), (60, 60, 60), 1)
        for a, b in CONNECTIONS33:
            p, q = pose.landmarks[a], pose.landmarks[b]
            if not p.valid or not q.valid:
                continue
            # Native Y is displayed downwards. Coordinates remain unchanged in JSON.
            u = origin + np.asarray([(p.x, p.y, p.z)[axis], p.y])*140
            v = origin + np.asarray([(q.x, q.y, q.z)[axis], q.y])*140
            # Clip to each view so extreme model predictions cannot overflow OpenCV ints.
            u = tuple(np.clip(u, -10000, 10000).astype(int))
            v = tuple(np.clip(v, -10000, 10000).astype(int))
            ok, u, v = cv2.clipLine((640, top+40, 640, 310), u, v)
            if ok:
                cv2.line(canvas, u, v, (50, 235, 90), 2, cv2.LINE_AA)
        good = sum(p.valid for p in pose.landmarks)
        cv2.putText(canvas, f'Valid joints: {good}/33 | hip-relative, no root motion',
                    (655, top+350), cv2.FONT_HERSHEY_SIMPLEX, .43,
                    (180, 180, 180), 1, cv2.LINE_AA)
    return canvas
