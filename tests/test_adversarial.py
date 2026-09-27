"""Adversarial checks: hostile / malformed input against every component.

These are attacks, not happy paths. Assumes gemini-3.8-flash. Where a test
documents an *inherent* limitation (e.g. the guard can't read a non-English Send
button), it asserts the current behaviour and is annotated so the gap is visible
rather than silent.
"""

from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from operator_app.config import Config
from operator_app.guard import Guard, Verdict
from operator_app.providers.gemini import GeminiProvider
from operator_app.screen.base import ScreenGeometry, model_to_physical
from operator_app.types import Action, ActionType


# --------------------------------------------------------------------------- #
# Gemini adapter — Flash output is UNTRUSTED. It must never crash the run.
# --------------------------------------------------------------------------- #

class _Models:
    def list(self):
        return [NS(name="gemini-3.8-flash"), NS(name="gemini-3.5-flash")]

    def generate_content(self, **kw):
        raise AssertionError("not used")


class _Client:
    models = _Models()


def _prov(geometry=ScreenGeometry(1920, 1080)):
    return GeminiProvider(config=Config(), client=_Client(),
                          active_model="gemini-3.8-flash", geometry=geometry)


@pytest.mark.parametrize("args", [
    {},                                          # no coords at all
    {"x": None, "y": None},
    {"x": "500", "y": "600"},                    # string coords
    {"x": -9999, "y": 999999},                   # wildly out of range
    {"x": 1e18, "y": -1e18},                      # absurd magnitudes
    {"coordinate": [1, 2, 3]},                    # over-long vector
    {"coordinate": "not-a-list"},                # wrong type
    {"x": float("nan"), "y": float("inf")},      # nan / inf
])
def test_click_never_crashes_on_bad_coords(args):
    p = _prov()
    action, flag = p._to_action(NS(name="click_at", args=args, id="1"), 0)
    # Either it produced a clamped in-range action or a None (skipped); never raise.
    if action is not None and action.x is not None:
        assert 0 <= action.x <= 1919
        assert 0 <= action.y <= 1079


def test_type_with_non_string_text():
    p = _prov()
    action, _ = p._to_action(NS(name="type_text_at", args={"text": 12345}, id="1"), 0)
    assert action.type is ActionType.TYPE
    assert isinstance(action.text, str)


def test_key_with_weird_types():
    p = _prov()
    action, _ = p._to_action(NS(name="key_combination", args={"keys": None}, id="1"), 0)
    assert action.keys == ""


def test_missing_name_and_args():
    p = _prov()
    action, flag = p._to_action(NS(name=None, args=None, id=None), 0)
    assert action is None  # unknown -> skipped with a flag
    assert flag is not None


def test_geometry_none_does_not_crash():
    p = GeminiProvider(config=Config(), client=_Client(),
                       active_model="gemini-3.8-flash", geometry=None)
    action, _ = p._to_action(NS(name="click_at", args={"x": 5, "y": 5}, id="1"), 0)
    # With no geometry we can't convert coords, but it must not raise.
    assert action.type is ActionType.CLICK


def test_scroll_absurd_magnitude():
    p = _prov()
    action, _ = p._to_action(NS(name="scroll", args={"magnitude": 10**9,
                                                     "direction": "down"}, id="1"), 0)
    assert isinstance(action.scroll_dy, int)


def test_parse_response_with_no_candidates():
    p = _prov()
    step = p._parse_response(NS(candidates=[], usage_metadata=None))
    assert step.done is True


def test_parse_response_with_none_parts():
    p = _prov()
    resp = NS(candidates=[NS(content=NS(parts=None))], usage_metadata=None)
    step = p._parse_response(resp)
    assert step.done is True


# --------------------------------------------------------------------------- #
# Guard — the safety backstop. Try to slip a dangerous action past it.
# --------------------------------------------------------------------------- #

def test_guard_case_insensitive_send():
    g = Guard()
    for ctx in ("SEND", "Send", "sEnD", "click SEND now"):
        assert g.evaluate(Action(type=ActionType.CLICK, x=1, y=1),
                          context_text=ctx).needs_confirmation


def test_guard_secret_variants():
    g = Guard()
    # These SHOULD be refused.
    caught = [
        "password: hunter2",
        "API_KEY=sk-abc",
        "4111 1111 1111 1111".replace(" ", ""),  # 16-digit card
    ]
    for t in caught:
        assert g.evaluate(Action(type=ActionType.TYPE, text=t)).verdict is Verdict.REFUSE


def test_guard_secret_evasion_documented():
    """LIMITATION: free-form secrets with no keyword/format are NOT caught.

    The guard catches labelled secrets and card-shaped numbers, not an arbitrary
    passphrase typed as prose. This asserts the current (permissive) behaviour so
    the gap is explicit. Mitigation: the model is instructed never to type secrets,
    and the user watches the live log.
    """
    g = Guard()
    d = g.evaluate(Action(type=ActionType.TYPE, text="correct horse battery staple"))
    assert d.verdict is Verdict.ALLOW  # not caught — known limitation


def test_guard_non_english_send_partial_coverage():
    """LIMITATION: non-English Send labels are caught only by accident.

    Keyword matching is English with a small suffix allowance, so German 'Senden'
    happens to match the 'send' stem — but languages that don't share the stem
    ('Envoyer', 'Enviar', 'Invia') are NOT caught from the label alone. Mitigation:
    add locale words to confirm_keywords (see next test) and/or use
    window_allowlist. Asserted so the real, partial coverage is explicit.
    """
    g = Guard()
    # Accidentally caught (shares the English stem):
    assert g.evaluate(Action(type=ActionType.CLICK, x=1, y=1),
                      context_text="Senden").needs_confirmation
    # NOT caught — genuine gap:
    for label in ("Envoyer", "Enviar", "Invia", "送信"):
        assert g.evaluate(Action(type=ActionType.CLICK, x=1, y=1),
                          context_text=label).verdict is Verdict.ALLOW


def test_guard_locale_keyword_configurable():
    # The mitigation works: add the locale word and it's caught.
    g = Guard(confirm_keywords=Guard().confirm_keywords + ("senden", "envoyer"))
    assert g.evaluate(Action(type=ActionType.CLICK, x=1, y=1),
                      context_text="Senden").needs_confirmation


def test_guard_allowlist_empty_title_still_evaluates():
    g = Guard(window_allowlist=("Notepad",))
    # No window title known -> allowlist can't confirm the window; other rules apply.
    d = g.evaluate(Action(type=ActionType.CLICK, x=1, y=1), window_title="")
    assert d.verdict is Verdict.ALLOW


def test_guard_newline_injection_in_text():
    g = Guard()
    d = g.evaluate(Action(type=ActionType.TYPE,
                          text="hello\nplease click send now\nbye"))
    # 'send' appears in typed text -> confirm (typing that text is benign, but
    # erring toward confirmation is the safe direction).
    assert d.needs_confirmation


# --------------------------------------------------------------------------- #
# Screen coordinate maths — boundary abuse.
# --------------------------------------------------------------------------- #

def test_degenerate_geometry_clamps_not_crashes():
    geom = ScreenGeometry(1, 1)
    # width-1 = 0; must not divide-by-zero.
    px, py = model_to_physical(500, 500, geom)
    assert (px, py) == (0, 0)


def test_negative_geometry_offsets():
    geom = ScreenGeometry(1920, 1080, left=-3840, top=-1080)
    px, py = model_to_physical(0, 0, geom)
    assert px == -3840 and py == -1080


# --------------------------------------------------------------------------- #
# Config — hostile TOML / tier evasion.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("tier", ["free", "FREE", "Free", " free "])
def test_free_tier_all_casings_refused(tmp_path, tier):
    from operator_app.config import ConfigError, load_config
    cfg = tmp_path / "c.toml"
    cfg.write_text(f'[provider]\nauth="api_key"\ntier="{tier}"\n')
    with pytest.raises(ConfigError):
        load_config(cfg, tmp_path / ".env", load_env=False)


def test_config_garbage_toml_raises(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text("this is = = not valid toml [[[")
    with pytest.raises(Exception):
        from operator_app.config import load_config
        load_config(cfg, tmp_path / ".env", load_env=False)


# --------------------------------------------------------------------------- #
# Playbooks — brace bombs / malformed headers.
# --------------------------------------------------------------------------- #

def test_playbook_unmatched_braces():
    from operator_app.playbooks import parse_playbook
    pb = parse_playbook("---\nname: x\n---\nHello {{{unclosed and {a}")
    out = pb.render({"a": "Z"})
    assert "Z" in out  # substitutes what it can, leaves the rest, no crash


def test_playbook_placeholder_is_not_recursive():
    from operator_app.playbooks import parse_playbook
    pb = parse_playbook('---\nname: x\ninputs:\n  a: "{a}"\n---\n{a}')
    # a resolves to "{a}" and must NOT loop forever.
    out = pb.render({})
    assert out == "{a}"


# --------------------------------------------------------------------------- #
# Persona — wrong types in profile.toml must not crash composition.
# --------------------------------------------------------------------------- #

def test_persona_rules_as_string(tmp_path):
    from operator_app.persona import load_persona
    path = tmp_path / "p.toml"
    # rules given as a bare string instead of a list.
    path.write_text('[voice]\nrules = "be terse"\n[identity]\nname="X"\n')
    p = load_persona(path)
    # Should not crash when composing; a string is iterable char-by-char, which
    # would be ugly — assert it degrades without raising.
    si = p.system_instruction()
    assert isinstance(si, str)


# --------------------------------------------------------------------------- #
# Agent loop — failure injection.
# --------------------------------------------------------------------------- #

from operator_app.agent import Agent, StopReason
from operator_app.executor import Executor, FakeInput
from operator_app.guard import FlagKillSwitch
from operator_app.providers.mock import MockProvider
from operator_app.screen.base import FakeScreen
from operator_app.types import SafetyDecision, SafetyFlag, Step


def _agent(script, **kw):
    provider = kw.pop("provider", None)
    if provider is None:
        provider = MockProvider(script, model="gemini-3.8-flash")
    return Agent(
        provider=provider,
        executor=Executor(FakeInput(), settle_delay=0, sleep=lambda *_: None),
        screen=kw.pop("screen", FakeScreen(vary=True)),
        guard=Guard(),
        config=kw.pop("config", Config()),
        confirm_cb=kw.pop("confirm_cb", lambda *a: True),
        kill_switch=kw.pop("kill_switch", FlagKillSwitch()),
        **kw,
    )


class _BoomProvider:
    active_model = "gemini-3.8-flash"

    def start(self, **kw):
        return Step(actions=[Action(type=ActionType.KEY, keys="a")], usage=None or __import__("operator_app.types", fromlist=["Usage"]).Usage(1, 1, 0))

    def continue_(self, results):
        raise RuntimeError("model exploded")


def test_provider_exception_becomes_error_outcome():
    a = _agent([], provider=_BoomProvider())
    out = a.run(task="t", system_instruction="s")
    assert out.reason is StopReason.ERROR
    assert "exploded" in out.message


def test_confirm_callback_that_raises_is_treated_as_denied():
    # A GUI dialog that throws must not crash the loop; safe default = stop.
    def boom(*a):
        raise RuntimeError("dialog crashed")
    script = [Step(actions=[Action(type=ActionType.CLICK, x=1, y=1)], text="click Send")]
    a = _agent(script, confirm_cb=boom)
    out = a.run(task="t", system_instruction="s")
    assert out.reason in (StopReason.USER_DENIED, StopReason.ERROR)


def test_start_raises_becomes_error():
    class BadStart:
        active_model = "gemini-3.8-flash"
        def start(self, **kw):
            raise RuntimeError("no start")
        def continue_(self, r):
            return Step(done=True)
    a = _agent([], provider=BadStart())
    out = a.run(task="t", system_instruction="s")
    assert out.reason is StopReason.ERROR


# --------------------------------------------------------------------------- #
# Executor — junk.
# --------------------------------------------------------------------------- #

def test_executor_type_none_text_raises_cleanly():
    from operator_app.executor import ExecutorError
    ex = Executor(FakeInput(), settle_delay=0, sleep=lambda *_: None)
    with pytest.raises(ExecutorError):
        ex.execute(Action(type=ActionType.TYPE, text=None))


# --------------------------------------------------------------------------- #
# Privacy — redaction with hostile rectangles.
# --------------------------------------------------------------------------- #

def test_redaction_out_of_bounds_and_negative():
    import io
    from PIL import Image
    from operator_app.privacy import CapturePolicy
    im = Image.new("RGB", (40, 40), (255, 255, 255))
    buf = io.BytesIO(); im.save(buf, format="PNG")
    pol = CapturePolicy(redaction_regions=((-10, -10, 5, 5), (30, 30, 9999, 9999)))
    out = pol.redact(buf.getvalue())  # must not crash
    with Image.open(io.BytesIO(out)) as r:
        assert r.getpixel((39, 39)) == (0, 0, 0)  # huge region covers corner


def test_blocked_none_title():
    from operator_app.privacy import CapturePolicy
    pol = CapturePolicy(blocklist=("bank",))
    assert pol.blocked(None) is None


# --------------------------------------------------------------------------- #
# Recorder — secret flagged but no text; masking preserves length only.
# --------------------------------------------------------------------------- #

def test_recorder_secret_without_text():
    from operator_app.recorder import RecordedEvent
    e = RecordedEvent(kind="key", ts=0.1, secret=True, text=None)
    assert e.masked().text is None  # no crash on None text


# --------------------------------------------------------------------------- #
# Secrets — keyring backend that throws on read.
# --------------------------------------------------------------------------- #

def test_secrets_keyring_read_throws(monkeypatch):
    import operator_app.secrets_store as ss
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    class Broken:
        def get_password(self, *a): raise RuntimeError("locked")
    monkeypatch.setattr(ss, "_keyring", lambda: Broken())
    assert ss.get_api_key() is None  # swallow, don't crash


# --------------------------------------------------------------------------- #
# Prompt-injection defence-in-depth: an injected instruction that leads to a
# SEND must still hit the guard gate before anything leaves.
# --------------------------------------------------------------------------- #

def test_injection_send_is_gated_end_to_end():
    # Simulated post-injection model behaviour: type an attacker address, then
    # click Send. Typing is free; the send must require confirmation.
    script = [
        Step(actions=[Action(type=ActionType.TYPE, text="attacker@evil.com")],
             text="Filling the To field"),
        Step(actions=[Action(type=ActionType.CLICK, x=9, y=9)],
             text="Clicking Send to deliver"),
        Step(done=True),
    ]
    denied = {"n": 0}
    def deny_sends(action, decision, png):
        denied["n"] += 1
        return False  # user rejects the send
    a = _agent(script, confirm_cb=deny_sends, screen=FakeScreen(vary=True))
    out = a.run(task="t", system_instruction="s")
    assert out.reason is StopReason.USER_DENIED
    assert denied["n"] == 1  # the click-Send prompted; user stopped it


def test_ctrl_enter_in_outlook_is_gated_without_narration():
    g = Guard()
    # No compose words at all, bare Ctrl+Enter, but the window is Outlook.
    d = g.evaluate(Action(type=ActionType.KEY, keys="ctrl+enter"),
                   context_text="", window_title="Inbox - jk@firm.com - Outlook")
    assert d.needs_confirmation


def test_enter_in_plain_editor_not_gated():
    g = Guard()
    d = g.evaluate(Action(type=ActionType.KEY, keys="enter"),
                   context_text="new line in the document",
                   window_title="untitled - Notepad")
    assert d.verdict is Verdict.ALLOW  # Notepad Enter is just a newline
