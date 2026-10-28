"""Manny hinge alignment: change axial rotations, preserve observed joint centers.

Pure math stays independent of Unreal so extension, missing evidence and fast
swing can be tested without running the editor. Quaternions use xyzw order.
"""
import math


def add(a,b):return tuple(x+y for x,y in zip(a,b))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def scale(a,s):return tuple(x*s for x in a)
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def length(a):return math.sqrt(dot(a,a))
def unit(a):
    n=length(a)
    if n<1e-10:raise ValueError('Degenerate alignment axis')
    return scale(a,1/n)
def inverse(q):return (-q[0],-q[1],-q[2],q[3])
def multiply(a,b):return (*add(add(scale(b[:3],a[3]),scale(a[:3],b[3])),cross(a[:3],b[:3])),a[3]*b[3]-dot(a[:3],b[:3]))
def rotate(q,v):return add(v,scale(cross(q[:3],add(cross(q[:3],v),scale(v,q[3]))),2))
def axis_rotation(axis,angle):return (*scale(unit(axis),math.sin(angle/2)),math.cos(angle/2))


def bounded_phase(values,limit):
    """Project offline phases onto a slew bound, distributing turns both ways."""
    values=list(values);corrections=[[0.,0.] for _ in range(len(values)-1)]
    for _ in range(600):
        change=0.
        for j,p in enumerate(corrections):
            a=values[j]+p[0];b=values[j+1]+p[1]
            excess=max(-limit,min(limit,b-a));middle=(a+b)/2
            na,nb=middle-excess/2,middle+excess/2
            p[0]=a-na;p[1]=b-nb
            change=max(change,abs(values[j]-na),abs(values[j+1]-nb))
            values[j]=na;values[j+1]=nb
        if change<1e-9:break
    # Finish with a feasible sequence even if the iterative projection hits its
    # budget on a long densely sampled clip.
    for j in range(1,len(values)):
        values[j]=max(values[j-1]-limit,min(values[j-1]+limit,values[j]))
    return values


def offline_hinge_rotations(rows,local_normal,bone,endpoint,names,fps):
    """Use both ends of low-bend spans to plan roll before a knee bends again.

    Solve phase in a parallel-transported frame; smoothing a correction relative
    to input twist would inherit that input's drift. No joint positions change.
    Degenerate geometry splits the solve, so missing evidence is never bridged.
    """
    result=[tuple(row[bone]['q']) for row in rows];start=0
    while start<len(rows):
        bases=[];axes=[];phases=[];weights=[];i=start;previous_phase=None
        while i<len(rows):
            row=rows[i];a,b,c=[row[name]['p'] for name in names]
            upper,lower=sub(b,a),sub(c,b)
            if min(length(upper),length(lower))<1e-6:break
            axis=unit(sub(row[endpoint]['p'],row[bone]['p']))
            base=transport(bases[-1],axes[-1],axis) if bases else unit(row[bone]['q'])
            bend=math.acos(max(-1.,min(1.,dot(unit(upper),unit(lower)))))
            plane=cross(upper,lower);weight=0.;phase=None
            if bend>math.radians(8) and length(plane)>1e-8:
                normal=unit(plane);current=rotate(base,local_normal)
                phase=math.atan2(dot(axis,cross(current,normal)),max(-1.,min(1.,dot(current,normal))))
                if previous_phase is not None:
                    phase+=2*math.pi*round((previous_phase-phase)/(2*math.pi))
                previous_phase=phase
                weight=min(1.,(bend-math.radians(8))/math.radians(12))**2
            bases.append(base);axes.append(axis);phases.append(phase);weights.append(weight);i+=1
        if bases:
            valid=[j for j,p in enumerate(phases) if p is not None]
            if valid:
                # Weighted least squares in continuous phase. Weak/straight knees
                # are connected between actual observations, with no causal lag.
                stiffness=(fps*.015)**2
                diag=[w+2*stiffness for w in weights]
                diag[0]-=stiffness;diag[-1]-=stiffness
                rhs=[w*(p or 0.) for w,p in zip(weights,phases)]
                for j in range(1,len(bases)):
                    ratio=-stiffness/diag[j-1]
                    diag[j]-=ratio*(-stiffness);rhs[j]-=ratio*rhs[j-1]
                solved=[0.]*len(bases);solved[-1]=rhs[-1]/diag[-1]
                for j in range(len(bases)-2,-1,-1):solved[j]=(rhs[j]+stiffness*solved[j+1])/diag[j]
                solved=bounded_phase(solved,math.radians(540)/fps)
                for j,phase in enumerate(solved):result[start+j]=unit(multiply(axis_rotation(axes[j],phase),bases[j]))
            # If no frame has bend evidence, keep the original rotations.
        start=i+1
    return result


def transport(q,old_axis,new_axis):
    """Preserve roll while following arbitrary fast positional swing exactly."""
    a,b=unit(old_axis),unit(new_axis);c=max(-1.,min(1.,dot(a,b)))
    if c<-1+1e-8:
        helper=(1.,0.,0.) if abs(a[0])<.9 else (0.,1.,0.)
        delta=axis_rotation(cross(a,helper),math.pi)
    else:delta=unit((*cross(a,b),1+c))
    return unit(multiply(delta,q))


class HingeAlignment:
    """Track a mesh's anatomical normal, not the drifting input axial correction.

Below 8 degrees there is no reliable knee plane. Use transported last rotation
there; regain plane evidence progressively at 8..20 degrees. Limit only added
axial motion, never the actual leg swing. Missing evidence resets state.
"""
    def __init__(self,local_normal,fps):
        if not math.isfinite(fps) or fps<=0:raise ValueError('Invalid alignment fps')
        self.local_normal=unit(local_normal);self.fps=fps;self.previous=None;self.axis=None

    def reset(self):self.previous=None;self.axis=None

    def solve(self,q,axis,plane_normal,bend):
        axis=unit(axis)
        reliable=plane_normal is not None and bend>math.radians(8)
        if self.previous is None:base=unit(q)
        else:base=transport(self.previous,self.axis,axis)
        step=0.
        if reliable:
            current=rotate(base,self.local_normal)
            current=unit(sub(current,scale(axis,dot(axis,current))))
            desired=unit(sub(plane_normal,scale(axis,dot(axis,plane_normal))))
            error=math.atan2(dot(axis,cross(current,desired)),max(-1.,min(1.,dot(current,desired))))
            confidence=min(1.,max(0.,(bend-math.radians(8))/math.radians(12)))
            if self.previous is None:step=error*confidence
            else:
                step=error*(1-math.exp(-confidence/(self.fps*.035)))
                limit=math.radians(360)/self.fps
                step=max(-limit,min(limit,step))
            base=unit(multiply(axis_rotation(axis,step),base))
        elif self.previous is None:
            # No evidence at the start: retain input. Do not invent a knee plane.
            base=unit(q)
        self.previous=base;self.axis=axis
        return base,step


def aligned_rotations(rows,reference,fps):
    """Return six local rotation/location tracks plus diagnostics; input immutable."""
    desired=[{name:tuple(t['q']) for name,t in row.items()} for row in rows]
    stats={}
    for side in ('l','r'):
        names=[f'{name}_{side}' for name in ('thigh','calf','foot')]
        a,b,c=[reference[name]['p'] for name in names]
        normal=unit(cross(sub(b,a),sub(c,b)))
        for bone,endpoint in zip(names[:2],names[1:]):
            local=rotate(inverse(reference[bone]['q']),normal)
            sequence=offline_hinge_rotations(rows,local,bone,endpoint,names,fps)
            errors_before=[];errors_after=[];steps=[]
            for i,row in enumerate(rows):
                a,b,c=[row[name]['p'] for name in names]
                upper,lower=sub(b,a),sub(c,b)
                if min(length(upper),length(lower))<1e-6:
                    continue
                bend=math.acos(max(-1.,min(1.,dot(unit(upper),unit(lower)))))
                plane=cross(upper,lower);plane=unit(plane) if length(plane)>1e-8 else None
                axis=unit(sub(row[endpoint]['p'],row[bone]['p']))
                result=sequence[i]
                desired[i][bone]=result
                if i:
                    old_axis=unit(sub(rows[i-1][endpoint]['p'],rows[i-1][bone]['p']))
                    prior=transport(sequence[i-1],old_axis,axis)
                    steps.append(math.degrees(2*math.acos(min(1.,abs(dot(prior,result))))))
                if plane is not None and bend>math.radians(15):
                    for q,values in ((row[bone]['q'],errors_before),(result,errors_after)):
                        values.append(math.degrees(math.acos(max(-1.,min(1.,dot(rotate(q,local),plane))))))
            stats[bone]={'reliable_frames':len(errors_before),
                         'before_mean_degrees':sum(errors_before)/max(1,len(errors_before)),
                         'after_mean_degrees':sum(errors_after)/max(1,len(errors_after)),
                         'max_axial_step_after_initial_degrees':max(steps,default=0.)}
    tracks={}
    for side in ('l','r'):
        for bone,parent in ((f'thigh_{side}','pelvis'),(f'calf_{side}',f'thigh_{side}'),(f'foot_{side}',f'calf_{side}')):
            rotations=[];positions=[]
            for i,row in enumerate(rows):
                parent_inv=inverse(desired[i][parent]);q=unit(multiply(parent_inv,desired[i][bone]))
                if rotations and dot(q,rotations[-1])<0:q=scale(q,-1)
                rotations.append(q)
                positions.append(rotate(parent_inv,sub(row[bone]['p'],row[parent]['p'])))
            tracks[bone]={'q':rotations,'p':positions}
    return tracks,stats


def correct_unreal_animation(clip,mesh):
    """Bake target-specific hinge correction into a newly created Manny sequence."""
    import unreal as u
    if clip.get_editor_property('skeleton')!=mesh.get_editor_property('skeleton'):
        raise ValueError('Manny alignment skeleton mismatch')
    source_fps=30.;fps=120.
    source_count=u.AnimationLibrary.get_num_frames(clip)+1
    duration=clip.get_editor_property('sequence_length')
    if source_count<2 or abs((source_count-1)/source_fps-duration)>1e-3:raise ValueError('Manny alignment expects 30 fps export')
    count=round(duration*fps)+1
    actor=u.EditorLevelLibrary.spawn_actor_from_class(u.SkeletalMeshActor,u.Vector())
    component=actor.skeletal_mesh_component;component.set_skeletal_mesh_asset(mesh)
    all_names=[str(component.get_bone_name(i)) for i in range(component.get_num_bones())]
    names=['root','pelvis']+[f'{b}_{s}' for s in ('l','r') for b in ('thigh','calf','foot','ball')]
    rows=[];baseline={b:{'p':[],'q':[],'s':[]} for b in all_names};options=u.AnimPoseEvaluationOptions()
    reference={}
    for i in range(count):
        pose=u.AnimPoseExtensions.get_anim_pose_at_time(clip,i/fps,options);row={}
        for bone in names:
            t=u.AnimPoseExtensions.get_bone_pose(pose,bone,u.AnimPoseSpaces.WORLD)
            row[bone]={'p':(t.translation.x,t.translation.y,t.translation.z),'q':(t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w)}
            if i==0:
                t=u.AnimPoseExtensions.get_ref_bone_pose(pose,bone,u.AnimPoseSpaces.WORLD)
                reference[bone]={'p':(t.translation.x,t.translation.y,t.translation.z),'q':(t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w)}
        for bone in all_names:
            local=u.AnimPoseExtensions.get_bone_pose(pose,bone,u.AnimPoseSpaces.LOCAL)
            baseline[bone]['p'].append(local.translation)
            baseline[bone]['q'].append(local.rotation)
            baseline[bone]['s'].append(local.scale3d)
        rows.append(row)
    tracks,stats=aligned_rotations(rows,reference,fps)
    controller=clip.controller
    controller.open_bracket('Bake dense Manny knee alignment',False)
    try:
        controller.set_frame_rate(u.FrameRate(numerator=120,denominator=1),False)
        controller.set_number_of_frames(u.FrameNumber(value=count-1),False)
        for bone,values in baseline.items():
            if bone in tracks:
                values['p']=[u.Vector(*v) for v in tracks[bone]['p']]
                values['q']=[u.Quat(*q) for q in tracks[bone]['q']]
            if not controller.set_bone_track_keys(bone,values['p'],values['q'],values['s'],False):
                raise RuntimeError('Cannot write Manny track '+bone)
    finally:controller.close_bracket(False)
    return {'method':'offline_knee_plane_transport_bounded_phase','fps':fps,'frames':count,'bones':stats,
            'source_fps':source_fps,'unreliable_plane':'interpolate_axial_phase_between_observations',
            'max_axial_speed_degrees_per_second':540,
            'limits':['not_ground_truth_twist','no_missing_pose_reconstruction','Manny_specific_reference_hinge']}
