"""The agent loop: screenshot -> model -> actions -> screenshot, with caps,
guard integration, stuck detection and dry-run.

The loop is deliberately free of GUI and platform code. It talks to a
:class:`~operator.providers.base.Provider`, an :class:`~operator.executor.Executor`,
a screen backend, the :class:`~operator.guard.Guard`, and callbacks for
confirmation and progress. That keeps it fully testable with fakes.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from operator_app.config import Config
from operator_app.cost import CostMeter
from operator_app.executor import Executor
from operator_app.guard import Guard, GuardDecision, KillSwitch, Verdict
from operator_app.logging_run import RunLogger
from operator_app.privacy import CapturePolicy
from operator_app.providers.base import Provider
from operator_app.screen.base import ScreenBackend
from operator_app.types import Action, ActionResult, ActionType, SafetyDecision, Step


class StopReason(str, Enum):
    DONE = "done"
    MAX_STEPS = "max_steps"
    MAX_COST = "max_cost"
    MAX_RUNTIME = "max_runtime"
    KILLED = "killed"
    USER_DENIED = "user_denied"
    REFUSED = "refused"
    STUCK = "stuck"
    CAPTURE_BLOCKED = "capture_blocked"
    ERROR = "error"


@dataclass
class RunOutcome:
    reason: StopReason
    steps: int
    cost_total: float
    model_used: str
    message: str = ""
    log_dir: str | None = None


# A confirmation callback: given the action, the guard/safety reason and the
# current screenshot, return True to proceed or False to stop. The GUI supplies
# this; tests supply a lambda.
ConfirmCallback = Callable[[Action, GuardDecision, bytes], bool]
ProgressCallback = Callable[[Step], None]


@dataclass
class ConfirmRequest:
    action: Action
    decision: GuardDecision
    screenshot_png: bytes


@dataclass
class Agent:
    provider: Provider
    executor: Executor
    screen: ScreenBackend
    guard: Guard
    config: Config
    capture_policy: CapturePolicy = field(default_factory=CapturePolicy)
    logger: RunLogger | None = None
    kill_switch: KillSwitch | None = None
    confirm_cb: ConfirmCallback | None = None
    progress_cb: ProgressCallback | None = None
    dry_run: bool = False
    clock: Callable[[], float] = time.monotonic

    # --- internal state ---
    _recent_hashes: list[str] = field(default_factory=list, init=False)
    _recent_actions: list[str] = field(default_factory=list, init=False)
    _recovered: bool = field(default=False, init=False)

    def run(self, *, task: str, system_instruction: str, max_steps: int | None = None) -> RunOutcome:
        cap_steps = max_steps or self.config.max_steps
        meter = CostMeter(self.config, self.provider.active_model)
        start_time = self.clock()

        capture = self._capture_guarded()
        if capture is None:
            return self._finish(StopReason.CAPTURE_BLOCKED, 0, meter, "Capture blocked by policy.")

        try:
            step = self.provider.start(
                task=task,
                system_instruction=system_instruction,
                screenshot_png=capture.png,
                geometry=capture.geometry,
            )
        except Exception as exc:  # provider/network failure
            return self._finish(StopReason.ERROR, 0, meter, f"Provider error: {exc}")

        step_no = 0
        while True:
            step_no += 1
            meter.add(step.usage)
            if self.progress_cb:
                self.progress_cb(step)

            latency = 0.0  # provider latency is measured inside real providers
            if self.logger:
                self.logger.log_step(step, latency_s=latency)

            # Caps.
            if self.kill_switch and self.kill_switch.aborted():
                return self._finish(StopReason.KILLED, step_no, meter, "Kill switch.")
            if meter.total().total > self.config.max_cost_per_run:
                return self._finish(StopReason.MAX_COST, step_no, meter, "Cost cap reached.")
            if self.clock() - start_time > self.config.max_runtime_seconds:
                return self._finish(StopReason.MAX_RUNTIME, step_no, meter, "Runtime cap reached.")

            if step.done:
                return self._finish(StopReason.DONE, step_no, meter, step.text or "Done.")

            # Execute this step's actions, collecting results for the provider.
            results, stop = self._run_actions(step, capture_png=capture.png)
            if stop is not None:
                return self._finish(stop, step_no, meter, self._stop_message(stop))

            # Stuck detection on the last screenshot.
            if results and results[-1].screenshot_png is not None:
                if self._is_stuck(results[-1].screenshot_png, step):
                    if not self._recovered:
                        self._recovered = True
                        # One recovery nudge: tell the model it appears stuck.
                        results.append(ActionResult(
                            action=results[-1].action,
                            ok=False,
                            error="No visible change after the last actions; try a "
                                  "different approach.",
                        ))
                    else:
                        return self._finish(StopReason.STUCK, step_no, meter,
                                            "Stuck: no change after recovery attempt.")

            if step_no >= cap_steps:
                return self._finish(StopReason.MAX_STEPS, step_no, meter, "Step cap reached.")

            try:
                step = self.provider.continue_(results)
            except Exception as exc:
                return self._finish(StopReason.ERROR, step_no, meter, f"Provider error: {exc}")

    # ------------------------------------------------------------------ helpers

    def _run_actions(
        self, step: Step, *, capture_png: bytes
    ) -> tuple[list[ActionResult], StopReason | None]:
        results: list[ActionResult] = []
        window = self.screen.foreground_window_title()
        safety_by_index = {s.action_index: s for s in step.safety if s.action_index is not None}
        model_level_safety = [s for s in step.safety if s.action_index is None]

        for idx, action in enumerate(step.actions):
            if self.kill_switch and self.kill_switch.aborted():
                return results, StopReason.KILLED

            decision = self.guard.evaluate(action, context_text=step.text, window_title=window)
            if decision.refused:
                return results, StopReason.REFUSED

            acknowledged = False
            # Model's own safety request for this action (or the whole step).
            model_flag = safety_by_index.get(idx) or (model_level_safety[0] if (idx == 0 and model_level_safety) else None)
            needs_confirm = decision.needs_confirmation or (
                model_flag is not None
                and model_flag.decision is SafetyDecision.REQUIRE_CONFIRMATION
            )
            if model_flag is not None and model_flag.decision is SafetyDecision.BLOCK:
                return results, StopReason.REFUSED

            if needs_confirm:
                reason = decision.reason or (model_flag.explanation if model_flag else "")
                if not self._confirm(action, GuardDecision(Verdict.CONFIRM, reason), capture_png):
                    return results, StopReason.USER_DENIED
                acknowledged = model_flag is not None

            if self.dry_run:
                results.append(ActionResult(action=action, ok=True,
                                            safety_acknowledged=acknowledged,
                                            error="(dry-run: not executed)"))
                continue

            try:
                self.executor.execute(action)
                ok, err = True, ""
            except Exception as exc:
                ok, err = False, str(exc)

            shot = self._capture_guarded()
            png = shot.png if shot else None
            results.append(ActionResult(
                action=action, ok=ok, error=err, screenshot_png=png,
                width=shot.sent_width if shot else 0,
                height=shot.sent_height if shot else 0,
                safety_acknowledged=acknowledged,
            ))
            self._recent_actions.append(action.summary())
        return results, None

    def _confirm(self, action: Action, decision: GuardDecision, png: bytes) -> bool:
        if self.confirm_cb is None:
            # No way to ask -> safest default is to stop.
            return False
        return bool(self.confirm_cb(action, decision, png))

    def _capture_guarded(self):
        window = self.screen.foreground_window_title()
        blocked = self.capture_policy.blocked(window)
        if blocked:
            # Ask the user before capturing a blocklisted window; if they can't be
            # asked, refuse to capture.
            if self.confirm_cb is None:
                return None
            allow = self.confirm_cb(
                Action(type=ActionType.SCREENSHOT),
                GuardDecision(
                    Verdict.CONFIRM,
                    f"Foreground window {window!r} is on the capture blocklist "
                    f"({blocked}).",
                ),
                b"",
            )
            if not allow:
                return None
        cap = self.screen.capture(self.config.max_image_width)
        cap.png = self.capture_policy.redact(cap.png)
        return cap

    def _is_stuck(self, png: bytes, step: Step) -> bool:
        h = hashlib.sha256(png).hexdigest()
        self._recent_hashes.append(h)
        self._recent_hashes = self._recent_hashes[-3:]
        same_screen = len(self._recent_hashes) == 3 and len(set(self._recent_hashes)) == 1
        tail = self._recent_actions[-3:]
        repeated_action = len(tail) == 3 and len(set(tail)) == 1
        return same_screen or repeated_action

    def _stop_message(self, reason: StopReason) -> str:
        return {
            StopReason.REFUSED: "Refused by guard (secret/blocked action). Control returned to you.",
            StopReason.USER_DENIED: "You declined a confirmation. Stopped.",
            StopReason.KILLED: "Kill switch pressed. Stopped.",
        }.get(reason, reason.value)

    def _finish(self, reason: StopReason, steps: int, meter: CostMeter, message: str) -> RunOutcome:
        cost = meter.total()
        log_dir = None
        if self.logger:
            self.logger.write_summary(
                outcome=reason.value,
                model_used=self.provider.active_model,
                steps=steps,
                cost=cost,
                tokens_in=meter.usage.input_tokens,
                tokens_out=meter.usage.output_tokens,
                cached_in=meter.usage.cached_input_tokens,
                extra=message,
            )
            log_dir = str(self.logger.dir)
        return RunOutcome(
            reason=reason, steps=steps, cost_total=cost.total,
            model_used=self.provider.active_model, message=message, log_dir=log_dir,
        )
