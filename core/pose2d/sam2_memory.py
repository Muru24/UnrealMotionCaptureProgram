"""Bound stored outputs for our single forward SAM2 pass, preserving its inputs."""


def trim_forward_memory(predictor, state, frame_index):
    # SAM2 reads num_maskmem strided frames and max_obj_ptrs recent pointers.
    # Keep a conservative extra window; conditioning frames are never evicted.
    history = max(32, predictor.num_maskmem * predictor.memory_temporal_stride_for_eval
                  + predictor.num_maskmem, predictor.max_obj_ptrs_in_encoder)
    cutoff = frame_index - history + 1
    removed = 0
    for obj in state['output_dict_per_obj'].values():
        outputs = obj['non_cond_frame_outputs']
        for index in list(outputs):
            if index < cutoff:
                del outputs[index]
                removed += 1
    return removed
