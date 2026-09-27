"""Recorder: capture what the user does, review it, then optionally draft a
playbook from it.

Privacy is the whole point of this module. Keystrokes stay on disk locally.
Nothing recorded is sent to a model during normal runs. A draft playbook is only
produced after the user passes the recording through :meth:`Review.redacted`,
which lets them drop events and blank out secrets. Password-field input is masked
at capture time and never stored in the clear.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol


@dataclass
class RecordedEvent:
    """One captured input event."""

    kind: str                 # "click" | "type" | "key" | "scroll" | "screenshot"
    ts: float                 # seconds since recording start
    x: int | None = None
    y: int | None = None
    button: str | None = None
    text: str | None = None   # typed text (masked if secret)
    keys: str | None = None
    secret: bool = False      # captured while a password field was focused
    screenshot: str | None = None  # filename, if a screenshot was sampled here

    def masked(self) -> "RecordedEvent":
        """Return a copy with secret text replaced by asterisks."""
        if self.secret and self.text:
            return RecordedEvent(**{**asdict(self), "text": "*" * len(self.text)})
        return self


class InputListener(Protocol):
    """Global mouse/keyboard listener. Windows implementation added in Phase 2."""

    def start(self, sink: Callable[[RecordedEvent], None]) -> None: ...
    def stop(self) -> None: ...
    def paused(self) -> bool: ...


@dataclass
class Recording:
    """An in-memory recording plus its on-disk folder."""

    directory: Path
    events: list[RecordedEvent] = field(default_factory=list)
    started: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add(self, event: RecordedEvent) -> None:
        # Never store secret text in the clear.
        self.events.append(event.masked())

    def save(self) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / "events.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for e in self.events:
                fh.write(json.dumps(asdict(e.masked())) + "\n")
        return path


@dataclass
class Review:
    """The mandatory review/redaction gate before anything is sent to a model."""

    recording: Recording
    dropped_indices: set[int] = field(default_factory=set)

    def drop(self, index: int) -> None:
        self.dropped_indices.add(index)

    def redacted(self) -> list[RecordedEvent]:
        """Events the user kept, all masked. This is the ONLY data that may be
        sent to a model to draft a playbook.
        """
        return [
            e.masked()
            for i, e in enumerate(self.recording.events)
            if i not in self.dropped_indices
        ]

    def sampled_screenshots(self) -> list[str]:
        return [e.screenshot for e in self.redacted() if e.screenshot]


def build_draft_prompt(events: list[RecordedEvent], *, goal: str = "") -> str:
    """Turn a reviewed event list into a prompt asking a model to write a playbook."""
    lines = [
        "You are writing a reusable Operator playbook from a recording of a user "
        "performing a task. Output Markdown with a YAML front-matter header "
        "(name, description, inputs, success_criteria, max_steps) then Steps, "
        "Rules and Output sections. Generalise concrete values into {inputs}. "
        "Never include anything that looks like a password or secret.",
        "",
        f"Task goal: {goal or '(infer from the events)'}",
        "",
        "Recorded events (secrets already masked):",
    ]
    for i, e in enumerate(events):
        parts = [f"{i:03d}", f"+{e.ts:0.1f}s", e.kind]
        if e.x is not None:
            parts.append(f"@({e.x},{e.y})")
        if e.text:
            parts.append(f"text={e.text!r}")
        if e.keys:
            parts.append(f"keys={e.keys}")
        lines.append("  " + " ".join(parts))
    return "\n".join(lines)


def draft_playbook(
    review: Review,
    *,
    goal: str,
    generate: Callable[[str], str],
) -> str:
    """Produce draft playbook Markdown from a reviewed recording.

    ``generate`` is any text function (a model call, injected by the caller). The
    result is returned for the user to edit and save; it is NEVER auto-run.
    """
    prompt = build_draft_prompt(review.redacted(), goal=goal)
    draft = generate(prompt)
    banner = (
        "<!-- DRAFT playbook generated from a recording. Review every step "
        "before use. Do not run without editing. -->\n\n"
    )
    return banner + draft
