"""Blender hand calibration: preserve target bind shape and transfer local bends."""
from mathutils import Matrix,Vector


def palm_frame(arm,wrist,index,middle,pinky):
    bones=arm.data.bones
    forward=(bones[middle].head_local-bones[wrist].head_local).normalized()
    lateral=bones[index].head_local-bones[pinky].head_local
    lateral=(lateral-forward*lateral.dot(forward)).normalized()
    normal=lateral.cross(forward).normalized()
    if min(forward.length,lateral.length,normal.length)<.99:raise ValueError('Degenerate palm calibration')
    return Matrix((lateral,forward,normal)).transposed()


def curl_axis(rest,palm,side):
    # Both reference palms curl toward -Z, despite mirrored palm frames.
    curl=rest.to_3x3().transposed()@(palm.col[2]*(-1 if side=='l' else 1))
    curl.y=0
    if curl.length<1e-6:raise ValueError('Finger axis parallel to palm normal')
    return curl.normalized()


def transfer_direction(source_quaternion,source_curl,target_curl):
    y=Vector((0,1,0));d=source_quaternion@y
    source_spread=source_curl.cross(y).normalized();target_spread=target_curl.cross(y).normalized()
    result=y*d.y+target_curl*d.dot(source_curl)+target_spread*d.dot(source_spread)
    return result.normalized()
