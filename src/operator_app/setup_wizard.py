"""First-run setup.

Ensures ``config.toml`` and ``profile.toml`` exist (copied from the shipped
examples), and that a Gemini API key is stored — prompting for it once via a small
Qt dialog when auth is ``api_key`` and none is found. The key goes to the OS
keyring, never to disk.

``ensure_setup`` runs headlessly except for the one key prompt; the Qt import is
lazy so the module can be imported (and unit-tested) without a display.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from operator_app import secrets_store


def _resource(name: str) -> Path:
    """Find a shipped example file: prefer the working dir, then the PyInstaller
    bundle (sys._MEIPASS), then the installed package's parent.
    """
    cwd = Path(name)
    if cwd.exists():
        return cwd
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidate = Path(base) / name
        if candidate.exists():
            return candidate
    return cwd  # may not exist; caller handles absence


@dataclass
class SetupPaths:
    config: Path = Path("config.toml")
    config_example: Path = Path("config.example.toml")
    profile: Path = Path("profile.toml")
    profile_example: Path = Path("profile.example.toml")


def ensure_files(paths: SetupPaths | None = None) -> list[str]:
    """Create config.toml / profile.toml from examples if missing.

    Returns the list of files that were created (for the caller to report).
    """
    paths = paths or SetupPaths()
    created: list[str] = []
    for target, example in (
        (paths.config, paths.config_example),
        (paths.profile, paths.profile_example),
    ):
        source = _resource(str(example))
        if not target.exists() and source.exists():
            shutil.copyfile(source, target)
            created.append(str(target))
    return created


def needs_api_key(auth: str) -> bool:
    """True if we must prompt: api_key auth selected and no key stored anywhere."""
    if auth != "api_key":
        return False
    return not secrets_store.get_api_key()


def store_api_key(key: str) -> None:
    """Validate lightly and store the key in the OS keyring."""
    if secrets_store.looks_like_free_tier(key):
        raise ValueError(
            "That looks like an empty or placeholder key. A paid-tier Gemini API "
            "key is required (the free tier is refused)."
        )
    secrets_store.set_api_key(key)


def prompt_for_api_key() -> str | None:  # pragma: no cover - needs Qt/display
    """Show a modal dialog asking for the API key. Returns the key or None."""
    from PySide6 import QtWidgets

    owns_app = QtWidgets.QApplication.instance() is None
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    key, ok = QtWidgets.QInputDialog.getText(
        None,
        "Operator setup",
        "Paste your PAID-tier Gemini API key.\n"
        "It is stored in Windows Credential Manager, never on disk.\n"
        "(Leave blank to cancel and use Vertex AI / an env var instead.)",
        QtWidgets.QLineEdit.Password,
    )
    if owns_app:
        app.quit()
    if not ok or not key.strip():
        return None
    return key.strip()


def ensure_setup(auth: str, paths: SetupPaths | None = None) -> list[str]:
    """Full first-run flow. Returns notes about what happened, for logging."""
    notes = []
    created = ensure_files(paths)
    if created:
        notes.append("Created: " + ", ".join(created))
    if needs_api_key(auth):
        key = prompt_for_api_key()
        if key:
            store_api_key(key)
            notes.append("Stored Gemini API key in the OS keyring.")
        else:
            notes.append("No API key entered; set GOOGLE_API_KEY or use Vertex auth.")
    return notes
