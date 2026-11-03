import pytest
from pianji.window_motion import WindowFade

def fixture(enabled=True):
    values=[];closed=[]
    fade=WindowFade(values.append,lambda:closed.append(True),enabled=enabled)
    fade.prepare()
    return fade,values,closed

def test_open_and_close_have_bounded_intermediate_values():
    fade,values,closed=fixture();assert values[-1]==0
    fade.reveal(0);fade.tick(.06);assert 0<values[-1]<1
    fade.tick(.25);assert values[-1]==1
    assert fade.request_close(.3) is False
    fade.tick(.36);assert 0<values[-1]<1 and not closed
    fade.tick(.6);assert values[-1]==0 and closed==[True]
    assert fade.request_close(.7) is True

def test_close_during_open_continues_at_presentation_opacity_once():
    fade,values,closed=fixture();fade.reveal(0);fade.tick(.04);current=values[-1]
    assert fade.request_close(.04) is False;assert values[-1]==current
    assert fade.request_close(.07) is False
    fade.reveal(.08) # a late load must not reopen a closing window
    fade.tick(.1);assert 0<=values[-1]<current
    fade.tick(.4);fade.tick(.5);assert closed==[True]

def test_reduce_motion_never_leaves_a_hidden_or_blocked_window():
    fade,values,closed=fixture(False);assert values[-1]==1
    fade.reveal(0);assert values[-1]==1
    assert fade.request_close(.1) is True and closed==[]

def test_close_before_loaded_has_no_timer_dependency():
    fade,values,closed=fixture();assert fade.request_close(0) is True
    fade.reveal(.1);assert values[-1]==0 and closed==[]
