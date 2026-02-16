"""Pydantic models for duh configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    """Configuration for a single LLM provider."""

    enabled: bool = True
    api_key: str | None = None
    api_key_env: str | None = None
    base_url: str | None = None
    default_model: str | None = None
    models: list[str] = Field(default_factory=list)
    display_name: str | None = None


class ConsensusConfig(BaseModel):
    """Configuration for the consensus protocol."""

    panel: list[str] = Field(default_factory=list)
    proposer_strategy: str = "round_robin"
    challenge_types: list[str] = Field(
        default_factory=lambda: ["flaw", "alternative", "risk", "devils_advocate"]
    )
    min_challengers: int = 2


class CostConfig(BaseModel):
    """Cost tracking and limits."""

    warn_threshold: float = 1.00
    hard_limit: float = 10.00
    show_running_cost: bool = True


class DatabaseConfig(BaseModel):
    """Database connection settings."""

    url: str = "sqlite+aiosqlite:///~/.local/share/duh/duh.db"


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    file: str = ""
    structured: bool = False


class GeneralConfig(BaseModel):
    """General engine settings."""

    max_rounds: int = 3
    decomposer_model: str = ""
    summary_model: str = ""
    stream_output: bool = True


class DuhConfig(BaseModel):
    """Top-level configuration for duh."""

    general: GeneralConfig = Field(default_factory=GeneralConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    cost: CostConfig = Field(default_factory=CostConfig)
    providers: dict[str, ProviderConfig] = Field(
        default_factory=lambda: {
            "anthropic": ProviderConfig(api_key_env="ANTHROPIC_API_KEY"),
            "openai": ProviderConfig(api_key_env="OPENAI_API_KEY"),
        }
    )
    consensus: ConsensusConfig = Field(default_factory=ConsensusConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
