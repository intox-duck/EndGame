from __future__ import annotations

import operator_app.secrets_store as ss
from operator_app.setup_wizard import (
    SetupPaths,
    ensure_files,
    needs_api_key,
    store_api_key,
)


class FakeKeyring:
    def __init__(self):
        self.store = {}

    def get_password(self, service, name):
        return self.store.get((service, name))

    def set_password(self, service, name, value):
        self.store[(service, name)] = value

    def delete_password(self, service, name):
        self.store.pop((service, name), None)


def test_api_key_env_takes_precedence(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "from-env")
    assert ss.get_api_key() == "from-env"


def test_api_key_from_keyring(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    fake = FakeKeyring()
    fake.set_password(ss.SERVICE, ss.API_KEY_ENTRY, "from-keyring")
    monkeypatch.setattr(ss, "_keyring", lambda: fake)
    assert ss.get_api_key() == "from-keyring"


def test_set_api_key_stores(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(ss, "_keyring", lambda: fake)
    ss.set_api_key("abc123")
    assert fake.store[(ss.SERVICE, ss.API_KEY_ENTRY)] == "abc123"


def test_set_empty_key_rejected(monkeypatch):
    monkeypatch.setattr(ss, "_keyring", lambda: FakeKeyring())
    import pytest
    with pytest.raises(ValueError):
        ss.set_api_key("   ")


def test_no_keyring_backend_raises(monkeypatch):
    monkeypatch.setattr(ss, "_keyring", lambda: None)
    import pytest
    with pytest.raises(RuntimeError):
        ss.set_api_key("abc")


def test_looks_like_free_tier():
    assert ss.looks_like_free_tier("")
    assert ss.looks_like_free_tier("changeme")
    assert not ss.looks_like_free_tier("AIzaSyRealLookingKey")


def test_needs_api_key_false_for_vertex(monkeypatch):
    assert needs_api_key("vertex") is False


def test_needs_api_key_true_when_absent(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(ss, "_keyring", lambda: FakeKeyring())
    assert needs_api_key("api_key") is True


def test_store_api_key_rejects_placeholder(monkeypatch):
    monkeypatch.setattr(ss, "_keyring", lambda: FakeKeyring())
    import pytest
    with pytest.raises(ValueError):
        store_api_key("free")


def test_ensure_files_copies_from_examples(tmp_path):
    (tmp_path / "config.example.toml").write_text("x=1\n")
    (tmp_path / "profile.example.toml").write_text("[identity]\nname='Y'\n")
    paths = SetupPaths(
        config=tmp_path / "config.toml",
        config_example=tmp_path / "config.example.toml",
        profile=tmp_path / "profile.toml",
        profile_example=tmp_path / "profile.example.toml",
    )
    created = ensure_files(paths)
    assert (tmp_path / "config.toml").exists()
    assert (tmp_path / "profile.toml").exists()
    assert len(created) == 2
    # Idempotent: second call creates nothing.
    assert ensure_files(paths) == []
