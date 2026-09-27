from __future__ import annotations

from operator_app.guard import Guard, Verdict
from operator_app.types import Action, ActionType


def test_plain_click_allowed():
    g = Guard()
    d = g.evaluate(Action(type=ActionType.CLICK, x=1, y=1))
    assert d.verdict is Verdict.ALLOW


def test_typing_a_draft_is_allowed():
    # Posture: drafting is free. Typing prose does not trip the guard.
    g = Guard()
    d = g.evaluate(Action(type=ActionType.TYPE, text="Thanks, I'll take a look."))
    assert d.verdict is Verdict.ALLOW


def test_send_button_context_confirms():
    g = Guard()
    d = g.evaluate(Action(type=ActionType.CLICK, x=1, y=1),
                   context_text="Click the Send button")
    assert d.verdict is Verdict.CONFIRM
    assert "send" in d.reason.lower()


def test_delete_confirms():
    g = Guard()
    d = g.evaluate(Action(type=ActionType.CLICK, x=1, y=1), context_text="Delete row")
    assert d.needs_confirmation


def test_secret_typing_refused():
    g = Guard()
    d = g.evaluate(Action(type=ActionType.TYPE, text="password: hunter2"))
    assert d.verdict is Verdict.REFUSE


def test_card_number_refused():
    g = Guard()
    d = g.evaluate(Action(type=ActionType.TYPE, text="4111111111111111"))
    assert d.verdict is Verdict.REFUSE


def test_window_allowlist_blocks_other_windows():
    g = Guard(window_allowlist=("Notepad",))
    d = g.evaluate(Action(type=ActionType.CLICK, x=1, y=1), window_title="Excel")
    assert d.verdict is Verdict.CONFIRM


def test_window_allowlist_allows_listed():
    g = Guard(window_allowlist=("Notepad",))
    d = g.evaluate(Action(type=ActionType.CLICK, x=1, y=1),
                   window_title="operator-demo - Notepad")
    assert d.verdict is Verdict.ALLOW


def test_enter_in_compose_confirms():
    g = Guard()
    d = g.evaluate(Action(type=ActionType.KEY, keys="enter"),
                   context_text="focused on the reply compose box")
    assert d.needs_confirmation


def test_suffix_match_send_variants():
    g = Guard()
    for ctx in ("Sending now", "Submit form", "Posting update"):
        assert g.evaluate(Action(type=ActionType.CLICK, x=1, y=1),
                          context_text=ctx).needs_confirmation


def test_word_boundary_avoids_false_positive():
    # "respond" contains "post"? no. Make sure "compose" doesn't fire on "post".
    g = Guard()
    d = g.evaluate(Action(type=ActionType.CLICK, x=1, y=1),
                   context_text="opened the compose window")
    # compose alone is not a guarded keyword; should be allowed.
    assert d.verdict is Verdict.ALLOW
