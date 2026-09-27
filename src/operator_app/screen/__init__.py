"""Screen capture and coordinate conversion.

The coordinate maths (normalised model space -> physical pixels) is the single
biggest source of bugs in a computer-use agent, so it lives here as pure
functions with no platform dependencies, and is unit-tested across resolutions
and DPI scales. The actual capture sits behind :class:`ScreenBackend` with a
:class:`FakeScreen` for tests and a Windows backend added in Phase 2.
"""

from operator_app.screen.base import (
    CaptureResult,
    FakeScreen,
    ScreenBackend,
    ScreenGeometry,
    downscale_png,
    model_to_physical,
    physical_to_model,
)

__all__ = [
    "CaptureResult",
    "FakeScreen",
    "ScreenBackend",
    "ScreenGeometry",
    "downscale_png",
    "model_to_physical",
    "physical_to_model",
]
