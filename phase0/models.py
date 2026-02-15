"""Async model client wrapping Anthropic and OpenAI SDKs."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import anthropic
import openai

from phase0.config import BenchmarkConfig, CostTracker

logger = logging.getLogger(__name__)


@dataclass
class ModelResponse:
    """Normalized response from any model provider."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class ModelClient:
    """Unified async client for Anthropic and OpenAI models."""

    def __init__(self, config: BenchmarkConfig, cost_tracker: CostTracker) -> None:
        self.config = config
        self.cost_tracker = cost_tracker
        self._anthropic = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
        self._openai = openai.AsyncOpenAI(api_key=config.openai_api_key)

    async def send(
        self,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ModelResponse:
        """Send a message and return a normalized response. Retries with exponential backoff."""
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens

        for attempt in range(self.config.max_retries):
            try:
                if model.startswith("claude"):
                    return await self._send_anthropic(model, system, user, temperature, max_tokens)
                else:
                    return await self._send_openai(model, system, user, temperature, max_tokens)
            except (anthropic.RateLimitError, openai.RateLimitError) as e:
                delay = self.config.retry_base_delay * (2 ** attempt)
                logger.warning(f"Rate limited on {model}, retrying in {delay:.1f}s (attempt {attempt + 1}/{self.config.max_retries})")
                await asyncio.sleep(delay)
            except (anthropic.APIError, openai.APIError) as e:
                if attempt == self.config.max_retries - 1:
                    raise
                delay = self.config.retry_base_delay * (2 ** attempt)
                logger.warning(f"API error on {model}: {e}, retrying in {delay:.1f}s")
                await asyncio.sleep(delay)

        raise RuntimeError(f"Failed after {self.config.max_retries} retries on {model}")

    async def _send_anthropic(
        self, model: str, system: str, user: str, temperature: float, max_tokens: int
    ) -> ModelResponse:
        response = await self._anthropic.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        content = response.content[0].text
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = self.cost_tracker.record(model, input_tokens, output_tokens)
        return ModelResponse(
            content=content,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )

    async def _send_openai(
        self, model: str, system: str, user: str, temperature: float, max_tokens: int
    ) -> ModelResponse:
        response = await self._openai.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        cost = self.cost_tracker.record(model, input_tokens, output_tokens)
        return ModelResponse(
            content=content,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )
