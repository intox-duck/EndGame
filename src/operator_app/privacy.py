"""Privacy controls: capture blocklist, redaction, screenshot retention.

Screenshots are the main data leaving the machine, so this module governs what
may be captured and what is blacked out before sending. Scope note: Outlook and
Teams are intended *targets* for this owner, so they are NOT blocked by default;
banking apps and password managers are.
"""

from __future__ import annotations

import io
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class CapturePolicy:
    """Decides whether the current foreground window may be captured."""

    blocklist: tuple[str, ...] = ()
    redaction_regions: tuple[tuple[int, int, int, int], ...] = ()

    def blocked(self, window_title: str) -> str | None:
        """Return the matching blocklist term if capture is blocked, else None."""
        title = (window_title or "").lower()
        for term in self.blocklist:
            if term.lower() in title:
                return term
        return None

    def redact(self, png: bytes) -> bytes:
        """Black out configured rectangles (x, y, w, h) before the image is sent."""
        if not self.redaction_regions:
            return png
        with Image.open(io.BytesIO(png)) as im:
            im = im.convert("RGB")
            for (x, y, w, h) in self.redaction_regions:
                for py in range(max(0, y), min(im.height, y + h)):
                    for px in range(max(0, x), min(im.width, x + w)):
                        im.putpixel((px, py), (0, 0, 0))
            out = io.BytesIO()
            im.save(out, format="PNG")
            return out.getvalue()


def sweep_old_screenshots(
    root: str | Path,
    retention_days: int,
    *,
    now: float | None = None,
    pattern: str = "*.png",
) -> list[Path]:
    """Delete screenshots older than ``retention_days`` under ``root``.

    Returns the list of deleted paths. Logs (JSONL/summary) are left untouched;
    only image files matching ``pattern`` are removed.
    """
    root = Path(root)
    if retention_days <= 0 or not root.exists():
        return []
    now = time.time() if now is None else now
    cutoff = now - retention_days * 86400
    deleted: list[Path] = []
    for path in root.rglob(pattern):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
                deleted.append(path)
        except OSError:
            continue
    return deleted
