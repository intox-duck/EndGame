"""Normalised vocabulary shared across providers, executor, guard and GUI.

Every provider maps its own action names into :class:`Action`. The executor,
guard and logger only ever deal with this normalised form, so adding a provider
never touches anything downstream.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class ActionType(str, enum.Enum):
    """The full set of desktop actions Operator can perform."""

    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    MOVE = "move"
    DRAG = "drag"
    TYPE = "type"
    KEY = "key"            # single key or chord, e.g. "enter", "ctrl+s"
    SCROLL = "scroll"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    NAVIGATE = "navigate"  # browser-style: open a URL / address bar
    GO_BACK = "go_back"
    GO_FORWARD = "go_forward"


# Actions that move the pointer to a location and therefore carry coordinates.
_POSITIONAL = {
    ActionType.CLICK,
    ActionType.DOUBLE_CLICK,
    ActionType.RIGHT_CLICK,
    ActionType.MOVE,
    ActionType.DRAG,
    ActionType.SCROLL,
}


@dataclass(frozen=True)
class Action:
    """A single normalised action.

    Coordinates are stored in **physical screen pixels** once normalisation has
    run. Providers that emit normalised (0-999) coordinates must convert first
    via :mod:`operator.screen` before constructing an ``Action``.
    """

    type: ActionType
    # Physical-pixel coordinates. Optional for non-positional actions.
    x: int | None = None
    y: int | None = None
    # Drag target (physical pixels).
    x2: int | None = None
    y2: int | None = None
    # Text to type (TYPE) or URL (NAVIGATE).
    text: str | None = None
    # Key or chord for KEY, e.g. "enter" or "ctrl+s".
    keys: str | None = None
    # Scroll amount (positive = down / right) and direction.
    scroll_dx: int = 0
    scroll_dy: int = 0
    # Seconds to wait for WAIT.
    seconds: float = 0.0
    # Free-form provider extras kept for logging/debug.
    raw: dict[str, Any] = field(default_factory=dict)

    def is_positional(self) -> bool:
        return self.type in _POSITIONAL

    def summary(self) -> str:
        """A short human string used for the guard keyword match and the log."""
        parts = [self.type.value]
        if self.text:
            parts.append(repr(self.text[:80]))
        if self.keys:
            parts.append(self.keys)
        if self.x is not None:
            parts.append(f"@({self.x},{self.y})")
        return " ".join(parts)


class SafetyDecision(str, enum.Enum):
    """The model's own safety signal, normalised."""

    NONE = "none"
    REQUIRE_CONFIRMATION = "require_confirmation"
    BLOCK = "block"


@dataclass(frozen=True)
class SafetyFlag:
    """A safety signal attached to a step or an action by the provider."""

    decision: SafetyDecision
    explanation: str = ""
    # Identifies which action the flag applies to (index into Step.actions).
    action_index: int | None = None


@dataclass(frozen=True)
class Usage:
    """Token accounting for one model call."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cached_input_tokens + other.cached_input_tokens,
        )


@dataclass
class Step:
    """One turn from the provider: what to do next.

    ``actions`` are executed in order. ``done`` ends the loop. ``safety`` holds
    any confirmation requests the provider surfaced; the guard layer adds its
    own on top of these.
    """

    actions: list[Action] = field(default_factory=list)
    text: str = ""                       # model reasoning / narration
    done: bool = False
    usage: Usage = field(default_factory=Usage)
    safety: list[SafetyFlag] = field(default_factory=list)
    model: str = ""                      # the model that actually produced this
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    """The outcome of executing one action, fed back to the provider."""

    action: Action
    ok: bool = True
    error: str = ""
    # PNG bytes of the screenshot taken after the action (the model needs it).
    screenshot_png: bytes | None = None
    # Physical size of the screenshot, for coordinate context.
    width: int = 0
    height: int = 0
    # Set when the user approved a model safety-confirmation for this action, so
    # the provider can send the acknowledgement the API expects on the next turn.
    safety_acknowledged: bool = False
