"""Provider interface.

A provider runs one model conversation. The agent loop calls :meth:`start` once
with the task, playbook and first screenshot, then :meth:`continue_` with the
results of executing each returned step, until a step reports ``done``.

Providers convert model coordinates to physical pixels themselves (via
:mod:`operator.screen`) so every :class:`~operator.types.Action` they emit is
already in physical-pixel space.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from operator_app.screen.base import ScreenGeometry
from operator_app.types import ActionResult, Step


class ProviderError(Exception):
    pass


@runtime_checkable
class Provider(Protocol):
    """The contract every provider implements."""

    #: The model id actually in use after any availability fallback.
    active_model: str

    def start(
        self,
        *,
        task: str,
        system_instruction: str,
        screenshot_png: bytes,
        geometry: ScreenGeometry,
    ) -> Step:
        """Begin a run and return the first :class:`Step`."""
        ...

    def continue_(self, results: list[ActionResult]) -> Step:
        """Feed executed-action results (incl. new screenshot) and get the next Step."""
        ...
