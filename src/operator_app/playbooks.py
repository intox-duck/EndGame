"""Playbook parsing: Markdown with a YAML front-matter header.

A playbook names a repeatable run: its inputs, success criteria and step limit,
plus the Markdown body that becomes the model's system instruction. ``{input}``
placeholders in the body are filled from the user's values before sending.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_FRONT_MATTER = re.compile(r"^\s*---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


class PlaybookError(Exception):
    pass


@dataclass(frozen=True)
class Playbook:
    name: str
    description: str
    inputs: dict[str, str]
    success_criteria: list[str]
    max_steps: int
    body: str
    path: Path | None = None

    def render(self, values: dict[str, str] | None = None) -> str:
        """Return the body with ``{key}`` placeholders substituted.

        Missing keys fall back to the playbook's declared defaults. Unknown
        placeholders are left as-is rather than raising, so a stray brace in prose
        doesn't break a run.
        """
        merged = dict(self.inputs)
        if values:
            merged.update({k: v for k, v in values.items() if v is not None})

        def repl(m: re.Match) -> str:
            key = m.group(1)
            return str(merged.get(key, m.group(0)))

        return re.sub(r"\{([a-zA-Z0-9_]+)\}", repl, self.body)

    def missing_inputs(self, values: dict[str, str]) -> list[str]:
        """Inputs declared with an empty default and not supplied by the user."""
        return [
            k for k, default in self.inputs.items()
            if not (values.get(k) or default)
        ]


def parse_playbook(text: str, *, path: Path | None = None) -> Playbook:
    m = _FRONT_MATTER.match(text)
    if not m:
        raise PlaybookError("Playbook is missing its --- YAML front-matter header.")
    header_raw, body = m.group(1), m.group(2).strip()
    try:
        header = yaml.safe_load(header_raw) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - passthrough
        raise PlaybookError(f"Invalid YAML header: {exc}") from exc
    if not isinstance(header, dict):
        raise PlaybookError("Playbook header must be a YAML mapping.")

    name = header.get("name")
    if not name:
        raise PlaybookError("Playbook header must include a 'name'.")

    inputs_raw = header.get("inputs") or {}
    if not isinstance(inputs_raw, dict):
        raise PlaybookError("'inputs' must be a mapping of name -> default.")
    inputs = {str(k): ("" if v is None else str(v)) for k, v in inputs_raw.items()}

    criteria = header.get("success_criteria") or []
    if isinstance(criteria, str):
        criteria = [criteria]

    return Playbook(
        name=str(name),
        description=str(header.get("description", "")),
        inputs=inputs,
        success_criteria=[str(c) for c in criteria],
        max_steps=int(header.get("max_steps", 150)),
        body=body,
        path=path,
    )


def load_playbook(path: str | Path) -> Playbook:
    path = Path(path)
    if not path.exists():
        raise PlaybookError(f"Playbook not found: {path}")
    return parse_playbook(path.read_text(encoding="utf-8"), path=path)


def list_playbooks(directory: str | Path) -> list[Playbook]:
    directory = Path(directory)
    if not directory.exists():
        return []
    out: list[Playbook] = []
    for p in sorted(directory.glob("*.md")):
        if p.name.upper() == "TEMPLATE.MD":
            continue
        try:
            out.append(load_playbook(p))
        except PlaybookError:
            continue  # skip malformed playbooks rather than failing the picker
    return out
