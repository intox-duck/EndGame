"""Per-run logging: a timestamped folder with a JSONL step log, screenshots and
a final ``summary.md``. No telemetry; everything stays local.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from operator_app.cost import CostBreakdown
from operator_app.types import Action, Step


def _jsonable(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "value"):  # enums
        return obj.value
    if isinstance(obj, bytes):
        return f"<{len(obj)} bytes>"
    return obj


class RunLogger:
    """Writes one run's artefacts into ``<logs_dir>/<timestamp>/``."""

    def __init__(self, logs_dir: str | Path, *, task: str, playbook: str = "") -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.dir = Path(logs_dir) / stamp
        self.dir.mkdir(parents=True, exist_ok=True)
        self.screens_dir = self.dir / "screenshots"
        self.screens_dir.mkdir(exist_ok=True)
        self._steps_path = self.dir / "steps.jsonl"
        self._task = task
        self._playbook = playbook
        self._n = 0
        self._started = datetime.now(timezone.utc)

    def log_step(
        self,
        step: Step,
        *,
        latency_s: float = 0.0,
        executed: list[Action] | None = None,
        note: str = "",
    ) -> int:
        self._n += 1
        record = {
            "step": self._n,
            "ts": datetime.now(timezone.utc).isoformat(),
            "model": step.model,
            "text": step.text,
            "actions": [_jsonable(a) for a in step.actions],
            "executed": [_jsonable(a) for a in (executed or [])],
            "done": step.done,
            "usage": _jsonable(step.usage),
            "safety": [_jsonable(s) for s in step.safety],
            "latency_s": round(latency_s, 3),
            "note": note,
        }
        with self._steps_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        return self._n

    def save_screenshot(self, png: bytes, *, step: int | None = None) -> Path:
        name = f"step-{step or self._n:03d}.png"
        path = self.screens_dir / name
        path.write_bytes(png)
        return path

    def write_summary(
        self,
        *,
        outcome: str,
        model_used: str,
        steps: int,
        cost: CostBreakdown,
        tokens_in: int,
        tokens_out: int,
        cached_in: int,
        extra: str = "",
    ) -> Path:
        elapsed = (datetime.now(timezone.utc) - self._started).total_seconds()
        symbol = {"USD": "$", "GBP": "£", "EUR": "€"}.get(cost.currency, "")
        lines = [
            "# Run summary",
            "",
            f"- **Outcome:** {outcome}",
            f"- **Task:** {self._task}",
            f"- **Playbook:** {self._playbook or '(none)'}",
            f"- **Model used:** {model_used}",
            f"- **Steps:** {steps}",
            f"- **Elapsed:** {elapsed:0.1f}s",
            f"- **Tokens:** in {tokens_in:,} (cached {cached_in:,}) / out {tokens_out:,}",
            f"- **Cost:** {symbol}{cost.total:0.4f} {cost.currency}",
        ]
        if extra:
            lines += ["", extra]
        path = self.dir / "summary.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
