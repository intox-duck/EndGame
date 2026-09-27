from __future__ import annotations

import pytest

from operator_app.executor import Executor, ExecutorError, FakeInput
from operator_app.types import Action, ActionType


def make():
    fake = FakeInput()
    ex = Executor(fake, settle_delay=0, sleep=lambda *_: None)
    return fake, ex


def test_click_maps_to_backend():
    fake, ex = make()
    ex.execute(Action(type=ActionType.CLICK, x=10, y=20))
    assert fake.events == [("click", 10, 20, "left", 1)]


def test_double_and_right_click():
    fake, ex = make()
    ex.execute(Action(type=ActionType.DOUBLE_CLICK, x=1, y=2))
    ex.execute(Action(type=ActionType.RIGHT_CLICK, x=3, y=4))
    assert fake.events == [("click", 1, 2, "left", 2), ("click", 3, 4, "right", 1)]


def test_type_and_key():
    fake, ex = make()
    ex.execute(Action(type=ActionType.TYPE, text="hi"))
    ex.execute(Action(type=ActionType.KEY, keys="ctrl+s"))
    assert fake.events == [("type", "hi"), ("key", "ctrl+s")]


def test_drag_requires_all_coords():
    _, ex = make()
    with pytest.raises(ExecutorError):
        ex.execute(Action(type=ActionType.DRAG, x=1, y=2))


def test_scroll():
    fake, ex = make()
    ex.execute(Action(type=ActionType.SCROLL, scroll_dx=0, scroll_dy=-3))
    assert fake.events == [("scroll", 0, -3)]


def test_wait_sleeps_and_no_settle():
    slept = []
    fake = FakeInput()
    ex = Executor(fake, settle_delay=5, sleep=slept.append)
    ex.execute(Action(type=ActionType.WAIT, seconds=2))
    assert slept == [2]  # only the wait, not the settle delay


def test_click_missing_coords_raises():
    _, ex = make()
    with pytest.raises(ExecutorError):
        ex.execute(Action(type=ActionType.CLICK))


def test_screenshot_and_navigate_are_noops():
    fake, ex = make()
    ex.execute(Action(type=ActionType.SCREENSHOT))
    ex.execute(Action(type=ActionType.NAVIGATE, text="https://x"))
    assert fake.events == []


def test_settle_delay_after_action():
    slept = []
    fake = FakeInput()
    ex = Executor(fake, settle_delay=0.4, sleep=slept.append)
    ex.execute(Action(type=ActionType.CLICK, x=1, y=1))
    assert slept == [0.4]
