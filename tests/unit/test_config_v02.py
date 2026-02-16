"""Tests for v0.2 config schema extensions."""

from __future__ import annotations

from duh.config.schema import (
    CodeExecutionConfig,
    DecomposeConfig,
    DuhConfig,
    TaxonomyConfig,
    ToolsConfig,
    VotingConfig,
    WebSearchConfig,
)

# ── New config model defaults ───────────────────────────────────────


class TestWebSearchConfig:
    def test_defaults(self) -> None:
        cfg = WebSearchConfig()
        assert cfg.backend == "duckduckgo"
        assert cfg.api_key is None
        assert cfg.max_results == 5


class TestCodeExecutionConfig:
    def test_defaults(self) -> None:
        cfg = CodeExecutionConfig()
        assert cfg.enabled is False
        assert cfg.timeout == 30
        assert cfg.max_output == 10_000


class TestToolsConfig:
    def test_defaults(self) -> None:
        cfg = ToolsConfig()
        assert cfg.enabled is False
        assert cfg.max_rounds == 5
        assert cfg.web_search.backend == "duckduckgo"
        assert cfg.code_execution.enabled is False


class TestVotingConfig:
    def test_defaults(self) -> None:
        cfg = VotingConfig()
        assert cfg.enabled is False
        assert cfg.aggregation == "majority"


class TestDecomposeConfig:
    def test_defaults(self) -> None:
        cfg = DecomposeConfig()
        assert cfg.max_subtasks == 7
        assert cfg.parallel is True


class TestTaxonomyConfig:
    def test_defaults(self) -> None:
        cfg = TaxonomyConfig()
        assert cfg.enabled is False
        assert cfg.model_ref == ""


# ── GeneralConfig extensions ────────────────────────────────────────


class TestGeneralConfigExtensions:
    def test_protocol_default(self) -> None:
        cfg = DuhConfig()
        assert cfg.general.protocol == "consensus"

    def test_decompose_default(self) -> None:
        cfg = DuhConfig()
        assert cfg.general.decompose is False


# ── DuhConfig integration ──────────────────────────────────────────


class TestDuhConfigV02:
    def test_new_sections_present(self) -> None:
        cfg = DuhConfig()
        assert isinstance(cfg.tools, ToolsConfig)
        assert isinstance(cfg.voting, VotingConfig)
        assert isinstance(cfg.decompose, DecomposeConfig)
        assert isinstance(cfg.taxonomy, TaxonomyConfig)

    def test_backward_compatible(self) -> None:
        """v0.1 configs still work with new defaults."""
        cfg = DuhConfig()
        # v0.1 fields unchanged
        assert cfg.general.max_rounds == 3
        assert cfg.cost.hard_limit == 10.00
        assert "anthropic" in cfg.providers
        # v0.2 fields have safe defaults
        assert cfg.tools.enabled is False
        assert cfg.voting.enabled is False
        assert cfg.taxonomy.enabled is False
