from __future__ import annotations

import pytest

from operator_app.playbooks import (
    Playbook,
    PlaybookError,
    list_playbooks,
    parse_playbook,
)

SAMPLE = """---
name: demo
description: A demo playbook.
inputs:
  role_title: ""
  location: "London"
success_criteria:
  - Something checkable
max_steps: 30
---

# Steps
1. Search for {role_title} in {location}.
"""


def test_parse_basic():
    pb = parse_playbook(SAMPLE)
    assert pb.name == "demo"
    assert pb.inputs == {"role_title": "", "location": "London"}
    assert pb.success_criteria == ["Something checkable"]
    assert pb.max_steps == 30


def test_render_substitutes_inputs():
    pb = parse_playbook(SAMPLE)
    body = pb.render({"role_title": "Data Engineer"})
    assert "Data Engineer" in body
    assert "London" in body  # default used


def test_render_leaves_unknown_placeholder():
    pb = parse_playbook("---\nname: x\n---\nHello {unknown}.")
    assert pb.render() == "Hello {unknown}."


def test_missing_inputs_detected():
    pb = parse_playbook(SAMPLE)
    assert pb.missing_inputs({}) == ["role_title"]
    assert pb.missing_inputs({"role_title": "X"}) == []


def test_missing_header_raises():
    with pytest.raises(PlaybookError):
        parse_playbook("no front matter here")


def test_missing_name_raises():
    with pytest.raises(PlaybookError):
        parse_playbook("---\ndescription: x\n---\nbody")


def test_string_success_criteria_coerced():
    pb = parse_playbook("---\nname: x\nsuccess_criteria: just one\n---\nbody")
    assert pb.success_criteria == ["just one"]


def test_list_playbooks_skips_template(tmp_path):
    (tmp_path / "TEMPLATE.md").write_text("---\nname: t\n---\nx")
    (tmp_path / "good.md").write_text(SAMPLE)
    (tmp_path / "broken.md").write_text("not a playbook")
    names = [p.name for p in list_playbooks(tmp_path)]
    assert names == ["demo"]  # template skipped, broken skipped


def test_repo_demo_notepad_parses():
    # The shipped demo playbook must be valid.
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "playbooks" / "demo-notepad.md"
    if path.exists():
        pb = parse_playbook(path.read_text(encoding="utf-8"), path=path)
        assert pb.name == "demo-notepad"
        assert pb.max_steps == 25
