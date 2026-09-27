"""Executes normalised actions against an input backend.

The backend is abstract so the loop runs unchanged in tests (``FakeInput``) and
on Windows (``pyautogui``/``pydirectinput``, added in Phase 2). A small settle
delay follows each action so the next screenshot reflects the result.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol

from operator_app.types import Action, ActionType


class InputBackend(Protocol):
    """Low-level input primitives. Coordinates are physical pixels."""

    def move(self, x: int, y: int) -> None: ...
    def click(self, x: int, y: int, button: str = "left", count: int = 1) -> None: ...
    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None: ...
    def type_text(self, text: str) -> None: ...
    def key(self, keys: str) -> None: ...
    def scroll(self, dx: int, dy: int) -> None: ...


class ExecutorError(Exception):
    pass


@dataclass
class FakeInput:
    """Records calls instead of touching a real desktop."""

    events: list[tuple] = field(default_factory=list)

    def move(self, x: int, y: int) -> None:
        self.events.append(("move", x, y))

    def click(self, x: int, y: int, button: str = "left", count: int = 1) -> None:
        self.events.append(("click", x, y, button, count))

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        self.events.append(("drag", x1, y1, x2, y2))

    def type_text(self, text: str) -> None:
        self.events.append(("type", text))

    def key(self, keys: str) -> None:
        self.events.append(("key", keys))

    def scroll(self, dx: int, dy: int) -> None:
        self.events.append(("scroll", dx, dy))


class Executor:
    """Turns :class:`Action`s into backend calls with a settle delay."""

    def __init__(
        self,
        backend: InputBackend,
        *,
        settle_delay: float = 0.4,
        sleep=time.sleep,
    ) -> None:
        self._backend = backend
        self._settle = settle_delay
        self._sleep = sleep

    def execute(self, action: Action) -> None:
        """Execute one action. Raises :class:`ExecutorError` on bad input."""
        t = action.type
        b = self._backend

        if t is ActionType.MOVE:
            self._require_xy(action)
            b.move(action.x, action.y)
        elif t is ActionType.CLICK:
            self._require_xy(action)
            b.click(action.x, action.y, "left", 1)
        elif t is ActionType.DOUBLE_CLICK:
            self._require_xy(action)
            b.click(action.x, action.y, "left", 2)
        elif t is ActionType.RIGHT_CLICK:
            self._require_xy(action)
            b.click(action.x, action.y, "right", 1)
        elif t is ActionType.DRAG:
            if None in (action.x, action.y, action.x2, action.y2):
                raise ExecutorError("drag requires x, y, x2, y2")
            b.drag(action.x, action.y, action.x2, action.y2)
        elif t is ActionType.TYPE:
            if action.text is None:
                raise ExecutorError("type requires text")
            b.type_text(action.text)
        elif t is ActionType.KEY:
            if not action.keys:
                raise ExecutorError("key requires keys")
            b.key(action.keys)
        elif t is ActionType.SCROLL:
            b.scroll(action.scroll_dx, action.scroll_dy)
        elif t is ActionType.WAIT:
            self._sleep(max(0.0, action.seconds))
            return  # no extra settle after an explicit wait
        elif t in (ActionType.SCREENSHOT, ActionType.NAVIGATE,
                   ActionType.GO_BACK, ActionType.GO_FORWARD):
            # SCREENSHOT is a no-op here (the loop always captures). NAVIGATE and
            # browser history are handled by the model in the browser environment;
            # on the desktop they arrive as key/click actions instead.
            return
        else:  # pragma: no cover - exhaustive
            raise ExecutorError(f"unknown action type {t!r}")

        if self._settle > 0:
            self._sleep(self._settle)

    @staticmethod
    def _require_xy(action: Action) -> None:
        if action.x is None or action.y is None:
            raise ExecutorError(f"{action.type.value} requires x and y")
