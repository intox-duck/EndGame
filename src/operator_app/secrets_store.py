"""Secret storage. On Windows this uses the Credential Manager (via ``keyring``,
which is DPAPI-backed); everywhere it falls back to environment variables.

The Gemini API key is a credential: it is NEVER written to a config file, a log,
or baked into the binary. The setup wizard stores it here; the provider reads it
back here.
"""

from __future__ import annotations

import os

SERVICE = "operator-app"
API_KEY_ENTRY = "gemini_api_key"

# Environment variables checked before the keyring, so CI / power users can inject.
_ENV_KEYS = ("GOOGLE_API_KEY", "GEMINI_API_KEY")


def _keyring():
    """Return the keyring module, or None if unavailable (e.g. headless CI)."""
    try:
        import keyring  # noqa: PLC0415

        return keyring
    except Exception:
        return None


def get_api_key() -> str | None:
    """Return the Gemini API key from the environment, else the OS keyring."""
    for name in _ENV_KEYS:
        val = os.environ.get(name)
        if val:
            return val
    kr = _keyring()
    if kr is None:
        return None
    try:
        return kr.get_password(SERVICE, API_KEY_ENTRY)
    except Exception:
        return None


def set_api_key(key: str) -> None:
    """Store the Gemini API key in the OS keyring.

    Raises RuntimeError if no keyring backend is available, so the caller can tell
    the user to set an environment variable instead of silently losing the key.
    """
    if not key or not key.strip():
        raise ValueError("Refusing to store an empty API key.")
    kr = _keyring()
    if kr is None:
        raise RuntimeError(
            "No OS keyring backend available. Set the GOOGLE_API_KEY environment "
            "variable instead."
        )
    kr.set_password(SERVICE, API_KEY_ENTRY, key.strip())


def delete_api_key() -> None:
    kr = _keyring()
    if kr is None:
        return
    try:
        kr.delete_password(SERVICE, API_KEY_ENTRY)
    except Exception:
        pass


def looks_like_free_tier(key: str) -> bool:
    """Best-effort guard. We cannot verify tier offline, so this only catches the
    obvious empty/placeholder cases; real tier enforcement happens at first call.
    """
    return not key or key.strip().lower() in {"", "free", "test", "changeme"}
