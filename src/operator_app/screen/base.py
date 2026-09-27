"""Screen backend interface, pure coordinate maths, and a fake for tests."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Protocol

from PIL import Image

# Gemini computer use returns coordinates normalised to this range on both axes.
# See docs/API_NOTES.md (⚠ verify against live docs before first live run).
MODEL_COORD_MAX = 999


@dataclass(frozen=True)
class ScreenGeometry:
    """Physical geometry of the monitor being driven.

    ``width``/``height`` are the *physical* pixel dimensions of the monitor.
    ``scale`` is the OS display scaling (1.0 = 100%, 1.25 = 125%, ...). It is
    recorded for logging and diagnostics; conversions use physical pixels
    directly because that is what the input backend must click.
    """

    width: int
    height: int
    scale: float = 1.0
    left: int = 0
    top: int = 0


@dataclass
class CaptureResult:
    """A captured, downscaled screenshot ready to send to the model."""

    png: bytes
    # Physical geometry the capture came from (for coordinate conversion back).
    geometry: ScreenGeometry
    # Size of the (possibly downscaled) image actually sent to the model.
    sent_width: int
    sent_height: int


def model_to_physical(
    mx: int | float,
    my: int | float,
    geom: ScreenGeometry,
    coord_max: int = MODEL_COORD_MAX,
) -> tuple[int, int]:
    """Convert normalised model coordinates (0..coord_max) to physical pixels.

    The model reasons over a normalised space regardless of the downscaled image
    size, so we map straight onto physical monitor pixels and offset by the
    monitor origin (for multi-monitor setups).
    """
    if coord_max <= 0:
        raise ValueError("coord_max must be positive")
    # Clamp into range so an out-of-range model value never lands off-screen.
    mx = min(max(float(mx), 0.0), float(coord_max))
    my = min(max(float(my), 0.0), float(coord_max))
    px = geom.left + round(mx / coord_max * (geom.width - 1))
    py = geom.top + round(my / coord_max * (geom.height - 1))
    return int(px), int(py)


def physical_to_model(
    px: int | float,
    py: int | float,
    geom: ScreenGeometry,
    coord_max: int = MODEL_COORD_MAX,
) -> tuple[int, int]:
    """Inverse of :func:`model_to_physical` (used by the recorder)."""
    if geom.width <= 1 or geom.height <= 1:
        raise ValueError("degenerate geometry")
    lx = min(max(float(px) - geom.left, 0.0), float(geom.width - 1))
    ly = min(max(float(py) - geom.top, 0.0), float(geom.height - 1))
    mx = round(lx / (geom.width - 1) * coord_max)
    my = round(ly / (geom.height - 1) * coord_max)
    return int(mx), int(my)


def downscale_png(png: bytes, max_width: int) -> tuple[bytes, int, int]:
    """Downscale a PNG so its width is at most ``max_width``.

    Returns ``(png_bytes, width, height)`` of the result. Aspect ratio is
    preserved. Images already narrow enough are returned re-encoded unchanged.
    """
    with Image.open(io.BytesIO(png)) as im:
        im = im.convert("RGB")
        w, h = im.size
        if w > max_width:
            new_h = round(h * max_width / w)
            im = im.resize((max_width, new_h), Image.LANCZOS)
            w, h = im.size
        out = io.BytesIO()
        im.save(out, format="PNG")
        return out.getvalue(), w, h


class ScreenBackend(Protocol):
    """Captures the screen. Real implementation is Windows-only (Phase 2)."""

    def geometry(self) -> ScreenGeometry: ...

    def capture(self, max_width: int) -> CaptureResult: ...

    def foreground_window_title(self) -> str: ...


class FakeScreen:
    """Deterministic screen backend for tests and the MockProvider loop."""

    def __init__(
        self,
        geometry: ScreenGeometry | None = None,
        *,
        foreground: str = "Notepad",
        fill: tuple[int, int, int] = (30, 30, 30),
        vary: bool = False,
    ) -> None:
        self._geom = geometry or ScreenGeometry(1920, 1080, 1.0)
        self._foreground = foreground
        self._fill = fill
        self._vary = vary  # when True each capture differs (defeats stuck detection)
        self.capture_count = 0

    def geometry(self) -> ScreenGeometry:
        return self._geom

    def set_foreground(self, title: str) -> None:
        self._foreground = title

    def foreground_window_title(self) -> str:
        return self._foreground

    def capture(self, max_width: int) -> CaptureResult:
        self.capture_count += 1
        fill = self._fill
        if self._vary:
            n = self.capture_count
            fill = (fill[0], fill[1], (fill[2] + n) % 256)
        im = Image.new("RGB", (self._geom.width, self._geom.height), fill)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        png, w, h = downscale_png(buf.getvalue(), max_width)
        return CaptureResult(png=png, geometry=self._geom, sent_width=w, sent_height=h)
