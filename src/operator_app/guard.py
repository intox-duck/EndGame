"""Operator's own safety layer, independent of the model's safety flags.

The guard decides, before an action runs, whether it must be confirmed by the
user, refused outright, or allowed. It is deliberately pure logic: no I/O, no
platform calls, so every rule is unit-tested. The kill switch and the actual
confirmation dialog live at the edges (GUI / hotkey listener) and consult this.

Posture (per the owner): drafting is free; the *send* boundary is gated. Typing a
reply into a compose box is allowed, but the action that submits it — send,
submit, post, message, etc. — pauses and asks.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import Protocol

from operator_app.types import Action, ActionType


class Verdict(str, enum.Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"     # pause, show the user, require explicit approval
    REFUSE = "refuse"       # never do this; hand control back


@dataclass(frozen=True)
class GuardDecision:
    verdict: Verdict
    reason: str = ""

    @property
    def needs_confirmation(self) -> bool:
        return self.verdict is Verdict.CONFIRM

    @property
    def refused(self) -> bool:
        return self.verdict is Verdict.REFUSE


# Patterns that strongly suggest a secret is being typed. If the *model* tries to
# type something matching these, we refuse and hand control back to the user.
_SECRET_PATTERNS = (
    re.compile(r"\b\d{13,19}\b"),                       # card-number-like
    re.compile(r"\b\d{3,4}\b\s*(cvv|cvc|security code)", re.I),
    re.compile(r"(password|passwd|pwd|secret|api[_-]?key|token)\s*[:=]", re.I),
)

# Words that, if they name the compose target, indicate a compose/reply box.
_COMPOSE_HINTS = ("compose", "reply", "new message", "to:", "message body")

# Foreground apps where Enter / Ctrl+Enter commonly SENDS. In these, an
# Enter-class keypress is confirmed even with no compose narration, because a
# terse model can send silently otherwise. Substring match on the window title.
_COMMS_WINDOW_HINTS = (
    "outlook", "teams", "slack", "gmail", "mail", "messeng", "whatsapp",
    "discord", "telegram", "webex", "zoom chat",
)

_ENTER_KEYS = ("enter", "return", "ctrl+enter", "cmd+enter", "alt+s")


class KillSwitch(Protocol):
    """Something the loop can poll to know the user hit the abort hotkey."""

    def aborted(self) -> bool: ...


@dataclass
class FlagKillSwitch:
    """A simple in-process kill switch (set by the GUI or hotkey listener)."""

    _aborted: bool = False

    def abort(self) -> None:
        self._aborted = True

    def reset(self) -> None:
        self._aborted = False

    def aborted(self) -> bool:
        return self._aborted


@dataclass
class Guard:
    """Evaluates actions against the safety rules.

    Parameters mirror config: ``confirm_keywords`` trigger a confirmation when
    they appear in the action's text/keys or in the on-screen context passed to
    :meth:`evaluate`; ``window_allowlist`` (if non-empty) restricts which
    foreground windows the agent may act in.
    """

    confirm_keywords: tuple[str, ...] = (
        "send", "submit", "post", "publish", "delete", "remove", "pay",
        "purchase", "confirm", "apply", "connect", "message", "inmail",
    )
    window_allowlist: tuple[str, ...] = ()
    confirm_typing_into_compose: bool = False  # posture: drafting is free

    def evaluate(
        self,
        action: Action,
        *,
        context_text: str = "",
        window_title: str = "",
    ) -> GuardDecision:
        """Decide what to do with ``action``.

        ``context_text`` is the model's narration and/or nearby on-screen text
        (e.g. the label of the button being clicked); ``window_title`` is the
        current foreground window.
        """
        # 1) Window allowlist (if configured) is a hard gate.
        if self.window_allowlist and window_title:
            if not any(a.lower() in window_title.lower() for a in self.window_allowlist):
                return GuardDecision(
                    Verdict.CONFIRM,
                    f"Foreground window {window_title!r} is not on the allowlist.",
                )

        # 2) Never type secrets.
        if action.type is ActionType.TYPE and action.text:
            for pat in _SECRET_PATTERNS:
                if pat.search(action.text):
                    return GuardDecision(
                        Verdict.REFUSE,
                        "Action would type something that looks like a password, "
                        "card number or secret. Handing control back to you.",
                    )

        haystack = " ".join(
            s for s in (action.summary(), action.text or "", action.keys or "",
                        context_text) if s
        ).lower()

        # 3) Confirm before any send/submit/delete/pay/message-style action.
        for kw in self.confirm_keywords:
            if _word_in(kw, haystack):
                return GuardDecision(
                    Verdict.CONFIRM,
                    f"Action matches guarded keyword {kw!r} — confirm before it runs.",
                )

        # 4) Optionally confirm typing into a compose box (off by default).
        if (
            self.confirm_typing_into_compose
            and action.type is ActionType.TYPE
            and any(h in haystack for h in _COMPOSE_HINTS)
        ):
            return GuardDecision(
                Verdict.CONFIRM, "Typing into a compose/reply box — confirm."
            )

        # 5) Enter / Ctrl+Enter can send. Confirm when either a compose box is in
        #    context OR the foreground app is a known comms client (where a terse
        #    model could otherwise send with no narration to match on).
        if action.type is ActionType.KEY and action.keys:
            keys = action.keys.replace(" ", "").lower()
            if keys in _ENTER_KEYS:
                in_compose = any(h in haystack for h in _COMPOSE_HINTS)
                in_comms = any(h in (window_title or "").lower()
                               for h in _COMMS_WINDOW_HINTS)
                if in_compose or in_comms:
                    return GuardDecision(
                        Verdict.CONFIRM,
                        "Enter/Ctrl+Enter may send a message here — confirm.",
                    )

        return GuardDecision(Verdict.ALLOW)


def _word_in(word: str, haystack: str) -> bool:
    """Whole-word-ish match so 'apply' doesn't fire on 'applying' spuriously.

    Uses a boundary on the left and allows common suffixes on the right, since the
    guarded verbs appear on buttons as 'Send', 'Submit', 'Delete', etc.
    """
    return re.search(rf"\b{re.escape(word)}\w{{0,3}}\b", haystack) is not None
