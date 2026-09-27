"""Configuration loading: ``config.toml`` + ``.env``.

Secrets come only from the environment / ``.env`` and are never written to logs.
The free tier is refused at load time (it may be used for training).
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(Exception):
    """Raised for invalid or unsafe configuration."""


@dataclass(frozen=True)
class ModelPrice:
    """Per-million-token prices, in the config's currency (default USD)."""

    input: float
    output: float
    cached_input: float


_DEFAULT_PRICES = {
    # From docs/RESEARCH_NOTES.md. gemini-3.8-flash price is a placeholder (⚠).
    "gemini-3.8-flash": ModelPrice(1.50, 9.00, 0.15),
    "gemini-3.5-flash": ModelPrice(1.50, 9.00, 0.15),
    "claude-sonnet-5": ModelPrice(2.00, 10.00, 0.20),
    "claude-opus-5.5": ModelPrice(4.00, 20.00, 0.20),
}


@dataclass(frozen=True)
class Config:
    # --- provider / auth ---
    provider: str = "gemini"
    auth: str = "vertex"                    # "vertex" | "api_key"
    tier: str = "paid"                      # "paid" | "free" (free is refused)
    project: str = ""                       # GCP project (vertex)
    location: str = "europe-west2"
    location_fallback: str = "global"
    preferred_model: str = "gemini-3.8-flash"
    fallback_model: str = "gemini-3.5-flash"

    # --- loop caps ---
    max_steps: int = 150
    max_cost_per_run: float = 3.0
    max_runtime_seconds: float = 1800.0
    screenshots_in_context: int = 3
    settle_delay_seconds: float = 0.4

    # --- screen ---
    monitor_index: int = 1                  # mss: 1 = primary
    max_image_width: int = 1280

    # --- currency + prices (per million tokens) ---
    currency: str = "USD"
    prices: dict[str, ModelPrice] = field(default_factory=lambda: dict(_DEFAULT_PRICES))

    # --- guard ---
    confirm_keywords: tuple[str, ...] = (
        "send", "submit", "post", "publish", "delete", "remove", "pay",
        "purchase", "confirm", "apply", "connect", "message", "inmail",
    )
    window_allowlist: tuple[str, ...] = ()   # empty = allow all (subject to blocklist)

    # --- privacy ---
    # Default flips PROMPT.md: Outlook/Teams are intended targets, so they are
    # NOT capture-blocked. Banking + password managers stay hard-blocked.
    capture_blocklist: tuple[str, ...] = (
        "1password", "bitwarden", "keepass", "lastpass", "dashlane",
        "banking", "barclays", "hsbc", "lloyds", "nationwide", "natwest",
        "monzo", "starling", "revolut",
    )
    redaction_regions: tuple[tuple[int, int, int, int], ...] = ()  # (x,y,w,h)
    screenshot_retention_days: int = 7

    # --- paths ---
    logs_dir: str = "logs"
    recordings_dir: str = "recordings"

    def price_for(self, model: str) -> ModelPrice:
        if model in self.prices:
            return self.prices[model]
        raise ConfigError(
            f"No price configured for model {model!r}. Add it under [prices] in "
            f"config.toml (prices live in config, not code)."
        )


def _load_env(env_path: Path) -> None:
    """Minimal .env loader (KEY=VALUE lines). Does not overwrite real env vars."""
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_config(
    config_path: str | Path = "config.toml",
    env_path: str | Path = ".env",
    *,
    load_env: bool = True,
) -> Config:
    """Load and validate configuration.

    Raises :class:`ConfigError` if the config selects the free tier.
    """
    if load_env:
        _load_env(Path(env_path))

    data: dict = {}
    cfg_path = Path(config_path)
    if cfg_path.exists():
        data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))

    prices: dict[str, ModelPrice] = dict(_DEFAULT_PRICES)
    for name, row in (data.get("prices") or {}).items():
        prices[name] = ModelPrice(
            float(row["input"]), float(row["output"]),
            float(row.get("cached_input", row.get("cached", 0.0))),
        )

    provider = data.get("provider", {})
    loop = data.get("loop", {})
    screen = data.get("screen", {})
    guard = data.get("guard", {})
    privacy = data.get("privacy", {})
    paths = data.get("paths", {})

    cfg = Config(
        provider=provider.get("name", "gemini"),
        auth=provider.get("auth", "vertex"),
        tier=provider.get("tier", "paid"),
        project=provider.get("project", ""),
        location=provider.get("location", "europe-west2"),
        location_fallback=provider.get("location_fallback", "global"),
        preferred_model=provider.get("preferred_model", "gemini-3.8-flash"),
        fallback_model=provider.get("fallback_model", "gemini-3.5-flash"),
        max_steps=int(loop.get("max_steps", 150)),
        max_cost_per_run=float(loop.get("max_cost_per_run", 3.0)),
        max_runtime_seconds=float(loop.get("max_runtime_seconds", 1800.0)),
        screenshots_in_context=int(loop.get("screenshots_in_context", 3)),
        settle_delay_seconds=float(loop.get("settle_delay_seconds", 0.4)),
        monitor_index=int(screen.get("monitor_index", 1)),
        max_image_width=int(screen.get("max_image_width", 1280)),
        currency=data.get("currency", "USD"),
        prices=prices,
        confirm_keywords=tuple(
            guard.get("confirm_keywords", list(Config.confirm_keywords))
        ),
        window_allowlist=tuple(guard.get("window_allowlist", [])),
        capture_blocklist=tuple(
            privacy.get("capture_blocklist", list(Config.capture_blocklist))
        ),
        redaction_regions=tuple(
            tuple(r) for r in privacy.get("redaction_regions", [])
        ),
        screenshot_retention_days=int(privacy.get("screenshot_retention_days", 7)),
        logs_dir=paths.get("logs_dir", "logs"),
        recordings_dir=paths.get("recordings_dir", "recordings"),
    )

    _validate(cfg)
    return cfg


def _validate(cfg: Config) -> None:
    if cfg.tier.lower() == "free":
        raise ConfigError(
            "Refusing to start on the FREE tier: free-tier requests may be used "
            "for training and human review, which is unacceptable for candidate "
            "data. Use Vertex AI (enterprise terms) or a PAID Gemini API key, and "
            "set tier = \"paid\" in config.toml."
        )
    if cfg.auth not in ("vertex", "api_key"):
        raise ConfigError(f"Unknown auth {cfg.auth!r}; expected 'vertex' or 'api_key'.")
    if cfg.auth == "vertex" and not cfg.project:
        # Not fatal here (project can come from GOOGLE_CLOUD_PROJECT), but warn early.
        if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
            raise ConfigError(
                "Vertex AI auth selected but no project set. Set provider.project "
                "in config.toml or GOOGLE_CLOUD_PROJECT in the environment."
            )
