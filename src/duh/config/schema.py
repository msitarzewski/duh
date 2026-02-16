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


class WebSearchConfig(BaseModel):
    """Web search tool configuration."""

    backend: str = "duckduckgo"
    api_key: str | None = None
    max_results: int = 5


class CodeExecutionConfig(BaseModel):
    """Code execution tool configuration."""

    enabled: bool = False
    timeout: int = 30
    max_output: int = 10_000


class ToolsConfig(BaseModel):
    """Tool framework configuration."""

    enabled: bool = False
    max_rounds: int = 5
    web_search: WebSearchConfig = Field(default_factory=WebSearchConfig)
    code_execution: CodeExecutionConfig = Field(default_factory=CodeExecutionConfig)


class VotingConfig(BaseModel):
    """Voting protocol configuration."""

    enabled: bool = False
    aggregation: str = "majority"


class DecomposeConfig(BaseModel):
    """Query decomposition configuration."""

    max_subtasks: int = 7
    parallel: bool = True


class TaxonomyConfig(BaseModel):
    """Decision taxonomy classification configuration."""

    enabled: bool = False
    model_ref: str = ""


class GeneralConfig(BaseModel):
    """General engine settings."""

    max_rounds: int = 3
    decomposer_model: str = ""
    summary_model: str = ""
    stream_output: bool = True
    protocol: str = "consensus"
    decompose: bool = False


class DuhConfig(BaseModel):
    """Top-level configuration for duh."""

    general: GeneralConfig = Field(default_factory=GeneralConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    cost: CostConfig = Field(default_factory=CostConfig)
    providers: dict[str, ProviderConfig] = Field(
        default_factory=lambda: {
            "anthropic": ProviderConfig(api_key_env="ANTHROPIC_API_KEY"),
            "openai": ProviderConfig(api_key_env="OPENAI_API_KEY"),
            "google": ProviderConfig(api_key_env="GOOGLE_API_KEY"),
        }
    )
    consensus: ConsensusConfig = Field(default_factory=ConsensusConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    voting: VotingConfig = Field(default_factory=VotingConfig)
    decompose: DecomposeConfig = Field(default_factory=DecomposeConfig)
    taxonomy: TaxonomyConfig = Field(default_factory=TaxonomyConfig)
