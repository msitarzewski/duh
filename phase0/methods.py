"""The 4 benchmark methods for Phase 0.

Each method takes a question and returns a structured result with the final
answer and metadata about the generation process.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from phase0.config import BenchmarkConfig
from phase0.models import ModelClient, ModelResponse
from phase0.prompts import (
    CONSENSUS_CHALLENGER_SYSTEM,
    CONSENSUS_CHALLENGER_USER,
    CONSENSUS_PROPOSER_SYSTEM,
    CONSENSUS_PROPOSER_USER,
    CONSENSUS_REVISER_SYSTEM,
    CONSENSUS_REVISER_USER,
    DIRECT_SYSTEM,
    DIRECT_USER,
    ENSEMBLE_SYNTHESIZER_SYSTEM,
    ENSEMBLE_SYNTHESIZER_USER,
    ENSEMBLE_SYSTEM,
    ENSEMBLE_USER,
    SELF_DEBATE_CRITIC_SYSTEM,
    SELF_DEBATE_CRITIC_USER,
    SELF_DEBATE_PROPOSER_SYSTEM,
    SELF_DEBATE_PROPOSER_USER,
    SELF_DEBATE_SYNTHESIZER_SYSTEM,
    SELF_DEBATE_SYNTHESIZER_USER,
)


@dataclass
class MethodResult:
    """Result from running a benchmark method."""

    method: str
    question: str
    final_answer: str
    steps: list[StepRecord] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0

    def add_step(self, name: str, response: ModelResponse) -> None:
        self.steps.append(StepRecord(name=name, model=response.model, content=response.content))
        self.total_input_tokens += response.input_tokens
        self.total_output_tokens += response.output_tokens
        self.total_cost_usd += response.cost_usd


@dataclass
class StepRecord:
    """Record of a single step within a method."""

    name: str
    model: str
    content: str


async def method_direct(
    question: str, client: ModelClient, config: BenchmarkConfig
) -> MethodResult:
    """(A) Direct: Single model, direct answer."""
    result = MethodResult(method="direct", question=question, final_answer="")

    response = await client.send(
        model=config.claude_model,
        system=DIRECT_SYSTEM,
        user=DIRECT_USER.format(question=question),
    )
    result.add_step("direct", response)
    result.final_answer = response.content
    return result


async def method_self_debate(
    question: str, client: ModelClient, config: BenchmarkConfig
) -> MethodResult:
    """(B) Self-debate: Same model proposes, critiques itself (high temp), synthesizes."""
    result = MethodResult(method="self_debate", question=question, final_answer="")

    # Step 1: Propose
    proposal = await client.send(
        model=config.claude_model,
        system=SELF_DEBATE_PROPOSER_SYSTEM,
        user=SELF_DEBATE_PROPOSER_USER.format(question=question),
    )
    result.add_step("propose", proposal)

    # Step 2: Self-critique at high temperature
    critique = await client.send(
        model=config.claude_model,
        system=SELF_DEBATE_CRITIC_SYSTEM,
        user=SELF_DEBATE_CRITIC_USER.format(question=question, proposal=proposal.content),
        temperature=config.high_temperature,
    )
    result.add_step("critique", critique)

    # Step 3: Synthesize
    synthesis = await client.send(
        model=config.claude_model,
        system=SELF_DEBATE_SYNTHESIZER_SYSTEM,
        user=SELF_DEBATE_SYNTHESIZER_USER.format(
            question=question, proposal=proposal.content, critique=critique.content
        ),
    )
    result.add_step("synthesize", synthesis)
    result.final_answer = synthesis.content
    return result


async def method_consensus(
    question: str, client: ModelClient, config: BenchmarkConfig
) -> MethodResult:
    """(C) Consensus: Claude proposes, GPT challenges (forced disagreement), Claude revises."""
    result = MethodResult(method="consensus", question=question, final_answer="")

    # Step 1: Claude proposes
    proposal = await client.send(
        model=config.claude_model,
        system=CONSENSUS_PROPOSER_SYSTEM,
        user=CONSENSUS_PROPOSER_USER.format(question=question),
    )
    result.add_step("propose", proposal)

    # Step 2: GPT challenges (forced disagreement)
    challenge = await client.send(
        model=config.gpt_model,
        system=CONSENSUS_CHALLENGER_SYSTEM,
        user=CONSENSUS_CHALLENGER_USER.format(question=question, proposal=proposal.content),
    )
    result.add_step("challenge", challenge)

    # Step 3: Claude revises incorporating challenge
    revision = await client.send(
        model=config.claude_model,
        system=CONSENSUS_REVISER_SYSTEM,
        user=CONSENSUS_REVISER_USER.format(
            question=question, proposal=proposal.content, challenge=challenge.content
        ),
    )
    result.add_step("revise", revision)
    result.final_answer = revision.content
    return result


async def method_ensemble(
    question: str, client: ModelClient, config: BenchmarkConfig
) -> MethodResult:
    """(D) Ensemble: 3 parallel samples (high temp), synthesized."""
    result = MethodResult(method="ensemble", question=question, final_answer="")

    # Step 1: 3 parallel samples at high temperature
    samples = await asyncio.gather(
        client.send(
            model=config.claude_model,
            system=ENSEMBLE_SYSTEM,
            user=ENSEMBLE_USER.format(question=question),
            temperature=config.high_temperature,
        ),
        client.send(
            model=config.claude_model,
            system=ENSEMBLE_SYSTEM,
            user=ENSEMBLE_USER.format(question=question),
            temperature=config.high_temperature,
        ),
        client.send(
            model=config.claude_model,
            system=ENSEMBLE_SYSTEM,
            user=ENSEMBLE_USER.format(question=question),
            temperature=config.high_temperature,
        ),
    )
    for i, sample in enumerate(samples):
        result.add_step(f"sample_{i + 1}", sample)

    # Step 2: Synthesize
    synthesis = await client.send(
        model=config.claude_model,
        system=ENSEMBLE_SYNTHESIZER_SYSTEM,
        user=ENSEMBLE_SYNTHESIZER_USER.format(
            question=question,
            answer_1=samples[0].content,
            answer_2=samples[1].content,
            answer_3=samples[2].content,
        ),
    )
    result.add_step("synthesize", synthesis)
    result.final_answer = synthesis.content
    return result


# Method registry for the runner
METHODS = {
    "direct": method_direct,
    "self_debate": method_self_debate,
    "consensus": method_consensus,
    "ensemble": method_ensemble,
}
