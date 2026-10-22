"""CPU rotation filtering, inferred stance locking and fixed-length two-link leg IK.

Contact-derived translation is a ground constraint estimate, not measured world motion.
"""
import copy,math
import numpy as np

REVISION=7


def unit(v):
    length=np.linalg.norm(v)
    return v/length if length>1e-9 else None


def slerp(a,b,t):
    a=np.asarray(a,float);b=np.asarray(b,float)
    a=a/np.linalg.norm(a);b=b/np.linalg.norm(b)
    dot=float(np.dot(a,b))
    if dot<0:b=-b;dot=-dot
    dot=min(1.,max(-1.,dot))
    if dot>.9995:
        q=a*(1-t)+b*t;return q/np.linalg.norm(q)
    angle=math.acos(dot)
    return (math.sin((1-t)*angle)*a+math.sin(t*angle)*b)/math.sin(angle)


def swing(a,b,previous=None):
    a=unit(a);b=unit(b);dot=float(np.clip(np.dot(a,b),-1,1))
    if dot<-1+1e-8:
        axis=None if previous is None else unit(previous[1:]-a*np.dot(previous[1:],a))
        if axis is None:
            helper=np.eye(3)[np.argmin(np.abs(a))];axis=unit(np.cross(a,helper))
        q=np.r_[0.,axis]
    else:
        q=np.r_[1+dot,np.cross(a,b)];q/=np.linalg.norm(q)
    if previous is not None and np.dot(previous,q)<0:q=-q
    return q


def rotate(q,v):
    return v+2*np.cross(q[1:],np.cross(q[1:],v)+q[0]*v)


def smooth_small_rotation_changes(values,fps,limits=(2,8)):
    """Symmetric small-curvature suppression; constant angular velocity is unchanged."""
    result=values.copy();stride=max(1,round(fps/30))
    for i in range(stride,len(values)-stride):
        midpoint=slerp(values[i-stride],values[i+stride],.5)
        deviation=2*math.acos(float(np.clip(abs(np.dot(values[i],midpoint)),0,1)))
        t=float(np.clip((deviation-math.radians(limits[0]))/math.radians(limits[1]-limits[0]),0,1))
        weight=.5*(1-t*t*(3-2*t))
        result[i]=slerp(values[i],midpoint,weight)
    return result


def smooth_quaternions(values,fps,*,small_change_degrees=(2,8)):
    """Reject isolated angular impulses, then strengthen low-speed zero-phase SLERP."""
    values=np.asarray(values,float).copy()
    if len(values)>2:
        original=values.copy()
        for i in range(1,len(values)-1):
            before,after=original[i-1],original[i+1]
            neighbor_angle=2*math.acos(float(np.clip(abs(np.dot(before,after)),0,1)))
            midpoint=slerp(before,after,.5)
            deviation=2*math.acos(float(np.clip(abs(np.dot(midpoint,original[i])),0,1)))
            if neighbor_angle<math.radians(6) and deviation>math.radians(12):values[i]=midpoint
    def pass_one(qs):
        result=[qs[0]]
        radius=max(1,round(.10*fps))
        steps=2*np.arccos(np.clip(np.abs(np.sum(qs[1:]*qs[:-1],axis=1)),0,1))
        path=np.r_[0.,np.cumsum(steps)]
        for i,q in enumerate(qs[1:],1):
            a=max(0,i-radius);b=min(len(qs)-1,i+radius)
            angle=2*math.acos(float(np.clip(abs(np.dot(qs[a],qs[b])),0,1)))
            coherence=min(1.,angle/max(1e-9,path[b]-path[a]))
            speed=angle*fps/max(1,b-a)*(.35+.65*coherence)
            cutoff=.9+min(17.1,max(0.,speed-.8)*2.)
            alpha=1-math.exp(-2*math.pi*cutoff/fps)
            result.append(slerp(result[-1],q,alpha))
        return np.asarray(result)
    filtered=pass_one(pass_one(values)[::-1])[::-1]
    return smooth_small_rotation_changes(filtered,fps,small_change_degrees)


def spans(mask,keys):
    start=None
    for i in range(len(mask)+1):
        if start is not None and (i==len(mask) or not mask[i] or keys[i]!=keys[i-1]):
            yield start,i;start=None
        if i<len(mask) and mask[i] and start is None:start=i


def leg_ik(hip,ankle,pole,l1,l2,previous=None,dt=None):
    delta=ankle-hip;d=float(np.linalg.norm(delta))
    if d<1e-7 or d>l1+l2+1e-6 or d<abs(l1-l2)-1e-6:return None,None
    axis=delta/d;side=unit(pole-hip-axis*np.dot(pole-hip,axis))
    if side is None and previous is not None:side=unit(previous-axis*np.dot(previous,axis))
    if side is None:
        helper=np.array([0.,-1.,0.]);side=unit(helper-axis*np.dot(helper,axis))
    if side is None:side=unit(np.cross(axis,[1.,0.,0.]))
    if previous is not None and np.dot(side,previous)<0:side=-side
    if previous is not None and dt is not None:
        old=unit(previous-axis*np.dot(previous,axis))
        if old is not None:
            angle=math.acos(float(np.clip(np.dot(old,side),-1,1)))
            alpha=1-math.exp(-dt/(.025 if angle>.8 else .10))
            side=unit(old*(1-alpha)+side*alpha)
    a=(l1*l1-l2*l2+d*d)/(2*d);h=math.sqrt(max(0.,l1*l1-a*a))
    return hip+axis*a+side*h,side


def image_ground_support(q,valid,feet,index,contacts,keys,video,evidence,cancelled):
    """Recover vertical support for bilateral crouches; never infer an XY lock."""
    support=np.zeros_like(contacts)
    if evidence is None:return support
    pixels=np.asarray(evidence,float);height=float(video.get('height',0));width=float(video.get('width',0))
    if pixels.shape!=(len(q),5,2) or not height>0 or not width>0:raise ValueError('Invalid ground image evidence.')
    finite=np.isfinite(pixels).all(axis=(1,2))
    inside=finite&(pixels[:,:,0]>=0).all(axis=1)&(pixels[:,:,0]<width).all(axis=1)&(pixels[:,:,1]>=0).all(axis=1)&(pixels[:,:,1]<height).all(axis=1)
    for a,b in spans(valid[:,index['pelvis']]&inside,keys):
        if cancelled():raise KeyboardInterrupt
        seeds=contacts[a:b].all(axis=1)
        if np.count_nonzero(seeds)<max(3,math.ceil(.1*float(video['fps']))):continue
        reference=np.median(pixels[a:b][seeds],axis=0)
        smoothed=pixels[a:b].copy()
        for i in range(b-a):smoothed[i]=np.median(pixels[max(a,a+i-2):min(b,a+i+3)],axis=0)
        ground=np.ones(b-a,bool);bent=np.ones(b-a,bool)
        for s,(hip,knee,ankle,toe) in enumerate(feet):
            ground &= (smoothed[:,s,1]>=reference[s,1]-.03*height)&(smoothed[:,s+2,1]>=reference[s+2,1]-.03*height)
            ground &= (smoothed[:,s,1]<=reference[s,1]+.12*height)&(smoothed[:,s+2,1]<=reference[s+2,1]+.12*height)
            u=q[a:b,hip]-q[a:b,knee];v=q[a:b,ankle]-q[a:b,knee]
            cosine=np.sum(u*v,axis=1)/np.maximum(1e-9,np.linalg.norm(u,axis=1)*np.linalg.norm(v,axis=1))
            bent &= valid[a:b,[hip,knee,ankle,toe]].all(axis=1)&(cosine>math.cos(math.radians(150)))
        # Hip descent relative to the feet rejects pure camera translation and straight-leg hops.
        gap=(smoothed[:,:2,1].mean(axis=1)-smoothed[:,4,1])
        reference_gap=reference[:2,1].mean()-reference[4,1]
        candidate=ground&bent&(gap<reference_gap-.035*height)
        for c,d in spans(candidate,keys[a:b]):
            if d-c>=max(3,math.ceil(.1*float(video['fps']))):support[a+c:a+d]=True
    return support


def prepare_motion(data,cancelled=lambda:False,*,ground_evidence=None,root_observations=None):
    if data.get('schema')!='standard_motion_positions_v1':raise ValueError('Expected standard motion positions.')
    result=copy.deepcopy(data);rows=result['frames'];spec=result['skeleton']['bones']
    names=[b['name'] for b in spec];index={n:i for i,n in enumerate(names)};fps=float(result['video']['fps'])
    if len(names)!=22 or not 0<len(rows)<=18000 or not math.isfinite(fps) or not 1<=fps<=240:
        raise ValueError('Invalid correction timeline or skeleton.')
    rest=np.asarray([b['head'] for b in spec],float)
    q=np.asarray([[[np.nan]*3 if p is None else p for p in row['positions']] for row in rows],float)
    if q.shape!=(len(rows),22,3) or np.isinf(q).any():raise ValueError('Invalid correction positions.')
    valid=np.isfinite(q).all(axis=2);source=q.copy()
    keys=[(r.get('tracking_segment',0),r.get('scene_index',0)) for r in rows]
    if any(r['frame_index']!=i for i,r in enumerate(rows)):raise ValueError('Correction frame order differs.')
    for j,bone in enumerate(spec):
        if cancelled():raise KeyboardInterrupt
        if bone['parent'] is None or bone['name']=='pelvis':continue
        p=index[bone['parent']];edge=rest[j]-rest[p];length=np.linalg.norm(edge)
        if length<1e-7:raise ValueError('Degenerate reference edge.')
        observed=source[:,j]-source[:,p];mask=valid[:,j]&valid[:,p]&(np.linalg.norm(observed,axis=1)>1e-7)
        for a,b in spans(mask,keys):
            quats=[];previous=None
            for direction in observed[a:b]:
                previous=swing(edge,direction,previous);quats.append(previous)
            limits=(1,5) if bone['name'].startswith(('thigh_','calf_','foot_','ball_')) else (2,8)
            filtered=smooth_quaternions(np.array(quats),fps,small_change_degrees=limits)
            for k,rotation in enumerate(filtered,a):q[k,j]=q[k,p]+rotate(rotation,edge)
    # Infer contact only within uninterrupted observed segments. No missing joints are filled.
    contacts=np.zeros((len(rows),2),bool);feet=[]
    for side in ('l','r'):feet.append(tuple(index[f'{n}_{side}'] for n in ('thigh','calf','foot','ball')))
    for a,b in spans(valid[:,index['pelvis']],keys):
        for s,(_,_,ankle,toe) in enumerate(feet):
            hip,knee=feet[s][:2];observed=valid[a:b,[hip,knee,ankle,toe]].all(axis=1)
            height=np.minimum(q[a:b,ankle,2],q[a:b,toe,2])
            if not observed.any():continue
            baseline=float(np.percentile(height[observed],20))
            speed=np.zeros(b-a)
            if b-a>1:speed[1:]=np.abs(np.diff(height))*fps;speed[0]=speed[1]
            candidate=observed&(height<=baseline+.07)&(speed<.65)
            for c,d in spans(candidate,keys[a:b]):
                if d-c>=max(2,math.ceil(.08*fps)):contacts[a+c:a+d,s]=True
    image_support=image_ground_support(q,valid,feet,index,contacts,keys,result['video'],ground_evidence,cancelled)
    from core.motion.root_motion import trajectory_hints
    drive,airborne,air_height,moving_support=trajectory_hints(q,valid,feet,index,contacts,keys,result['video'],root_observations,spans)
    image_support|=moving_support&contacts
    contacts[moving_support]=False
    contacts[airborne]=False;image_support[airborne]=False
    root=np.zeros(3);anchors={};poles={};last=None;reports=[]
    previous_feet={};previous_states={};release_offsets={};landing=set()
    image_root_base=None
    drive_offset=None;drive_epoch=None;air_root_base=None
    for i,row in enumerate(rows):
        if cancelled():raise KeyboardInterrupt
        continuous=i>0 and keys[i]==last and valid[i-1,index['pelvis']] and valid[i,index['pelvis']]
        if keys[i]!=last or not valid[i,index['pelvis']]:
            root=np.zeros(3);anchors={};poles={};previous_feet={};previous_states={};release_offsets={};landing=set()
            image_root_base=None
            drive_offset=None;drive_epoch=None;air_root_base=None
        last=keys[i];states=[]
        driven=np.isfinite(drive[i]).all()
        if driven:
            epoch=root_observations['epochs'][i]
            if drive_offset is None or drive_epoch!=epoch:drive_offset=root[:2]-drive[i,:2]
            else:
                delta=(drive_offset+drive[i,:2]-root[:2])*(1-math.exp(-1/(fps*.09)))
                delta[0]=float(np.clip(delta[0],-2.5/fps,2.5/fps));delta[1]=float(np.clip(delta[1],-1.2/fps,1.2/fps))
                root[:2]+=delta
            drive_epoch=epoch
        else:drive_offset=None;drive_epoch=None
        if airborne[i] and air_root_base is None:air_root_base=float(root[2])
        if not airborne[i] and air_root_base is not None:
            if abs(root[2]-air_root_base)>.03:
                contacts[i]=False;image_support[i]=False
                root[2]+=float(np.clip(air_root_base-root[2],-3./fps,3./fps))
            else:air_root_base=None
        for s in list(anchors):
            if not contacts[i,s]:anchors.pop(s)
        shifts=[]
        for s,(_,_,ankle,_) in enumerate(feet):
            if contacts[i,s] and s in anchors:shifts.append(anchors[s]-q[i,ankle])
        if shifts:
            proposal=np.mean(shifts,axis=0)
            delta=(proposal[:2]-root[:2])*(1-math.exp(-1/(fps*.045)))
            distance=np.linalg.norm(delta);limit=1.8/fps
            root[:2]+=delta*min(1.,limit/max(distance,1e-9))
        supported=[s for s in range(2) if contacts[i,s] or image_support[i,s]]
        if image_support[i].any():
            if image_root_base is None:image_root_base=float(root[2])
        elif image_root_base is not None:
            if not supported:
                root[2]+=float(np.clip(image_root_base-root[2],-1.2/fps,1.2/fps))
            if supported or abs(root[2]-image_root_base)<1e-5:image_root_base=None
        if airborne[i]:
            root[2]+=float(np.clip(air_height[i]-root[2],-3./fps,3./fps))
            clearance=max(max(.07-q[i,ankle,2],.03-q[i,toe,2]) for _,_,ankle,toe in feet)
            root[2]=max(root[2],clearance+.015)
            anchors={};poles={};previous_feet={};previous_states={};release_offsets={};landing=set()
        elif supported:
            height=float(np.mean([.07-q[i,feet[s][2],2] for s in supported]))
            root[2]=root[2]+float(np.clip((1-math.exp(-1/(fps*.05)))*(height-root[2]),-1.2/fps,1.2/fps)) if continuous else height
            # Lower the pelvis when necessary rather than stretch a planted leg.
            for s in supported:
                hip,knee,ankle,toe=feet[s];l1=np.linalg.norm(rest[knee]-rest[hip]);l2=np.linalg.norm(rest[ankle]-rest[knee])
                target=anchors.get(s,q[i,ankle]+root).copy();target[2]=.07
                horizontal=np.linalg.norm(target[:2]-(q[i,hip,:2]+root[:2]))
                if horizontal<l1+l2:
                    root[2]=min(root[2],.07+math.sqrt(max(0.,(l1+l2-1e-5)**2-horizontal**2))-q[i,hip,2])
        for j in range(1,22):
            if valid[i,j]:q[i,j]+=root
        if valid[i,0]:q[i,0]=[root[0],root[1],max(0.,root[2]-(air_root_base or 0.)) if air_root_base is not None else 0.]
        for s,(hip,knee,ankle,toe) in enumerate(feet):
            state='missing' if not valid[i,[hip,knee,ankle,toe]].all() else 'swing'
            if state!='missing' and contacts[i,s]:
                target=anchors.get(s,q[i,ankle].copy()).copy();target[2]=.07
                l1=np.linalg.norm(rest[knee]-rest[hip]);l2=np.linalg.norm(rest[ankle]-rest[knee])
                bend,pole=leg_ik(q[i,hip],target,q[i,knee],l1,l2,poles.get(s),1/fps)
                if bend is not None:
                    direction=unit(np.r_[q[i,toe,:2]-q[i,ankle,:2],0.])
                    if direction is None:direction=np.array([0.,-1.,0.])
                    length=np.linalg.norm(rest[toe]-rest[ankle]);horizontal=math.sqrt(max(0.,length*length-.04**2))
                    q[i,knee]=bend;q[i,ankle]=target;q[i,toe]=target+direction*horizontal;q[i,toe,2]=.03
                    anchors[s]=target.copy();poles[s]=pole;state='inferred_contact'
                else:contacts[i,s]=False;anchors.pop(s,None);state='unreachable_contact_released'
            elif not image_support[i,s]:poles.pop(s,None)
            if state!='missing' and state!='inferred_contact' and not airborne[i] and (image_support[i,s] or q[i,ankle,2]<.07 or q[i,toe,2]<.03):
                target=q[i,ankle].copy();target[2]=max(.07,target[2])
                if image_support[i,s]:target[2]=.07
                l1=np.linalg.norm(rest[knee]-rest[hip]);l2=np.linalg.norm(rest[ankle]-rest[knee])
                bend,pole=leg_ik(q[i,hip],target,q[i,knee],l1,l2,poles.get(s),1/fps)
                if bend is not None:
                    direction=unit(np.r_[q[i,toe,:2]-q[i,ankle,:2],0.])
                    if direction is None:direction=np.array([0.,-1.,0.])
                    length=np.linalg.norm(rest[toe]-rest[ankle]);horizontal=math.sqrt(max(0.,length*length-.04**2))
                    q[i,knee]=bend;q[i,ankle]=target;q[i,toe]=target+direction*horizontal;q[i,toe,2]=target[2]-.04
                    poles[s]=pole;state='inferred_ground_support' if image_support[i,s] else 'ground_collision'
                else:state='unresolved_ground_collision'
            if state=='missing':
                previous_feet.pop(s,None);previous_states.pop(s,None);release_offsets.pop(s,None);landing.discard(s)
            else:
                is_contact=state=='inferred_contact'
                constrained=state in ('inferred_contact','ground_collision','inferred_ground_support')
                was_contact=previous_states.get(s) in ('inferred_contact','contact_transition')
                was_constrained=previous_states.get(s) in ('inferred_contact','contact_transition','ground_collision','collision_transition','inferred_ground_support')
                if s in previous_feet:
                    if (is_contact and not was_contact) or (state in ('ground_collision','inferred_ground_support') and not was_constrained and s not in release_offsets):
                        landing.add(s);release_offsets.pop(s,None)
                    if (not is_contact and was_contact) or (not constrained and was_constrained):
                        release_offsets[s]=previous_feet[s]-q[i,ankle];landing.discard(s)
                    target=q[i,ankle].copy();transition=False
                    if constrained and s in landing:
                        delta=target-previous_feet[s];distance=np.linalg.norm(delta)
                        if distance>3./fps:
                            target=previous_feet[s]+delta*(3./fps/distance);transition=True
                            state='contact_transition' if state=='inferred_contact' else 'collision_transition'
                        else:landing.discard(s)
                    elif not is_contact and s in release_offsets:
                        offset=release_offsets[s];distance=np.linalg.norm(offset)
                        # Fade the constraint offset, without clamping genuine source swing velocity.
                        if was_contact:transition=True
                        else:offset=offset*max(0.,1.-3./fps/max(distance,1e-9))
                        release_offsets[s]=offset;target+=offset
                        transition=transition or np.linalg.norm(offset)>.001
                        if transition:state='release_blend'
                        else:release_offsets.pop(s,None)
                    if transition:
                        l1=np.linalg.norm(rest[knee]-rest[hip]);l2=np.linalg.norm(rest[ankle]-rest[knee])
                        target[2]=max(.07,target[2],q[i,hip,2]-(l1+l2-1e-5))
                        horizontal=target[:2]-q[i,hip,:2]
                        radius=math.sqrt(max(0.,(l1+l2-1e-5)**2-(target[2]-q[i,hip,2])**2))
                        norm=np.linalg.norm(horizontal)
                        if norm>radius:target[:2]=q[i,hip,:2]+horizontal*(radius/max(norm,1e-9))
                        bend,pole=leg_ik(q[i,hip],target,q[i,knee],l1,l2,poles.get(s),1/fps)
                        if bend is not None:
                            toe_offset=q[i,toe]-q[i,ankle]
                            q[i,knee]=bend;q[i,ankle]=target;q[i,toe]=target+toe_offset;poles[s]=pole
                            if q[i,toe,2]<.03:
                                direction=unit(np.r_[toe_offset[:2],0.])
                                if direction is None:direction=np.array([0.,-1.,0.])
                                length=np.linalg.norm(rest[toe]-rest[ankle]);dz=.03-target[2]
                                dz=max(-length,min(length,dz))
                                q[i,toe]=target+direction*math.sqrt(max(0.,length*length-dz*dz));q[i,toe,2]=target[2]+dz
                previous_feet[s]=q[i,ankle].copy();previous_states[s]=state
            states.append('estimated_airborne' if airborne[i] and state!='missing' else state)
        row['positions']=[q[i,j].tolist() if valid[i,j] else None for j in range(22)]
        reports.append({'frame_index':i,'feet':states,'image_ground_support':image_support[i].tolist(),'image_moving_support':moving_support[i].tolist(),
                        'image_root_drive':bool(driven),'estimated_airborne':bool(airborne[i]),'root_offset_m':root.tolist() if valid[i,index['pelvis']] else None})
    image_driven=bool(np.isfinite(drive).all(axis=1).any())
    result['root_motion']=True;result['root_motion_kind']='image_and_contact_estimate' if image_driven else 'contact_constraint_estimate'
    result['correction']={'revision':REVISION,'rotation_filter':'adaptive_bidirectional_shortest_arc_quaternion_slerp',
        'constraint_offset_release_speed_mps':3.,'root_xy_soft_speed_limit_mps':1.8,'root_z_soft_speed_limit_mps':1.2,
        'cutoff_hz':[.9,18],'motion_coherence_weighting':True,'isolated_impulse_degrees':12,'ik_pole_smoothing_seconds':.10,
        'small_rotation_curvature_degrees':[2,8],'small_rotation_smoothing_seconds':1/30,
        'leg_small_rotation_curvature_degrees':[1,5],
        'ground_z_m':0.,'ankle_contact_z_m':.07,'toe_contact_z_m':.03,
        'contact_is_estimated':True,'root_translation':result['root_motion_kind']+'_not_measured_world_motion',
        'image_ground_evidence_used':ground_evidence is not None,'crouch_support':'bilateral_bent_legs_and_image_floor_proximity_vertical_only',
        'image_root_observations_used':image_driven,'root_depth_is_model_estimate':image_driven,
        'limits':['no_ground_truth_contact_or_camera_motion','no_missing_joint_recovery','not_calibrated_world_trajectory',
                  'sole_height_reference_proxy_not_real_shoe_geometry','not_anatomical_joint_limit_solver','image_floor_is_model_projection_not_calibrated_ground'],
        'frames':reports}
    return result
