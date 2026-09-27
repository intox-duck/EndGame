from __future__ import annotations

import pytest

from operator_app.config import ConfigError, load_config


def test_free_tier_refused(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[provider]\ntier = "free"\nauth = "api_key"\n')
    with pytest.raises(ConfigError) as exc:
        load_config(cfg, tmp_path / ".env", load_env=False)
    assert "free" in str(exc.value).lower()


def test_api_key_auth_ok(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[provider]\ntier = "paid"\nauth = "api_key"\n')
    c = load_config(cfg, tmp_path / ".env", load_env=False)
    assert c.auth == "api_key"
    assert c.provider == "gemini"


def test_vertex_without_project_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    cfg = tmp_path / "config.toml"
    cfg.write_text('[provider]\nauth = "vertex"\ntier = "paid"\n')
    with pytest.raises(ConfigError):
        load_config(cfg, tmp_path / ".env", load_env=False)


def test_vertex_with_project_ok(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[provider]\nauth = "vertex"\ntier = "paid"\nproject = "my-proj"\n')
    c = load_config(cfg, tmp_path / ".env", load_env=False)
    assert c.project == "my-proj"


def test_prices_parsed_from_toml(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[provider]\nauth = "api_key"\ntier = "paid"\n'
        '[prices."gemini-3.8-flash"]\ninput = 2.0\noutput = 8.0\ncached_input = 0.2\n'
    )
    c = load_config(cfg, tmp_path / ".env", load_env=False)
    assert c.price_for("gemini-3.8-flash").input == 2.0


def test_defaults_present(tmp_path):
    # Default auth is vertex (which needs a project), so use api_key to reach the
    # happy path and assert the built-in defaults are populated.
    cfg = tmp_path / "c.toml"
    cfg.write_text('[provider]\nauth="api_key"\ntier="paid"\n')
    c = load_config(cfg, tmp_path / ".env", load_env=False)
    assert "gemini-3.5-flash" in c.prices
    assert c.max_steps == 150
    assert c.screenshot_retention_days == 7
