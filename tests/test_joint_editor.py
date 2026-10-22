from app.joint_editor import swap_sides


def test_explicit_swap_keeps_torso_and_handles_partial_pairs():
    points={'pelvis':[1,2],'chest':[1,20],'left_wrist':[0,10],'right_wrist':[100,10],
            'left_knee':[0,30]}
    swapped=swap_sides(points)
    assert swapped['right_wrist']==[0,10] and swapped['left_wrist']==[100,10]
    assert swapped['right_knee']==[0,30] and 'left_knee' not in swapped
    assert swapped['pelvis']==[1,2] and swap_sides(swapped)==points
    swapped['pelvis'][0]=99
    assert points['pelvis']==[1,2]
