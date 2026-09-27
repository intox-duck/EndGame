"""Coordinate mapping is the #1 bug source, so it gets the most tests:
multiple resolutions and 100/125/150% scaling, plus round-trips and clamping.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from operator_app.screen.base import (
    FakeScreen,
    ScreenGeometry,
    downscale_png,
    model_to_physical,
    physical_to_model,
)

RESOLUTIONS = [
    (1920, 1080, 1.0),
    (1920, 1080, 1.25),
    (2560, 1440, 1.5),
    (3840, 2160, 1.5),
    (1366, 768, 1.0),
]


@pytest.mark.parametrize("w,h,scale", RESOLUTIONS)
def test_corners_map_to_physical_corners(w, h, scale):
    geom = ScreenGeometry(w, h, scale)
    assert model_to_physical(0, 0, geom) == (0, 0)
    assert model_to_physical(999, 999, geom) == (w - 1, h - 1)


@pytest.mark.parametrize("w,h,scale", RESOLUTIONS)
def test_centre_maps_near_centre(w, h, scale):
    geom = ScreenGeometry(w, h, scale)
    px, py = model_to_physical(500, 500, geom)
    # 500 is not exactly the centre of 0..999, so allow a couple of pixels on
    # large displays where the half-step rounds up.
    assert abs(px - (w - 1) / 2) <= 2
    assert abs(py - (h - 1) / 2) <= 2


def test_multi_monitor_offset_applied():
    geom = ScreenGeometry(1920, 1080, 1.0, left=-1920, top=0)
    assert model_to_physical(0, 0, geom) == (-1920, 0)
    assert model_to_physical(999, 0, geom) == (-1, 0)


def test_out_of_range_is_clamped():
    geom = ScreenGeometry(1920, 1080)
    assert model_to_physical(-50, -50, geom) == (0, 0)
    assert model_to_physical(5000, 5000, geom) == (1919, 1079)


@pytest.mark.parametrize("w,h,scale", RESOLUTIONS)
def test_round_trip_is_close(w, h, scale):
    geom = ScreenGeometry(w, h, scale)
    for mx, my in [(100, 100), (250, 750), (999, 0), (0, 999)]:
        px, py = model_to_physical(mx, my, geom)
        rx, ry = physical_to_model(px, py, geom)
        assert abs(rx - mx) <= 1
        assert abs(ry - my) <= 1


def test_coord_max_validation():
    with pytest.raises(ValueError):
        model_to_physical(1, 1, ScreenGeometry(100, 100), coord_max=0)


def _png(w, h):
    im = Image.new("RGB", (w, h), (10, 20, 30))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_downscale_reduces_width():
    png, w, h = downscale_png(_png(1920, 1080), 1280)
    assert w == 1280
    assert h == 720  # aspect preserved


def test_downscale_leaves_small_images():
    png, w, h = downscale_png(_png(800, 600), 1280)
    assert (w, h) == (800, 600)


def test_fake_screen_capture_is_downscaled():
    screen = FakeScreen(ScreenGeometry(1920, 1080))
    cap = screen.capture(1280)
    assert cap.sent_width == 1280
    assert cap.geometry.width == 1920
    assert screen.capture_count == 1
