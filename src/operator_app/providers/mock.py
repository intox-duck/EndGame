"""A scripted provider that drives the loop with no API calls.

Used for the end-to-end loop test and for the GUI's offline demo. It emits a
fixed list of :class:`Step`s, ignoring the screenshots it receives, and reports
plausible token usage so the cost meter has something to add up.
"""

from __future__ import annotations

from operator_app.screen.base import ScreenGeometry
from operator_app.types import ActionResult, Step, Usage


class MockProvider:
    """Replays a predefined script of steps."""

    def __init__(self, script: list[Step], *, model: str = "mock-1") -> None:
        if not script:
            raise ValueError("MockProvider needs at least one step")
        self._script = script
        self.active_model = model
        self._i = 0
        # Record what it was given, for assertions in tests.
        self.started_with: dict | None = None
        self.results_seen: list[list[ActionResult]] = []

    def _stamp(self, step: Step) -> Step:
        if not step.model:
            step.model = self.active_model
        if step.usage == Usage():
            step.usage = Usage(input_tokens=1200, output_tokens=200, cached_input_tokens=800)
        return step

    def start(
        self,
        *,
        task: str,
        system_instruction: str,
        screenshot_png: bytes,
        geometry: ScreenGeometry,
    ) -> Step:
        self.started_with = {
            "task": task,
            "system_instruction": system_instruction,
            "geometry": geometry,
            "screenshot_bytes": len(screenshot_png),
        }
        self._i = 0
        step = self._script[self._i]
        self._i += 1
        return self._stamp(step)

    def continue_(self, results: list[ActionResult]) -> Step:
        self.results_seen.append(results)
        if self._i >= len(self._script):
            # Nothing scripted left: report done so the loop terminates safely.
            return self._stamp(Step(done=True, text="mock: script exhausted"))
        step = self._script[self._i]
        self._i += 1
        return self._stamp(step)
