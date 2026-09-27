"""Tests for the Gemini adapter using fixture objects shaped like the SDK's.

These stand in for recorded API responses: the adapter only touches attributes
(`name`, `args`, `id`, `candidates`, `content.parts`, `usage_metadata`), so simple
namespaces exercise the real normalisation and coordinate maths without a network
call. When the live desktop action names are confirmed, update _ACTION_MAP and add
real recorded fixtures alongside these.
"""

from __future__ import annotations

from types import SimpleNamespace as NS

from operator_app.config import Config
from operator_app.providers.gemini import (
    GeminiProvider,
    _extract_xy,
    _parse_safety,
)
from operator_app.screen.base import ScreenGeometry
from operator_app.types import ActionType, SafetyDecision


class FakeModels:
    def __init__(self, names, responses=None):
        self._names = names
        self._responses = responses or []
        self._i = 0

    def list(self):
        return [NS(name=n) for n in self._names]

    def generate_content(self, *, model, contents, config):
        resp = self._responses[self._i]
        self._i += 1
        return resp


class FakeClient:
    def __init__(self, names, responses=None):
        self.models = FakeModels(names, responses)


def make_provider(names=("gemini-3.8-flash", "gemini-3.5-flash"), active=None,
                  responses=None, geometry=None):
    cfg = Config()
    p = GeminiProvider(
        config=cfg,
        client=FakeClient(names, responses),
        active_model=active or "",
        geometry=geometry or ScreenGeometry(1920, 1080),
    )
    return p


# --- helpers to build response fixtures ---

def fc(name, args=None, id="c1"):
    return NS(function_call=NS(name=name, args=args or {}, id=id),
              text=None, inline_data=None)


def text_part(t):
    return NS(function_call=None, text=t, inline_data=None)


def response(parts, usage=None):
    cand = NS(content=NS(parts=parts, role="model"))
    return NS(candidates=[cand],
              usage_metadata=usage or NS(prompt_token_count=1000,
                                         candidates_token_count=200,
                                         cached_content_token_count=800))


# --- model selection / fallback ---

def test_prefers_preferred_model():
    p = make_provider(names=("gemini-3.8-flash", "gemini-3.5-flash"))
    assert p.active_model == "gemini-3.8-flash"


def test_falls_back_when_preferred_absent():
    p = make_provider(names=("gemini-3.5-flash",))
    assert p.active_model == "gemini-3.5-flash"


def test_raises_when_no_model_available():
    import pytest
    from operator_app.providers.base import ProviderError
    with pytest.raises(ProviderError):
        make_provider(names=("some-other-model",))


def test_model_id_strips_path_prefix():
    p = make_provider(names=("publishers/google/models/gemini-3.8-flash",))
    assert p.active_model == "gemini-3.8-flash"


# --- coordinate extraction ---

def test_extract_xy_variants():
    assert _extract_xy({"x": 100, "y": 200}) == (100.0, 200.0)
    assert _extract_xy({"coordinate": [10, 20]}) == (10.0, 20.0)
    assert _extract_xy({}) == (None, None)


# --- action normalisation ---

def test_click_normalised_and_converted():
    p = make_provider(active="gemini-3.5-flash",
                      geometry=ScreenGeometry(1000, 1000))
    action, flag = p._to_action(NS(name="click_at", args={"x": 999, "y": 0}, id="1"), 0)
    assert action.type is ActionType.CLICK
    assert action.x == 999  # 999/999 * (1000-1) = 999
    assert action.y == 0
    assert flag is None


def test_type_text_normalised():
    p = make_provider(active="gemini-3.5-flash")
    action, _ = p._to_action(NS(name="type_text_at", args={"text": "hello"}, id="1"), 0)
    assert action.type is ActionType.TYPE
    assert action.text == "hello"


def test_key_combination_joined():
    p = make_provider(active="gemini-3.5-flash")
    action, _ = p._to_action(
        NS(name="key_combination", args={"keys": ["ctrl", "s"]}, id="1"), 0)
    assert action.type is ActionType.KEY
    assert action.keys == "ctrl+s"


def test_scroll_direction_sign():
    p = make_provider(active="gemini-3.5-flash")
    up, _ = p._to_action(NS(name="scroll", args={"direction": "up", "amount": 5}, id="1"), 0)
    down, _ = p._to_action(NS(name="scroll", args={"direction": "down", "amount": 5}, id="2"), 0)
    assert up.scroll_dy == -5
    assert down.scroll_dy == 5


def test_unknown_action_becomes_confirm_flag():
    p = make_provider(active="gemini-3.5-flash")
    action, flag = p._to_action(NS(name="frobnicate", args={}, id="1"), 0)
    assert action is None
    assert flag.decision is SafetyDecision.REQUIRE_CONFIRMATION


def test_drag_two_points_converted():
    p = make_provider(active="gemini-3.5-flash", geometry=ScreenGeometry(1000, 1000))
    action, _ = p._to_action(
        NS(name="drag_and_drop",
           args={"x": 0, "y": 0, "destination": [999, 999]}, id="1"), 0)
    assert action.type is ActionType.DRAG
    assert (action.x, action.y) == (0, 0)
    assert (action.x2, action.y2) == (999, 999)


# --- safety parsing ---

def test_parse_safety_require_confirmation():
    flag = _parse_safety({"safety_decision": {"decision": "require_confirmation",
                                              "explanation": "sends an email"}})
    assert flag.decision is SafetyDecision.REQUIRE_CONFIRMATION
    assert "email" in flag.explanation


def test_parse_safety_none():
    assert _parse_safety({}) is None


def test_action_carries_safety_flag():
    p = make_provider(active="gemini-3.5-flash")
    _, flag = p._to_action(
        NS(name="click_at",
           args={"x": 1, "y": 1,
                 "safety_decision": {"decision": "require_confirmation"}}, id="1"), 2)
    assert flag.decision is SafetyDecision.REQUIRE_CONFIRMATION
    assert flag.action_index == 2


# --- response parsing / done detection ---

def test_parse_response_with_actions():
    p = make_provider(active="gemini-3.5-flash")
    resp = response([text_part("I'll click"), fc("click_at", {"x": 500, "y": 500})])
    step = p._parse_response(resp)
    assert step.done is False
    assert len(step.actions) == 1
    assert step.text == "I'll click"
    assert step.usage.input_tokens == 1000


def test_parse_response_done_when_no_calls():
    p = make_provider(active="gemini-3.5-flash")
    step = p._parse_response(response([text_part("All finished.")]))
    assert step.done is True
    assert "finished" in step.text


def test_start_then_generate_uses_client():
    resp = response([fc("type_text_at", {"text": "hi"})])
    p = make_provider(active="gemini-3.5-flash", responses=[resp])
    step = p.start(task="do", system_instruction="sys",
                   screenshot_png=b"\x89PNG", geometry=ScreenGeometry(1920, 1080))
    assert step.actions[0].type is ActionType.TYPE
    assert step.actions[0].text == "hi"
