"""Configuration loading: TOML files, env var overrides, merge logic.

Discovery order (later overrides earlier):
    1. Built-in defaults (Pydantic model defaults)
    2. User config: ``~/.config/duh/config.toml``
    3. Project-local config: ``./duh.toml``
    4. ``$DUH_CONFIG`` environment variable (explicit path)
    5. Programmatic overrides (passed to ``load_config``)

Environment variable overrides for provider API keys:
    Each provider's ``api_key_env`` field names an env var (e.g.
    ``ANTHROPIC_API_KEY``).  If the env var is set *and* ``api_key``
    is not already provided, the loader resolves it automatically.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from duh.core.errors import ConfigError

from .schema import DuhConfig


def _user_config_path() -> Path:
    """Return XDG-compliant user config path."""
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "duh" / "config.toml"


def _project_config_path() -> Path:
    """Return project-local config path."""
    return Path.cwd() / "duh.toml"


def _discover_config_files() -> list[Path]:
    """Return config files in merge order (first = lowest priority)."""
    paths: list[Path] = []

    user = _user_config_path()
    if user.is_file():
        paths.append(user)

    project = _project_config_path()
    if project.is_file():
        paths.append(project)

    env_path = os.environ.get("DUH_CONFIG")
    if env_path:
        p = Path(env_path)
        if not p.is_file():
            msg = f"DUH_CONFIG points to non-existent file: {env_path}"
            raise ConfigError(msg)
        paths.append(p)

    return paths


def _read_toml(path: Path) -> dict[str, Any]:
    """Read and parse a TOML file."""
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        msg = f"Invalid TOML in {path}: {e}"
        raise ConfigError(msg) from e
    except OSError as e:
        msg = f"Cannot read config file {path}: {e}"
        raise ConfigError(msg) from e


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base. Override wins on conflicts."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _resolve_api_keys(config: DuhConfig) -> None:
    """Resolve API keys from environment variables (in-place)."""
    for provider in config.providers.values():
        if provider.api_key is None and provider.api_key_env:
            provider.api_key = os.environ.get(provider.api_key_env)


def load_config(
    path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> DuhConfig:
    """Load and validate configuration.

    Args:
        path: Explicit config file path (highest file priority).
        overrides: Dict of overrides merged last (highest overall priority).

    Returns:
        Validated DuhConfig instance.

    Raises:
        ConfigError: On invalid TOML, missing files, or validation failure.
    """
    merged: dict[str, Any] = {}

    # Discover and merge config files
    files = _discover_config_files()

    # Explicit path overrides DUH_CONFIG
    if path is not None:
        p = Path(path)
        if not p.is_file():
            msg = f"Config file not found: {path}"
            raise ConfigError(msg)
        files.append(p)

    for config_file in files:
        data = _read_toml(config_file)
        merged = _deep_merge(merged, data)

    # Apply programmatic overrides
    if overrides:
        merged = _deep_merge(merged, overrides)

    # Validate with Pydantic
    try:
        config = DuhConfig.model_validate(merged)
    except Exception as e:
        msg = f"Configuration validation failed: {e}"
        raise ConfigError(msg) from e

    # Resolve API keys from env vars
    _resolve_api_keys(config)

    return config
