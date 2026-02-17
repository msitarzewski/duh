"""Tests for v0.3 config schema extensions (API configuration)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from duh.config.loader import load_config
from duh.config.schema import APIConfig, DuhConfig

# ── APIConfig defaults ─────────────────────────────────────────────


class TestAPIConfigDefaults:
    def test_host_default(self) -> None:
        cfg = APIConfig()
        assert cfg.host == "127.0.0.1"

    def test_port_default(self) -> None:
        cfg = APIConfig()
        assert cfg.port == 8080

    def test_cors_origins_default(self) -> None:
        cfg = APIConfig()
        assert cfg.cors_origins == ["http://localhost:3000"]

    def test_rate_limit_default(self) -> None:
        cfg = APIConfig()
        assert cfg.rate_limit == 60

    def test_rate_limit_window_default(self) -> None:
        cfg = APIConfig()
        assert cfg.rate_limit_window == 60


# ── APIConfig overrides ───────────────────────────────────────────


class TestAPIConfigOverrides:
    def test_override_host(self) -> None:
        cfg = APIConfig(host="0.0.0.0")
        assert cfg.host == "0.0.0.0"

    def test_override_port(self) -> None:
        cfg = APIConfig(port=9090)
        assert cfg.port == 9090

    def test_override_cors_origins(self) -> None:
        origins = ["http://example.com", "https://app.example.com"]
        cfg = APIConfig(cors_origins=origins)
        assert cfg.cors_origins == origins

    def test_override_rate_limit(self) -> None:
        cfg = APIConfig(rate_limit=120, rate_limit_window=120)
        assert cfg.rate_limit == 120
        assert cfg.rate_limit_window == 120


# ── APIConfig validation ──────────────────────────────────────────


class TestAPIConfigValidation:
    def test_port_must_be_int(self) -> None:
        with pytest.raises(ValidationError):
            APIConfig.model_validate({"port": "not_a_number"})

    def test_host_must_be_string(self) -> None:
        with pytest.raises(ValidationError):
            APIConfig.model_validate({"host": 12345})

    def test_rate_limit_must_be_int(self) -> None:
        with pytest.raises(ValidationError):
            APIConfig.model_validate({"rate_limit": "fast"})

    def test_cors_origins_must_be_list(self) -> None:
        with pytest.raises(ValidationError):
            APIConfig.model_validate({"cors_origins": "not_a_list"})


# ── APIConfig from dict ───────────────────────────────────────────


class TestAPIConfigFromDict:
    def test_from_dict(self) -> None:
        data = {
            "host": "0.0.0.0",
            "port": 3000,
            "cors_origins": ["https://prod.example.com"],
            "rate_limit": 100,
            "rate_limit_window": 30,
        }
        cfg = APIConfig.model_validate(data)
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 3000
        assert cfg.cors_origins == ["https://prod.example.com"]
        assert cfg.rate_limit == 100
        assert cfg.rate_limit_window == 30


# ── DuhConfig integration ─────────────────────────────────────────


class TestDuhConfigAPIIntegration:
    def test_api_field_present(self) -> None:
        cfg = DuhConfig()
        assert isinstance(cfg.api, APIConfig)

    def test_api_defaults_in_duh_config(self) -> None:
        cfg = DuhConfig()
        assert cfg.api.host == "127.0.0.1"
        assert cfg.api.port == 8080
        assert cfg.api.cors_origins == ["http://localhost:3000"]
        assert cfg.api.rate_limit == 60
        assert cfg.api.rate_limit_window == 60

    def test_api_override_via_dict(self) -> None:
        data = {"api": {"host": "0.0.0.0", "port": 9090}}
        cfg = DuhConfig.model_validate(data)
        assert cfg.api.host == "0.0.0.0"
        assert cfg.api.port == 9090
        # Other defaults preserved
        assert cfg.api.cors_origins == ["http://localhost:3000"]

    def test_backward_compatible(self) -> None:
        """v0.1/v0.2 configs still work with new api defaults."""
        cfg = DuhConfig()
        assert cfg.general.max_rounds == 3
        assert cfg.cost.hard_limit == 10.00
        assert "anthropic" in cfg.providers
        assert cfg.tools.enabled is False
        assert cfg.api.host == "127.0.0.1"


# ── TOML loading integration ──────────────────────────────────────


class TestAPIConfigTOMLLoading:
    def test_load_api_from_toml(self, tmp_path) -> None:
        toml_file = tmp_path / "test.toml"
        toml_file.write_text(
            "[api]\n"
            'host = "0.0.0.0"\n'
            "port = 3000\n"
            'cors_origins = ["https://app.example.com"]\n'
            "rate_limit = 120\n"
        )
        cfg = load_config(path=toml_file)
        assert cfg.api.host == "0.0.0.0"
        assert cfg.api.port == 3000
        assert cfg.api.cors_origins == ["https://app.example.com"]
        assert cfg.api.rate_limit == 120
        # Default preserved for unset field
        assert cfg.api.rate_limit_window == 60

    def test_toml_merge_api_section(self, tmp_path, monkeypatch) -> None:
        """API section merges correctly with defaults via overrides."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("DUH_CONFIG", raising=False)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        cfg = load_config(overrides={"api": {"port": 4000}})
        assert cfg.api.port == 4000
        assert cfg.api.host == "127.0.0.1"  # default preserved

    def test_toml_api_does_not_affect_other_sections(self, tmp_path) -> None:
        toml_file = tmp_path / "test.toml"
        toml_file.write_text("[api]\nport = 9999\n")
        cfg = load_config(path=toml_file)
        assert cfg.api.port == 9999
        # Other sections unaffected
        assert cfg.general.max_rounds == 3
        assert cfg.cost.hard_limit == 10.00
