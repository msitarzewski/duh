"""Convergence detection — cross-round challenge comparison.

Determines whether the consensus protocol has stabilized by comparing
challenges across rounds. When challengers raise the same issues in
consecutive rounds, further iteration is unlikely to improve the answer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from duh.consensus.machine import ChallengeResult, ConsensusContext


def _challenge_similarity(a: str, b: str) -> float:
    """Compute normalized word-overlap (Jaccard) between two texts.

    Returns 0.0 (no shared words) to 1.0 (identical word sets).
    """
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a and not words_b:
        return 1.0
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _rounds_converged(
    current: list[ChallengeResult],
    previous: list[ChallengeResult],
    *,
    threshold: float = 0.7,
) -> bool:
    """Check if current challenges are substantially similar to previous.

    For each current challenge, finds the maximum similarity to any
    previous challenge. If the average of these max similarities meets
    or exceeds the threshold, the rounds have converged.
    """
    if not current or not previous:
        return False

    max_sims: list[float] = []
    for cur in current:
        best = max(
            _challenge_similarity(cur.content, prev.content) for prev in previous
        )
        max_sims.append(best)

    return sum(max_sims) / len(max_sims) >= threshold


def check_convergence(
    ctx: ConsensusContext,
    *,
    threshold: float = 0.7,
) -> bool:
    """Check whether the consensus protocol has converged.

    Compares the current round's challenges against the most recent
    archived round. Convergence means challengers are raising the same
    issues, so further rounds won't improve the answer.

    Must be called after handle_commit (challenges are set) and before
    the state machine transition out of COMMIT.

    Round 1 always returns False (nothing to compare against).

    Sets ``ctx.converged = True`` if convergence is detected.

    Args:
        ctx: Consensus context with current challenges and round history.
        threshold: Jaccard similarity threshold for convergence (0.0-1.0).

    Returns:
        Whether the protocol has converged.
    """
    if not ctx.round_history:
        return False

    previous_challenges = list(ctx.round_history[-1].challenges)

    converged = _rounds_converged(
        ctx.challenges,
        previous_challenges,
        threshold=threshold,
    )

    if converged:
        ctx.converged = True

    return converged
