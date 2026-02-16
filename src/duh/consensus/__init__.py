"""Consensus engine — multi-model agreement protocol."""

from duh.consensus.convergence import check_convergence
from duh.consensus.handlers import (
    build_challenge_prompt,
    build_propose_prompt,
    build_revise_prompt,
    detect_sycophancy,
    handle_challenge,
    handle_commit,
    handle_propose,
    handle_revise,
    select_challengers,
    select_proposer,
)
from duh.consensus.machine import (
    ChallengeResult,
    ConsensusContext,
    ConsensusState,
    ConsensusStateMachine,
    RoundResult,
)

__all__ = [
    "ChallengeResult",
    "ConsensusContext",
    "ConsensusState",
    "ConsensusStateMachine",
    "RoundResult",
    "build_challenge_prompt",
    "build_propose_prompt",
    "build_revise_prompt",
    "check_convergence",
    "detect_sycophancy",
    "handle_challenge",
    "handle_commit",
    "handle_propose",
    "handle_revise",
    "select_challengers",
    "select_proposer",
]
