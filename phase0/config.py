"""Configuration and cost tracking for Phase 0 benchmark."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from pydantic import BaseModel


# Budget presets: (claude_model, gpt_model, judge_claude, judge_gpt)
BUDGETS = {
    "small": {
        "claude_model": "claude-sonnet-4-5-20250929",
        "gpt_model": "gpt-4o",
        "judge_gpt_model": "gpt-4o",
        "judge_claude_model": "claude-sonnet-4-5-20250929",
    },
    "full": {
        "claude_model": "claude-opus-4-6",
        "gpt_model": "gpt-5.2",
        "judge_gpt_model": "gpt-5.2",
        "judge_claude_model": "claude-opus-4-6",
    },
}


class BenchmarkConfig(BaseModel):
    """Configuration for the Phase 0 benchmark."""

    # Models — defaults are SOTA (full budget)
    claude_model: str = "claude-opus-4-6"
    gpt_model: str = "gpt-5.2"
    judge_gpt_model: str = "gpt-5.2"
    judge_claude_model: str = "claude-opus-4-6"

    # API keys (from env)
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Generation params
    max_tokens: int = 4096
    temperature: float = 0.7
    high_temperature: float = 1.0
    judge_temperature: float = 0.3

    # Benchmark params
    pilot_count: int = 5
    max_retries: int = 3
    retry_base_delay: float = 1.0

    # Paths
    results_dir: str = "results"

    def model_post_init(self, __context: object) -> None:
        if not self.anthropic_api_key:
            self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.openai_api_key:
            self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")

    @classmethod
    def with_budget(cls, budget: str, **overrides: object) -> "BenchmarkConfig":
        """Create config from a budget preset."""
        if budget not in BUDGETS:
            raise ValueError(f"Unknown budget '{budget}'. Choose from: {', '.join(BUDGETS)}")
        params = dict(BUDGETS[budget])
        params.update(overrides)
        return cls(**params)


# Pricing per 1M tokens (USD) as of early 2026
PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
    "gpt-5.2": {"input": 1.75, "output": 14.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}


@dataclass
class CostTracker:
    """Tracks API costs across all calls."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    calls: int = 0
    _by_model: dict[str, dict[str, float]] = field(default_factory=dict)

    def record(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Record token usage and return cost for this call."""
        pricing = PRICING.get(model, {"input": 5.0, "output": 15.0})
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost
        self.calls += 1

        if model not in self._by_model:
            self._by_model[model] = {"input_tokens": 0, "output_tokens": 0, "cost": 0.0, "calls": 0}
        self._by_model[model]["input_tokens"] += input_tokens
        self._by_model[model]["output_tokens"] += output_tokens
        self._by_model[model]["cost"] += cost
        self._by_model[model]["calls"] += 1

        return cost

    def summary(self) -> str:
        """Return a human-readable cost summary."""
        lines = [f"Total: ${self.total_cost_usd:.4f} ({self.calls} calls, {self.total_input_tokens + self.total_output_tokens:,} tokens)"]
        for model, stats in sorted(self._by_model.items()):
            lines.append(f"  {model}: ${stats['cost']:.4f} ({int(stats['calls'])} calls)")
        return "\n".join(lines)
