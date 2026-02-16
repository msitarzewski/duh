"""Tests for configuration loading and validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from duh.config.loader import _deep_merge, load_config
from duh.config.schema import (
    ConsensusConfig,
    CostConfig,
    DatabaseConfig,
    DuhConfig,
    GeneralConfig,
    LoggingConfig,
    ProviderConfig,
)
from duh.core.errors import ConfigError

# ─── Schema Defaults ──────────────────────────────────────────


class TestSchemaDefaults:
    def test_duh_config_all_defaults(self):
        cfg = DuhConfig()
        assert cfg.general.max_rounds == 3
        assert cfg.general.stream_output is True
        assert cfg.database.url == "sqlite+aiosqlite:///~/.local/share/duh/duh.db"
        assert cfg.cost.warn_threshold == 1.00
        assert cfg.cost.hard_limit == 10.00
        assert "anthropic" in cfg.providers
        assert "openai" in cfg.providers
        assert cfg.providers["anthropic"].api_key_env == "ANTHROPIC_API_KEY"
        assert cfg.providers["openai"].api_key_env == "OPENAI_API_KEY"
        assert cfg.consensus.proposer_strategy == "round_robin"
        assert cfg.logging.level == "INFO"

    def test_general_config_defaults(self):
        cfg = GeneralConfig()
        assert cfg.max_rounds == 3
        assert cfg.decomposer_model == ""
        assert cfg.summary_model == ""
        assert cfg.stream_output is True

    def test_cost_config_defaults(self):
        cfg = CostConfig()
        assert cfg.warn_threshold == 1.00
        assert cfg.hard_limit == 10.00
        assert cfg.show_running_cost is True

    def test_database_config_defaults(self):
        cfg = DatabaseConfig()
        assert "sqlite" in cfg.url

    def test_consensus_config_defaults(self):
        cfg = ConsensusConfig()
        assert cfg.panel == []
        assert cfg.proposer_strategy == "round_robin"
        assert "flaw" in cfg.challenge_types
        assert "devils_advocate" in cfg.challenge_types
        assert cfg.min_challengers == 2

    def test_logging_config_defaults(self):
        cfg = LoggingConfig()
        assert cfg.level == "INFO"
        assert cfg.file == ""
        assert cfg.structured is False

    def test_provider_config_defaults(self):
        cfg = ProviderConfig()
        assert cfg.enabled is True
        assert cfg.api_key is None
        assert cfg.api_key_env is None
        assert cfg.base_url is None
        assert cfg.models == []


# ─── Schema Validation ────────────────────────────────────────


class TestSchemaValidation:
    def test_provider_config_with_values(self):
        cfg = ProviderConfig(
            enabled=True,
            api_key_env="ANTHROPIC_API_KEY",
            default_model="claude-sonnet-4-5-20250929",
            models=["claude-opus-4-6", "claude-sonnet-4-5-20250929"],
        )
        assert cfg.api_key_env == "ANTHROPIC_API_KEY"
        assert len(cfg.models) == 2

    def test_duh_config_from_dict(self):
        data = {
            "general": {"max_rounds": 5},
            "cost": {"hard_limit": 50.0},
            "providers": {
                "anthropic": {
                    "api_key_env": "ANTHROPIC_API_KEY",
                    "default_model": "claude-opus-4-6",
                }
            },
        }
        cfg = DuhConfig.model_validate(data)
        assert cfg.general.max_rounds == 5
        assert cfg.cost.hard_limit == 50.0
        assert "anthropic" in cfg.providers
        assert cfg.providers["anthropic"].api_key_env == "ANTHROPIC_API_KEY"

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            DuhConfig.model_validate({"general": {"max_rounds": "not_a_number"}})

    def test_extra_fields_ignored_by_default(self):
        """Unknown keys in TOML should not crash config loading."""
        cfg = DuhConfig.model_validate({"unknown_section": {"foo": "bar"}})
        assert cfg.general.max_rounds == 3  # defaults preserved


# ─── Deep Merge ───────────────────────────────────────────────


class TestDeepMerge:
    def test_flat_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"general": {"max_rounds": 3, "stream_output": True}}
        override = {"general": {"max_rounds": 5}}
        result = _deep_merge(base, override)
        assert result["general"]["max_rounds"] == 5
        assert result["general"]["stream_output"] is True

    def test_override_replaces_non_dict(self):
        base = {"key": "old"}
        override = {"key": "new"}
        result = _deep_merge(base, override)
        assert result["key"] == "new"

    def test_base_unchanged(self):
        base = {"a": 1}
        override = {"a": 2}
        _deep_merge(base, override)
        assert base["a"] == 1  # original not mutated


# ─── TOML Loading ─────────────────────────────────────────────


class TestLoadConfig:
    def test_defaults_when_no_files(self, tmp_path, monkeypatch):
        """With no config files, returns all defaults."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("DUH_CONFIG", raising=False)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        cfg = load_config()
        assert cfg.general.max_rounds == 3
        assert "anthropic" in cfg.providers
        assert "openai" in cfg.providers

    def test_load_from_explicit_path(self, tmp_path):
        toml_file = tmp_path / "test.toml"
        toml_file.write_text("[general]\nmax_rounds = 7\n\n[cost]\nhard_limit = 25.0\n")
        cfg = load_config(path=toml_file)
        assert cfg.general.max_rounds == 7
        assert cfg.cost.hard_limit == 25.0
        assert cfg.general.stream_output is True  # default preserved

    def test_load_with_providers(self, tmp_path):
        toml_file = tmp_path / "test.toml"
        toml_file.write_text(
            "[providers.anthropic]\n"
            'api_key_env = "ANTHROPIC_API_KEY"\n'
            'default_model = "claude-opus-4-6"\n'
        )
        cfg = load_config(path=toml_file)
        assert "anthropic" in cfg.providers
        assert cfg.providers["anthropic"].default_model == "claude-opus-4-6"

    def test_explicit_path_not_found_raises(self, tmp_path):
        with pytest.raises(ConfigError, match="not found"):
            load_config(path=tmp_path / "nonexistent.toml")

    def test_invalid_toml_raises(self, tmp_path):
        bad = tmp_path / "bad.toml"
        bad.write_text("[invalid\n")
        with pytest.raises(ConfigError, match="Invalid TOML"):
            load_config(path=bad)

    def test_overrides_applied(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("DUH_CONFIG", raising=False)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        cfg = load_config(overrides={"general": {"max_rounds": 10}})
        assert cfg.general.max_rounds == 10

    def test_overrides_beat_file(self, tmp_path):
        toml_file = tmp_path / "test.toml"
        toml_file.write_text("[general]\nmax_rounds = 5\n")
        cfg = load_config(path=toml_file, overrides={"general": {"max_rounds": 99}})
        assert cfg.general.max_rounds == 99


# ─── Environment Variables ────────────────────────────────────


class TestEnvVarOverrides:
    def test_duh_config_env_path(self, tmp_path, monkeypatch):
        toml_file = tmp_path / "env.toml"
        toml_file.write_text("[general]\nmax_rounds = 12\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("DUH_CONFIG", str(toml_file))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        cfg = load_config()
        assert cfg.general.max_rounds == 12

    def test_duh_config_env_missing_file_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("DUH_CONFIG", str(tmp_path / "nope.toml"))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        with pytest.raises(ConfigError, match="non-existent"):
            load_config()

    def test_api_key_resolved_from_env(self, tmp_path, monkeypatch):
        toml_file = tmp_path / "test.toml"
        toml_file.write_text(
            '[providers.anthropic]\napi_key_env = "ANTHROPIC_API_KEY"\n'
        )
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key-123")
        cfg = load_config(path=toml_file)
        assert cfg.providers["anthropic"].api_key == "sk-test-key-123"

    def test_api_key_not_overwritten_if_set(self, tmp_path, monkeypatch):
        toml_file = tmp_path / "test.toml"
        toml_file.write_text(
            "[providers.anthropic]\n"
            'api_key = "sk-explicit"\n'
            'api_key_env = "ANTHROPIC_API_KEY"\n'
        )
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
        cfg = load_config(path=toml_file)
        assert cfg.providers["anthropic"].api_key == "sk-explicit"

    def test_api_key_none_when_env_not_set(self, tmp_path, monkeypatch):
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('[providers.anthropic]\napi_key_env = "MISSING_KEY_VAR"\n')
        monkeypatch.delenv("MISSING_KEY_VAR", raising=False)
        cfg = load_config(path=toml_file)
        assert cfg.providers["anthropic"].api_key is None


# ─── File Discovery ───────────────────────────────────────────


class TestFileDiscovery:
    def test_project_local_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("DUH_CONFIG", raising=False)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        (tmp_path / "duh.toml").write_text("[general]\nmax_rounds = 8\n")
        cfg = load_config()
        assert cfg.general.max_rounds == 8

    def test_user_config_xdg(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        monkeypatch.delenv("DUH_CONFIG", raising=False)

        xdg_dir = tmp_path / "xdg" / "duh"
        xdg_dir.mkdir(parents=True)
        (xdg_dir / "config.toml").write_text("[cost]\nhard_limit = 99.0\n")

        cfg = load_config()
        assert cfg.cost.hard_limit == 99.0

    def test_project_overrides_user(self, tmp_path, monkeypatch):
        """Project-local config takes precedence over user config."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        monkeypatch.delenv("DUH_CONFIG", raising=False)

        xdg_dir = tmp_path / "xdg" / "duh"
        xdg_dir.mkdir(parents=True)
        (xdg_dir / "config.toml").write_text("[general]\nmax_rounds = 2\n")
        (tmp_path / "duh.toml").write_text("[general]\nmax_rounds = 9\n")

        cfg = load_config()
        assert cfg.general.max_rounds == 9

    def test_merge_preserves_non_overlapping(self, tmp_path, monkeypatch):
        """Non-overlapping sections merge together."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        monkeypatch.delenv("DUH_CONFIG", raising=False)

        xdg_dir = tmp_path / "xdg" / "duh"
        xdg_dir.mkdir(parents=True)
        (xdg_dir / "config.toml").write_text("[cost]\nhard_limit = 50.0\n")
        (tmp_path / "duh.toml").write_text("[general]\nmax_rounds = 6\n")

        cfg = load_config()
        assert cfg.cost.hard_limit == 50.0
        assert cfg.general.max_rounds == 6
