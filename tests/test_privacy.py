from __future__ import annotations

import io
import time

from PIL import Image

from operator_app.privacy import CapturePolicy, sweep_old_screenshots


def _png(w=40, h=40, colour=(200, 200, 200)):
    im = Image.new("RGB", (w, h), colour)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_blocklist_matches_substring_case_insensitive():
    pol = CapturePolicy(blocklist=("1password", "barclays"))
    assert pol.blocked("1Password - Vault") == "1password"
    assert pol.blocked("Barclays Online Banking") == "barclays"


def test_outlook_and_teams_not_blocked_by_default():
    from operator_app.config import Config
    pol = CapturePolicy(blocklist=Config().capture_blocklist)
    assert pol.blocked("Inbox - Outlook") is None
    assert pol.blocked("Microsoft Teams | General") is None


def test_no_block_returns_none():
    pol = CapturePolicy(blocklist=("banking",))
    assert pol.blocked("Notepad") is None


def test_redaction_blacks_out_region():
    pol = CapturePolicy(redaction_regions=((0, 0, 20, 20),))
    out = pol.redact(_png(40, 40, (255, 255, 255)))
    with Image.open(io.BytesIO(out)) as im:
        assert im.getpixel((5, 5)) == (0, 0, 0)      # inside region
        assert im.getpixel((30, 30)) == (255, 255, 255)  # outside


def test_redaction_noop_without_regions():
    pol = CapturePolicy()
    raw = _png()
    assert pol.redact(raw) == raw


def test_retention_sweep_deletes_old(tmp_path):
    old = tmp_path / "old.png"
    new = tmp_path / "new.png"
    old.write_bytes(_png())
    new.write_bytes(_png())
    now = time.time()
    import os
    os.utime(old, (now - 10 * 86400, now - 10 * 86400))
    deleted = sweep_old_screenshots(tmp_path, retention_days=7, now=now)
    assert old in deleted
    assert new.exists()
    assert not old.exists()


def test_retention_zero_days_is_noop(tmp_path):
    (tmp_path / "a.png").write_bytes(_png())
    assert sweep_old_screenshots(tmp_path, retention_days=0) == []
