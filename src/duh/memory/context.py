"""Context builder — assemble thread history for model prompts.

Builds a context string from DB-persisted memory (thread summaries,
past decisions) so models have awareness of prior conversations.
Pure functions — no DB access. Caller provides the data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from duh.memory.models import Decision, Outcome, Thread

# Approximate chars per token for budget estimation.
# Conservative (low) to avoid exceeding real token limits.
_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estimate token count from text length.

    Uses a simple ~4 chars/token heuristic. Conservative estimate
    suitable for budget enforcement without an external tokenizer.
    """
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)


def build_context(
    thread: Thread | None,
    decisions: list[Decision],
    *,
    outcomes: list[Outcome] | None = None,
    max_tokens: int = 2000,
) -> str:
    """Assemble context from thread history and past decisions.

    Priority order (most relevant first):
    1. Thread summary (if available)
    2. Past decisions (most recent first, with confidence and dissent)
    3. Outcomes (if provided)

    Truncates to stay within the token budget. Returns an empty
    string if no history is available.

    Args:
        thread: Current thread (may have a summary). None if new.
        decisions: Past decisions from other threads, ordered by
            relevance or recency. Most recent should be first.
        outcomes: Outcome records to include alongside decisions.
        max_tokens: Maximum estimated tokens for the context.

    Returns:
        Formatted context string, or empty string if no history.
    """
    sections: list[str] = []
    remaining = max_tokens

    # Build outcome lookup by decision_id
    outcome_map: dict[str, Outcome] = {}
    if outcomes:
        for o in outcomes:
            outcome_map[o.decision_id] = o

    # 1. Thread summary (highest priority)
    if thread is not None and thread.summary is not None:
        summary_text = f"Previous conversation summary:\n{thread.summary.summary}"
        cost = estimate_tokens(summary_text)
        if cost <= remaining:
            sections.append(summary_text)
            remaining -= cost

    # 2. Past decisions (with outcomes if available)
    if decisions and remaining > 0:
        decision_parts: list[str] = []
        for d in decisions:
            part = f"- [{d.confidence:.0%} confidence] {d.content}"
            if d.dissent:
                part += f"\n  Dissent: {d.dissent}"
            outcome = outcome_map.get(d.id)
            if outcome:
                part += f"\n  [OUTCOME: {outcome.result}"
                if outcome.notes:
                    part += f' - "{outcome.notes}"'
                part += "]"
            cost = estimate_tokens(part)
            if cost > remaining:
                break
            decision_parts.append(part)
            remaining -= cost

        if decision_parts:
            header = "Relevant past decisions:"
            header_cost = estimate_tokens(header)
            if header_cost <= remaining + sum(
                estimate_tokens(p) for p in decision_parts
            ):
                sections.append(header + "\n" + "\n".join(decision_parts))

    return "\n\n".join(sections)
