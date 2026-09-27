from __future__ import annotations

from pathlib import Path

from operator_app.persona import Persona, load_persona

SAMPLE = """
[identity]
name = "James King"
role = "Senior Talent Intelligence Lead"
country = "United Kingdom"
timezone = "Europe/London"
org = "UK recruitment firm."

[background]
engineering = "Python/FastAPI, TS/Next.js, Fabric."

[voice]
spelling = "British"
register = "Terse, dry wit."
rules = ["Lead with the answer.", "Push back when I'm wrong."]
voice_samples = ["Thanks for the steer — shortlist Thursday.", ""]
signoffs = { email = "Best, James", slack = "J" }

[habits]
common_tasks = ["Triage overnight inbox", ""]
working_hours = "08:30-18:00"
do_not_auto_contact = ["ceo@client.com"]
sensitive_contacts = ["my manager"]

[boundaries]
never = ["Never send without confirmation.", "Never automate LinkedIn."]
"""


def test_empty_persona_is_harmless():
    p = Persona()
    # No profile => composing just returns the task unchanged.
    assert p.compose("do the thing") == "do the thing"


def test_load_and_compose(tmp_path):
    path = tmp_path / "profile.toml"
    path.write_text(SAMPLE)
    p = load_persona(path)
    assert p.name == "James King"
    assert p.voice_samples == ["Thanks for the steer — shortlist Thursday."]  # blanks dropped
    si = p.system_instruction()
    assert "British" in si
    assert "Senior Talent Intelligence Lead" in si
    assert "ceo@client.com" in si
    assert "Never automate LinkedIn." in si


def test_compose_prepends_persona(tmp_path):
    path = tmp_path / "profile.toml"
    path.write_text(SAMPLE)
    p = load_persona(path)
    composed = p.compose("Open the demo playbook.")
    assert composed.startswith("# Who you are working for")
    assert "This run's task" in composed
    assert composed.strip().endswith("Open the demo playbook.")


def test_missing_file_returns_empty():
    p = load_persona(Path("does-not-exist.toml"))
    assert p == Persona()


def test_shipped_example_is_valid():
    root = Path(__file__).resolve().parents[1]
    example = root / "profile.example.toml"
    if example.exists():
        p = load_persona(example)
        assert p.name == "James King"
        assert p.spelling == "British"
