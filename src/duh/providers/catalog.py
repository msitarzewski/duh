"""Centralized model catalog for all providers.

One file to update when models change.  Each provider imports its
models from here instead of defining its own ``_KNOWN_MODELS`` list.
"""

from __future__ import annotations

from typing import Any

from duh.providers.base import ModelCapability

# ── Per-provider default capabilities ──────────────────────────

PROVIDER_CAPS: dict[str, ModelCapability] = {
    "anthropic": (
        ModelCapability.TEXT
        | ModelCapability.STREAMING
        | ModelCapability.SYSTEM_PROMPT
        | ModelCapability.JSON_MODE
        | ModelCapability.WEB_SEARCH
    ),
    "openai": (
        ModelCapability.TEXT
        | ModelCapability.STREAMING
        | ModelCapability.SYSTEM_PROMPT
        | ModelCapability.JSON_MODE
    ),
    "google": (
        ModelCapability.TEXT
        | ModelCapability.STREAMING
        | ModelCapability.SYSTEM_PROMPT
        | ModelCapability.JSON_MODE
        | ModelCapability.WEB_SEARCH
    ),
    "mistral": (
        ModelCapability.TEXT
        | ModelCapability.STREAMING
        | ModelCapability.SYSTEM_PROMPT
        | ModelCapability.JSON_MODE
        | ModelCapability.WEB_SEARCH
    ),
    "perplexity": (
        ModelCapability.TEXT
        | ModelCapability.STREAMING
        | ModelCapability.SYSTEM_PROMPT
        | ModelCapability.JSON_MODE
        | ModelCapability.WEB_SEARCH
    ),
    # Cloudflare Workers AI (OpenAI-compatible endpoint), e.g. Zhipu GLM
    "cloudflare": (
        ModelCapability.TEXT
        | ModelCapability.STREAMING
        | ModelCapability.SYSTEM_PROMPT
        | ModelCapability.JSON_MODE
    ),
}

# ── Model catalog keyed by provider_id ─────────────────────────

MODEL_CATALOG: dict[str, list[dict[str, Any]]] = {
    "anthropic": [
        {
            "model_id": "claude-opus-4-8",
            "display_name": "Claude Opus 4.8",
            "context_window": 1_000_000,
            "max_output_tokens": 128_000,
            "input_cost_per_mtok": 5.00,
            "output_cost_per_mtok": 25.00,
        },
        {
            "model_id": "claude-opus-4-7",
            "display_name": "Claude Opus 4.7",
            "context_window": 1_000_000,
            "max_output_tokens": 128_000,
            "input_cost_per_mtok": 5.00,
            "output_cost_per_mtok": 25.00,
        },
        {
            "model_id": "claude-opus-4-6",
            "display_name": "Claude Opus 4.6",
            "context_window": 1_000_000,
            "max_output_tokens": 128_000,
            "input_cost_per_mtok": 5.00,
            "output_cost_per_mtok": 25.00,
        },
        {
            "model_id": "claude-sonnet-4-6",
            "display_name": "Claude Sonnet 4.6",
            "context_window": 1_000_000,
            "max_output_tokens": 64_000,
            "input_cost_per_mtok": 3.00,
            "output_cost_per_mtok": 15.00,
        },
        {
            "model_id": "claude-sonnet-4-5-20250929",
            "display_name": "Claude Sonnet 4.5",
            "context_window": 200_000,
            "max_output_tokens": 64_000,
            "input_cost_per_mtok": 3.00,
            "output_cost_per_mtok": 15.00,
        },
        {
            "model_id": "claude-haiku-4-5-20251001",
            "display_name": "Claude Haiku 4.5",
            "context_window": 200_000,
            "max_output_tokens": 64_000,
            "input_cost_per_mtok": 1.00,
            "output_cost_per_mtok": 5.00,
        },
    ],
    "openai": [
        {
            "model_id": "gpt-5.5",
            "display_name": "GPT-5.5",
            "context_window": 1_050_000,
            "max_output_tokens": 128_000,
            "input_cost_per_mtok": 5.00,
            "output_cost_per_mtok": 30.00,
        },
        {
            "model_id": "gpt-5.4",
            "display_name": "GPT-5.4",
            "context_window": 1_050_000,
            "max_output_tokens": 128_000,
            "input_cost_per_mtok": 2.50,
            "output_cost_per_mtok": 15.00,
        },
        {
            "model_id": "gpt-5.4-mini",
            "display_name": "GPT-5.4 mini",
            "context_window": 400_000,
            "max_output_tokens": 128_000,
            "input_cost_per_mtok": 0.75,
            "output_cost_per_mtok": 4.50,
        },
        {
            "model_id": "gpt-5.2",
            "display_name": "GPT-5.2",
            "context_window": 400_000,
            "max_output_tokens": 128_000,
            "input_cost_per_mtok": 1.75,
            "output_cost_per_mtok": 14.00,
        },
        {
            "model_id": "gpt-5-mini",
            "display_name": "GPT-5 mini",
            "context_window": 400_000,
            "max_output_tokens": 128_000,
            "input_cost_per_mtok": 0.25,
            "output_cost_per_mtok": 2.00,
        },
    ],
    "google": [
        {
            "model_id": "gemini-3.5-flash",
            "display_name": "Gemini 3.5 Flash",
            "context_window": 1_048_576,
            "max_output_tokens": 65_536,
            "input_cost_per_mtok": 1.50,
            "output_cost_per_mtok": 9.00,
        },
        {
            "model_id": "gemini-3.1-pro-preview",
            "display_name": "Gemini 3.1 Pro (Preview)",
            "context_window": 1_048_576,
            "max_output_tokens": 65_536,
            "input_cost_per_mtok": 2.00,
            "output_cost_per_mtok": 12.00,
        },
        {
            "model_id": "gemini-3-pro-preview",
            "display_name": "Gemini 3 Pro (Preview)",
            "context_window": 1_048_576,
            "max_output_tokens": 65_536,
            "input_cost_per_mtok": 2.00,
            "output_cost_per_mtok": 12.00,
        },
        {
            "model_id": "gemini-3-flash-preview",
            "display_name": "Gemini 3 Flash (Preview)",
            "context_window": 1_048_576,
            "max_output_tokens": 65_536,
            "input_cost_per_mtok": 0.50,
            "output_cost_per_mtok": 3.00,
        },
        {
            "model_id": "gemini-2.5-pro",
            "display_name": "Gemini 2.5 Pro",
            "context_window": 1_048_576,
            "max_output_tokens": 65_536,
            "input_cost_per_mtok": 1.25,
            "output_cost_per_mtok": 10.00,
        },
        {
            "model_id": "gemini-2.5-flash",
            "display_name": "Gemini 2.5 Flash",
            "context_window": 1_048_576,
            "max_output_tokens": 65_536,
            "input_cost_per_mtok": 0.30,
            "output_cost_per_mtok": 2.50,
        },
    ],
    "mistral": [
        {
            "model_id": "mistral-large-latest",
            "display_name": "Mistral Large",
            "context_window": 128_000,
            "max_output_tokens": 32_000,
            "input_cost_per_mtok": 2.0,
            "output_cost_per_mtok": 6.0,
        },
        {
            "model_id": "mistral-medium-latest",
            "display_name": "Mistral Medium",
            "context_window": 128_000,
            "max_output_tokens": 32_000,
            "input_cost_per_mtok": 2.7,
            "output_cost_per_mtok": 8.1,
        },
        {
            "model_id": "mistral-small-latest",
            "display_name": "Mistral Small",
            "context_window": 128_000,
            "max_output_tokens": 32_000,
            "input_cost_per_mtok": 0.2,
            "output_cost_per_mtok": 0.6,
        },
        {
            "model_id": "codestral-latest",
            "display_name": "Codestral",
            "context_window": 256_000,
            "max_output_tokens": 32_000,
            "input_cost_per_mtok": 0.3,
            "output_cost_per_mtok": 0.9,
        },
    ],
    "perplexity": [
        {
            "model_id": "sonar",
            "display_name": "Sonar",
            "context_window": 128_000,
            "max_output_tokens": 8_192,
            "input_cost_per_mtok": 1.0,
            "output_cost_per_mtok": 1.0,
        },
        {
            "model_id": "sonar-pro",
            "display_name": "Sonar Pro",
            "context_window": 200_000,
            "max_output_tokens": 8_192,
            "input_cost_per_mtok": 3.0,
            "output_cost_per_mtok": 15.0,
        },
        {
            "model_id": "sonar-reasoning-pro",
            "display_name": "Sonar Reasoning Pro",
            "context_window": 128_000,
            "max_output_tokens": 8_192,
            "input_cost_per_mtok": 2.0,
            "output_cost_per_mtok": 8.0,
        },
        {
            "model_id": "sonar-deep-research",
            "display_name": "Sonar Deep Research",
            "context_window": 128_000,
            "max_output_tokens": 8_192,
            "input_cost_per_mtok": 2.0,
            "output_cost_per_mtok": 8.0,
        },
    ],
    "cloudflare": [
        {
            # Zhipu GLM-5.2 served on Cloudflare Workers AI. Pricing/context per
            # the Workers AI model page (max_output not published; conservative).
            "model_id": "@cf/zai-org/glm-5.2",
            "display_name": "GLM-5.2 (Cloudflare)",
            "context_window": 262_144,
            "max_output_tokens": 32_768,
            "input_cost_per_mtok": 1.40,
            "output_cost_per_mtok": 4.40,
        },
    ],
}

# ── OpenAI reasoning models (no temperature support) ───────────

NO_TEMPERATURE_MODELS: set[str] = {
    "o3",
    "o3-mini",
    "o4-mini",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5.2",
    "gpt-5.4",
    "gpt-5.5",
}

# ── Anthropic models that reject the temperature param ─────────
# The newest thinking models (Opus 4.7+) deprecated `temperature`; older
# models (Opus 4.6, Sonnet, Haiku) still accept it. Verified empirically.

ANTHROPIC_NO_TEMPERATURE_MODELS: set[str] = {
    "claude-opus-4-8",
    "claude-opus-4-7",
}

# ── Providers that are challenger-only (not proposer-eligible) ──

CHALLENGER_ONLY_PROVIDERS: set[str] = {"perplexity"}
