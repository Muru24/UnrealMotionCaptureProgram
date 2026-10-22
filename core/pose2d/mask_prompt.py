"""Accessory-reduced prompt is a hypothesis, never a visible-body ground truth."""
import numpy as np


def reduced_prompt(person,regions,min_remaining_fraction=.2):
    person=np.asarray(person,bool)
    if person.ndim!=2 or person.sum()<32:raise ValueError('Person prompt unavailable.')
    remove=np.zeros_like(person)
    used=[]
    for name,(mask,logit) in regions.items():
        mask=np.asarray(mask,bool)
        if mask.shape!=person.shape:raise ValueError('Accessory prompt dimensions differ.')
        if np.isfinite(logit) and logit>0:remove|=mask;used.append(name)
    reduced=person&~remove;fraction=float(reduced.sum()/person.sum())
    info={'accessories_used':used,'remaining_person_fraction':fraction,'visible_body_verified':False,
          'original_pixels_modified':False,'mask_embedding_score_is_not_accuracy_confidence':True}
    if reduced.sum()<32 or fraction<min_remaining_fraction or fraction>.98:
        return None,dict(info,status='insufficient_or_unchanged_prompt')
    return reduced,dict(info,status='accessory_reduced_hypothesis')
