"""Windows screen backend. Imported lazily; only used on Windows (Phase 2).

Isolated here so nothing on the cloud path imports ``mss``/``win32``. DPI
awareness MUST be set before the first capture or every coordinate will be wrong
on scaled displays — this is called from :func:`make_windows_screen`.
"""

from __future__ import annotations

import ctypes
import io

from PIL import Image

from operator_app.screen.base import CaptureResult, ScreenGeometry, downscale_png

_dpi_set = False


def set_dpi_awareness() -> None:
    """Make the process per-monitor DPI aware, before any capture.

    Tries the modern PerMonitorV2 context, then falls back to older APIs. Safe to
    call more than once.
    """
    global _dpi_set
    if _dpi_set:
        return
    try:  # Windows 10 1703+
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(-4)  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        )
    except Exception:
        try:  # Windows 8.1+
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    _dpi_set = True


def _display_scale() -> float:
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        LOGPIXELSX = 88
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, LOGPIXELSX)
        ctypes.windll.user32.ReleaseDC(0, hdc)
        return round(dpi / 96.0, 4) if dpi else 1.0
    except Exception:
        return 1.0


class WindowsScreen:
    """Concrete :class:`~operator.screen.base.ScreenBackend` for Windows."""

    def __init__(self, monitor_index: int = 1) -> None:
        set_dpi_awareness()
        import mss  # noqa: PLC0415  (lazy: Windows path only)

        self._sct = mss.mss()
        self._monitor_index = monitor_index

    def _monitor(self) -> dict:
        return self._sct.monitors[self._monitor_index]

    def geometry(self) -> ScreenGeometry:
        m = self._monitor()
        return ScreenGeometry(
            width=m["width"], height=m["height"], scale=_display_scale(),
            left=m["left"], top=m["top"],
        )

    def capture(self, max_width: int) -> CaptureResult:
        geom = self.geometry()
        shot = self._sct.grab(self._monitor())
        im = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        png, w, h = downscale_png(buf.getvalue(), max_width)
        return CaptureResult(png=png, geometry=geom, sent_width=w, sent_height=h)

    def foreground_window_title(self) -> str:
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value
        except Exception:
            return ""


def make_windows_screen(monitor_index: int = 1) -> WindowsScreen:
    return WindowsScreen(monitor_index=monitor_index)
