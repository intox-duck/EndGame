"""Gemini computer-use provider (``google-genai`` SDK).

Built against ``docs/API_NOTES.md``, which was taken from introspecting
``google-genai==2.25.0`` (the live docs are unreachable from the build sandbox).
Everything the docs might still change is isolated here:

* action-name normalisation -> :data:`_ACTION_MAP`
* coordinate conversion -> :mod:`operator.screen` (normalised 0-999 -> pixels)
* safety-decision parsing -> :func:`_parse_safety`

When the live desktop action list is confirmed on Windows, only those spots move;
the agent loop, guard and executor are untouched.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from operator_app.config import Config
from operator_app.providers.base import ProviderError
from operator_app.screen.base import MODEL_COORD_MAX, ScreenGeometry, model_to_physical
from operator_app.types import (
    Action,
    ActionResult,
    ActionType,
    SafetyDecision,
    SafetyFlag,
    Step,
    Usage,
)

# Normalise Gemini predefined-function names -> our ActionType.
# ⚠ Desktop names are not enumerated by the SDK; these cover the documented
# browser set plus the expected desktop variants. Fix here once confirmed.
_ACTION_MAP: dict[str, ActionType] = {
    "click": ActionType.CLICK,
    "click_at": ActionType.CLICK,
    "left_click": ActionType.CLICK,
    "double_click": ActionType.DOUBLE_CLICK,
    "double_click_at": ActionType.DOUBLE_CLICK,
    "right_click": ActionType.RIGHT_CLICK,
    "right_click_at": ActionType.RIGHT_CLICK,
    "move": ActionType.MOVE,
    "hover_at": ActionType.MOVE,
    "mouse_move": ActionType.MOVE,
    "drag": ActionType.DRAG,
    "drag_and_drop": ActionType.DRAG,
    "type": ActionType.TYPE,
    "type_text": ActionType.TYPE,
    "type_text_at": ActionType.TYPE,
    "key": ActionType.KEY,
    "press_key": ActionType.KEY,
    "press_keys": ActionType.KEY,
    "key_combination": ActionType.KEY,
    "hotkey": ActionType.KEY,
    "scroll": ActionType.SCROLL,
    "scroll_at": ActionType.SCROLL,
    "scroll_document": ActionType.SCROLL,
    "wait": ActionType.WAIT,
    "wait_5_seconds": ActionType.WAIT,
    "take_screenshot": ActionType.SCREENSHOT,
    "screenshot": ActionType.SCREENSHOT,
    "navigate": ActionType.NAVIGATE,
    "open_web_browser": ActionType.NAVIGATE,
    "go_back": ActionType.GO_BACK,
    "go_forward": ActionType.GO_FORWARD,
}


def _first(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _num(v) -> float | None:
    """Best-effort float conversion; None for junk the model might emit."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


def _extract_xy(args: dict) -> tuple[float | None, float | None]:
    """Pull normalised coordinates out of assorted possible arg shapes.

    Never raises: malformed values from the model become (None, None) so the
    caller skips coordinates rather than crashing the run.
    """
    c = args.get("coordinate")
    if isinstance(c, (list, tuple)) and len(c) >= 2:
        x, y = _num(c[0]), _num(c[1])
        if x is not None and y is not None:
            return x, y
    x = _num(_first(args, "x", "px", "pos_x"))
    y = _num(_first(args, "y", "py", "pos_y"))
    if x is not None and y is not None:
        return x, y
    return None, None


def _parse_safety(args: dict) -> SafetyFlag | None:
    """Parse a ``safety_decision`` embedded in a function call's args."""
    sd = args.get("safety_decision")
    if not isinstance(sd, dict):
        return None
    decision = str(sd.get("decision", "")).lower()
    explanation = str(sd.get("explanation", ""))
    if "confirm" in decision:
        return SafetyFlag(SafetyDecision.REQUIRE_CONFIRMATION, explanation)
    if "block" in decision or "refuse" in decision:
        return SafetyFlag(SafetyDecision.BLOCK, explanation)
    return None


@dataclass
class GeminiProvider:
    config: Config
    geometry: ScreenGeometry | None = None
    active_model: str = ""
    # Injected for tests; defaults to a real google-genai client.
    client: object | None = None

    _contents: list = field(default_factory=list, init=False)
    _tool: object | None = field(default=None, init=False)
    _types: object | None = field(default=None, init=False)
    _coord_max: int = field(default=MODEL_COORD_MAX, init=False)

    def __post_init__(self) -> None:
        from google.genai import types  # noqa: PLC0415

        self._types = types
        if self.client is None:
            self.client = self._make_client()
        if not self.active_model:
            self.active_model = self._select_model()
        self._tool = types.Tool(
            computer_use=types.ComputerUse(
                environment=types.Environment.ENVIRONMENT_DESKTOP,
                enable_prompt_injection_detection=True,
            )
        )

    # ------------------------------------------------------------------ setup

    def _make_client(self):
        from google import genai  # noqa: PLC0415

        if self.config.auth == "vertex":
            import os  # noqa: PLC0415

            project = self.config.project or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
            return genai.Client(
                vertexai=True, project=project, location=self.config.location
            )
        from operator_app import secrets_store  # noqa: PLC0415

        key = secrets_store.get_api_key()
        if not key:
            raise ProviderError(
                "auth = api_key but no Gemini API key found (checked "
                "GOOGLE_API_KEY/GEMINI_API_KEY and the OS keyring). Run "
                "`operator --setup` or set the environment variable."
            )
        return genai.Client(api_key=key)

    def _select_model(self) -> str:
        """Pick the preferred model if available, else the fallback.

        Availability is checked by listing models. If listing fails (offline,
        permissions), we optimistically use the preferred model and let the first
        real call surface any error.
        """
        preferred = self.config.preferred_model
        fallback = self.config.fallback_model
        try:
            available = {self._model_id(m) for m in self.client.models.list()}
        except Exception:
            return preferred
        if self._model_id(preferred) in available:
            return preferred
        if self._model_id(fallback) in available:
            return fallback
        raise ProviderError(
            f"Neither {preferred!r} nor {fallback!r} is available on this "
            f"endpoint. Available: {sorted(available)[:10]}..."
        )

    @staticmethod
    def _model_id(m) -> str:
        name = getattr(m, "name", m) if not isinstance(m, str) else m
        return str(name).split("/")[-1]

    # ------------------------------------------------------------------ loop

    def start(
        self,
        *,
        task: str,
        system_instruction: str,
        screenshot_png: bytes,
        geometry: ScreenGeometry,
    ) -> Step:
        self.geometry = geometry
        types = self._types
        self._contents = [
            types.Content(role="user", parts=[
                types.Part.from_text(text=task),
                types.Part(inline_data=types.Blob(
                    mime_type="image/png", data=screenshot_png)),
            ])
        ]
        return self._generate(system_instruction=system_instruction)

    def continue_(self, results: list[ActionResult]) -> Step:
        types = self._types
        parts = []
        for r in results:
            response: dict = {"ok": r.ok}
            if r.error:
                response["error"] = r.error
            if r.safety_acknowledged:
                # ⚠ exact key/value — see docs/API_NOTES.md item 3.
                response["safety_acknowledgement"] = "CONTINUE"
            fr_parts = []
            if r.screenshot_png is not None:
                fr_parts.append(types.Part(inline_data=types.Blob(
                    mime_type="image/png", data=r.screenshot_png)))
            parts.append(types.Part(function_response=types.FunctionResponse(
                name=r.action.raw.get("gemini_name", r.action.type.value),
                id=r.action.raw.get("gemini_id"),
                response=response,
                parts=fr_parts or None,
            )))
        self._contents.append(types.Content(role="user", parts=parts))
        self._trim_screenshots()
        return self._generate(system_instruction=None)

    def _generate(self, *, system_instruction: str | None) -> Step:
        types = self._types
        cfg_kwargs = {"tools": [self._tool]}
        if system_instruction:
            cfg_kwargs["system_instruction"] = system_instruction
        t0 = time.monotonic()
        try:
            resp = self.client.models.generate_content(
                model=self.active_model,
                contents=self._contents,
                config=types.GenerateContentConfig(**cfg_kwargs),
            )
        except Exception as exc:
            raise ProviderError(f"generate_content failed: {exc}") from exc
        latency = time.monotonic() - t0

        step = self._parse_response(resp)
        step.raw["latency_s"] = round(latency, 3)
        # Append the model turn to history so the next call has full context.
        cand = self._candidate(resp)
        if cand is not None and getattr(cand, "content", None) is not None:
            self._contents.append(cand.content)
        return step

    # ------------------------------------------------------------------ parse

    def _candidate(self, resp):
        cands = getattr(resp, "candidates", None) or []
        return cands[0] if cands else None

    def _parse_response(self, resp) -> Step:
        step = Step(model=self.active_model)
        step.usage = self._usage(resp)
        cand = self._candidate(resp)
        if cand is None:
            step.done = True
            step.text = "No candidates returned."
            return step

        parts = getattr(getattr(cand, "content", None), "parts", None) or []
        saw_call = False
        for i, part in enumerate(parts):
            text = getattr(part, "text", None)
            if text:
                step.text += text
            fc = getattr(part, "function_call", None)
            if fc is None:
                continue
            saw_call = True
            action, flag = self._to_action(fc, len(step.actions))
            if action is not None:
                step.actions.append(action)
            if flag is not None:
                step.safety.append(flag)

        # Gemini signals completion by returning narration with no function call.
        step.done = not saw_call
        return step

    def _to_action(self, fc, index: int) -> tuple[Action | None, SafetyFlag | None]:
        name = getattr(fc, "name", "") or ""
        args = dict(getattr(fc, "args", None) or {})
        fc_id = getattr(fc, "id", None)
        atype = _ACTION_MAP.get(name.lower())
        if atype is None:
            # Unknown action: keep it visible in the log but don't execute.
            return None, SafetyFlag(
                SafetyDecision.REQUIRE_CONFIRMATION,
                f"Unknown model action {name!r}; skipped. Verify _ACTION_MAP.",
                index,
            )

        raw = {"gemini_name": name, "gemini_id": fc_id, "args": args}
        flag = _parse_safety(args)
        if flag is not None:
            flag = SafetyFlag(flag.decision, flag.explanation, index)

        kwargs: dict = {"type": atype, "raw": raw}
        if atype in (ActionType.CLICK, ActionType.DOUBLE_CLICK,
                     ActionType.RIGHT_CLICK, ActionType.MOVE, ActionType.SCROLL):
            mx, my = _extract_xy(args)
            if mx is not None and self.geometry is not None:
                px, py = model_to_physical(mx, my, self.geometry, self._coord_max)
                kwargs["x"], kwargs["y"] = px, py
        elif atype is ActionType.DRAG:
            mx, my = _extract_xy(args)
            dx = _first(args, "destination_x", "x2", "to_x")
            dy = _first(args, "destination_y", "y2", "to_y")
            dest = args.get("destination")
            if isinstance(dest, (list, tuple)) and len(dest) >= 2:
                dx, dy = dest[0], dest[1]
            dx, dy = _num(dx), _num(dy)
            if None not in (mx, my, dx, dy) and self.geometry is not None:
                kwargs["x"], kwargs["y"] = model_to_physical(mx, my, self.geometry, self._coord_max)
                kwargs["x2"], kwargs["y2"] = model_to_physical(dx, dy, self.geometry, self._coord_max)

        if atype is ActionType.TYPE:
            kwargs["text"] = str(_first(args, "text", "content", "value", default=""))
        if atype is ActionType.KEY:
            keys = _first(args, "keys", "key", "combination", "text")
            if isinstance(keys, (list, tuple)):
                keys = "+".join(str(k) for k in keys)
            kwargs["keys"] = str(keys or "")
        if atype is ActionType.SCROLL:
            kwargs["scroll_dx"] = int(_num(_first(args, "dx", "scroll_x", default=0)) or 0)
            direction = str(_first(args, "direction", default="")).lower()
            magnitude = int(_num(
                _first(args, "dy", "scroll_y", "amount", "magnitude", default=3)) or 3)
            if direction == "up":
                magnitude = -abs(magnitude)
            elif direction == "down":
                magnitude = abs(magnitude)
            kwargs["scroll_dy"] = magnitude
        if atype is ActionType.WAIT:
            secs = _num(_first(args, "seconds", "duration", default=5))
            kwargs["seconds"] = secs if secs is not None else 5.0
        if atype is ActionType.NAVIGATE:
            kwargs["text"] = str(_first(args, "url", "address", default=""))

        return Action(**kwargs), flag

    def _usage(self, resp) -> Usage:
        um = getattr(resp, "usage_metadata", None)
        if um is None:
            return Usage()
        return Usage(
            input_tokens=int(getattr(um, "prompt_token_count", 0) or 0),
            output_tokens=int(getattr(um, "candidates_token_count", 0) or 0),
            cached_input_tokens=int(getattr(um, "cached_content_token_count", 0) or 0),
        )

    def _trim_screenshots(self) -> None:
        """Keep only the last N screenshots in history; replace older image parts
        with a short text placeholder so context stays small and cheap.
        """
        keep = self.config.screenshots_in_context
        types = self._types
        # Find indices of content turns that carry an image part.
        image_turns = []
        for idx, content in enumerate(self._contents):
            parts = getattr(content, "parts", None) or []
            if any(getattr(p, "inline_data", None) is not None for p in parts):
                image_turns.append(idx)
            fr_has_image = any(
                getattr(getattr(p, "function_response", None), "parts", None)
                for p in parts
            )
            if fr_has_image:
                image_turns.append(idx)
        for idx in image_turns[:-keep] if keep > 0 else image_turns:
            content = self._contents[idx]
            new_parts = []
            for p in getattr(content, "parts", []) or []:
                if getattr(p, "inline_data", None) is not None:
                    new_parts.append(types.Part.from_text(text="[older screenshot omitted]"))
                    continue
                fr = getattr(p, "function_response", None)
                if fr is not None and getattr(fr, "parts", None):
                    fr.parts = None
                new_parts.append(p)
            content.parts = new_parts
