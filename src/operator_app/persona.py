"""The "baked me" layer: loads ``profile.toml`` and composes the personal system
instruction injected into every run, so the agent works in the owner's voice and
to the owner's rules from the first step.

The profile holds personal data, so it lives in ``profile.toml`` (git-ignored),
copied from ``profile.example.toml`` on first run — never committed, never baked
into a distributed binary.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Persona:
    name: str = ""
    role: str = ""
    country: str = ""
    timezone: str = ""
    work_email: str = ""
    org: str = ""
    engineering: str = ""
    spelling: str = "British"
    register: str = ""
    voice_rules: list[str] = field(default_factory=list)
    voice_samples: list[str] = field(default_factory=list)
    signoffs: dict[str, str] = field(default_factory=dict)
    common_tasks: list[str] = field(default_factory=list)
    working_hours: str = ""
    do_not_auto_contact: list[str] = field(default_factory=list)
    sensitive_contacts: list[str] = field(default_factory=list)
    never: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """True if no substantive profile content was supplied (spelling default
        alone doesn't count), so composing should be a no-op.
        """
        return not any((
            self.name, self.role, self.org, self.register,
            self.voice_rules, self.voice_samples, self.common_tasks,
            self.do_not_auto_contact, self.sensitive_contacts, self.never,
        ))

    def system_instruction(self) -> str:
        """The persona block prepended to every task/playbook instruction."""
        if self.is_empty():
            return ""
        L: list[str] = ["# Who you are working for"]
        who = ", ".join(p for p in (self.role, self.org, self.country) if p)
        if self.name:
            L.append(f"You are assisting {self.name}" + (f" — {who}." if who else "."))
        if self.timezone:
            L.append(f"Timezone: {self.timezone}. Track the current date and time.")
        if self.engineering:
            L.append(f"Their technical background: {self.engineering}")

        L.append("\n# Voice and style")
        if self.spelling:
            L.append(f"- Use {self.spelling} spelling.")
        if self.register:
            L.append(f"- {self.register}")
        L += [f"- {r}" for r in self.voice_rules]
        for i, s in enumerate(self.voice_samples, 1):
            if i == 1:
                L.append("Voice samples (match this phrasing):")
            L.append(f'  {i}. "{s}"')
        if any(self.signoffs.values()):
            offs = "; ".join(f"{k}: {v}" for k, v in self.signoffs.items() if v)
            L.append(f"Sign off as — {offs}.")

        if self.common_tasks:
            L.append("\n# Their recurring work")
            L += [f"- {t}" for t in self.common_tasks]
        if self.working_hours:
            L.append(f"Working hours: {self.working_hours}.")

        if self.do_not_auto_contact or self.sensitive_contacts:
            L.append("\n# People rules")
            if self.do_not_auto_contact:
                L.append("NEVER draft to or act on these without explicit approval: "
                         + ", ".join(self.do_not_auto_contact) + ".")
            if self.sensitive_contacts:
                L.append("Treat these with extra care: "
                         + ", ".join(self.sensitive_contacts) + ".")

        if self.never:
            L.append("\n# Hard boundaries")
            L += [f"- {n}" for n in self.never]

        return "\n".join(L).strip()

    def compose(self, task_instruction: str) -> str:
        """Prepend the persona to a task/playbook instruction."""
        persona = self.system_instruction()
        if not persona:
            return task_instruction
        return f"{persona}\n\n# This run's task\n{task_instruction}".strip()


def load_persona(path: str | Path = "profile.toml") -> Persona:
    """Load a profile. A missing file yields an empty (harmless) persona."""
    p = Path(path)
    if not p.exists():
        return Persona()
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    ident = data.get("identity", {})
    bg = data.get("background", {})
    voice = data.get("voice", {})
    habits = data.get("habits", {})
    boundaries = data.get("boundaries", {})
    return Persona(
        name=ident.get("name", ""),
        role=ident.get("role", ""),
        country=ident.get("country", ""),
        timezone=ident.get("timezone", ""),
        work_email=ident.get("work_email", ""),
        org=ident.get("org", ""),
        engineering=bg.get("engineering", ""),
        spelling=voice.get("spelling", "British"),
        register=voice.get("register", ""),
        voice_rules=list(voice.get("rules", [])),
        voice_samples=[s for s in voice.get("voice_samples", []) if s],
        signoffs=dict(voice.get("signoffs", {})),
        common_tasks=[t for t in habits.get("common_tasks", []) if t],
        working_hours=habits.get("working_hours", ""),
        do_not_auto_contact=list(habits.get("do_not_auto_contact", [])),
        sensitive_contacts=list(habits.get("sensitive_contacts", [])),
        never=list(boundaries.get("never", [])),
    )
