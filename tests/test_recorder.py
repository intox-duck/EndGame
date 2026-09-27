from __future__ import annotations

from pathlib import Path

from operator_app.recorder import (
    RecordedEvent,
    Recording,
    Review,
    build_draft_prompt,
    draft_playbook,
)


def test_secret_text_masked_on_add(tmp_path):
    rec = Recording(directory=Path(tmp_path))
    rec.add(RecordedEvent(kind="type", ts=1.0, text="hunter2", secret=True))
    assert rec.events[0].text == "*******"


def test_non_secret_text_kept(tmp_path):
    rec = Recording(directory=Path(tmp_path))
    rec.add(RecordedEvent(kind="type", ts=1.0, text="hello", secret=False))
    assert rec.events[0].text == "hello"


def test_save_writes_masked(tmp_path):
    rec = Recording(directory=Path(tmp_path))
    rec.add(RecordedEvent(kind="type", ts=1.0, text="s3cr3t", secret=True))
    path = rec.save()
    content = path.read_text()
    assert "s3cr3t" not in content
    assert "******" in content


def test_review_drops_events(tmp_path):
    rec = Recording(directory=Path(tmp_path))
    rec.add(RecordedEvent(kind="click", ts=0.1, x=1, y=1))
    rec.add(RecordedEvent(kind="type", ts=0.2, text="keep"))
    review = Review(rec)
    review.drop(0)
    kept = review.redacted()
    assert len(kept) == 1
    assert kept[0].text == "keep"


def test_draft_prompt_masks_and_lists():
    events = [
        RecordedEvent(kind="type", ts=0.5, text="hunter2", secret=True).masked(),
        RecordedEvent(kind="click", ts=1.0, x=10, y=20),
    ]
    prompt = build_draft_prompt(events, goal="Log in and search")
    assert "hunter2" not in prompt
    assert "Log in and search" in prompt
    assert "@(10,20)" in prompt


def test_draft_playbook_wraps_with_banner(tmp_path):
    rec = Recording(directory=Path(tmp_path))
    rec.add(RecordedEvent(kind="click", ts=0.1, x=1, y=1))
    review = Review(rec)
    md = draft_playbook(review, goal="x", generate=lambda p: "---\nname: y\n---\nbody")
    assert md.startswith("<!-- DRAFT")
    assert "name: y" in md
