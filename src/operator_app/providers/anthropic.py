"""Anthropic (Claude computer use) provider — STUB.

Implements the same :class:`~operator.providers.base.Provider` interface so the
GUI can A/B Claude against Gemini later. The action loop, tool schema and
coordinate handling are left as TODOs and are UNTESTED. Do not select this
provider for a live run until it is completed and covered by fixtures like
``providers/gemini.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from operator_app.config import Config
from operator_app.providers.base import ProviderError
from operator_app.screen.base import ScreenGeometry
from operator_app.types import ActionResult, Step

# Claude computer use uses pixel coordinates against the actual image size sent,
# and a tool named "computer" with a display_width_px / display_height_px schema.
# TODO: confirm the current tool version string and action set against the docs.
_TOOL_VERSION = "computer_20250124"  # ⚠ verify before use


@dataclass
class AnthropicProvider:
    config: Config
    geometry: ScreenGeometry | None = None
    active_model: str = "claude-sonnet-5"
    client: object | None = None

    _messages: list = field(default_factory=list, init=False)

    def start(
        self,
        *,
        task: str,
        system_instruction: str,
        screenshot_png: bytes,
        geometry: ScreenGeometry,
    ) -> Step:  # pragma: no cover - stub
        raise ProviderError(
            "AnthropicProvider is a stub. Implement the Claude computer-use loop "
            f"(tool {_TOOL_VERSION}) before selecting it. See providers/gemini.py "
            "for the shape to mirror."
        )

    def continue_(self, results: list[ActionResult]) -> Step:  # pragma: no cover
        raise ProviderError("AnthropicProvider is a stub; continue_ not implemented.")
