"""Shared pytest configuration: skip Windows-only tests off Windows."""

from __future__ import annotations

import sys

import pytest


def pytest_collection_modifyitems(config, items):
    if sys.platform.startswith("win"):
        return
    skip_windows = pytest.mark.skip(reason="requires a real Windows desktop")
    for item in items:
        if "windows" in item.keywords:
            item.add_marker(skip_windows)
