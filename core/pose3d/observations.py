"""Compact foreground support for pose-independent boxes and duplicate evidence."""

from dataclasses import dataclass

import cv2
import numpy as np

from core.pose2d.tracker import box_iou


@dataclass(frozen=True)
class MaskSupport:
    bbox: np.ndarray
    pixels: np.ndarray


def mask_support(values, width, height):
    values = np.asarray(values)
    if values.shape == (height, width, 1):
        values = values[:, :, 0]
    if values.shape != (height, width) or not np.isfinite(values).all():
        return None
    # Keep at most 256 pixels per side for bounded per-frame matching and CC memory.
    ratio = min(1., 256/max(width, height))
    small = cv2.resize(values, (max(1,round(width*ratio)), max(1,round(height*ratio))),
                       interpolation=cv2.INTER_AREA)
    binary = (small >= .5).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if count <= 1:
        return None
    component = 1+int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h, area = stats[component]
    if area < max(20,binary.size*.002) or area > binary.size*.85:
        return None
    sx, sy = width/binary.shape[1], height/binary.shape[0]
    low = np.asarray([x*sx,y*sy])
    high = np.asarray([(x+w)*sx,(y+h)*sy])
    padding = np.maximum((high-low)*.04,4.)
    box = np.r_[np.maximum(low-padding,0),np.minimum(high+padding,[width-1,height-1])]
    if min(box[2:]-box[:2]) < 8:
        return None
    return MaskSupport(box.astype(np.float32), labels == component)


def intersection_ratios(a, b):
    if a.pixels.shape != b.pixels.shape:
        return 0., 0., 0.
    area_a, area_b = np.count_nonzero(a.pixels), np.count_nonzero(b.pixels)
    intersection = np.count_nonzero(a.pixels & b.pixels)
    return (intersection/max(area_a+area_b-intersection,1),
            intersection/max(min(area_a,area_b),1), min(area_a,area_b)/max(area_a,area_b,1))


def same_foreground(a, b, previous):
    """Merge nested supports only with a unique, shared previous observation.

    Boxes alone and a single foreground mask cannot prove identity. Previously
    distinct bodies which overlap now remain ambiguous instead of being merged.
    """
    if a is None or b is None or not previous or box_iou(a.bbox,b.bbox) < .5:
        return False
    _, containment, ratio = intersection_ratios(a,b)
    if containment < .95 or ratio < .5:
        return False
    return shared_previous_observation(a,b,previous)


def shared_previous_observation(a,b,previous):
    if a is None or b is None:
        return False
    references_a = [i for i,p in enumerate(previous) if p is not None and intersection_ratios(a,p)[0] >= .2]
    references_b = [i for i,p in enumerate(previous) if p is not None and intersection_ratios(b,p)[0] >= .2]
    return len(references_a)==1 and references_a==references_b
