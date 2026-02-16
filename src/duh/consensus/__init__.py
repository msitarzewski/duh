"""Consensus engine — multi-model agreement protocol."""

from duh.consensus.convergence import check_convergence
from duh.consensus.decompose import (
    build_decompose_prompt,
    handle_decompose,
    validate_subtask_dag,
)
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
    SubtaskSpec,
)
from duh.consensus.scheduler import SubtaskResult, schedule_subtasks
from duh.consensus.synthesis import SynthesisResult, synthesize

__all__ = [
    "ChallengeResult",
    "ConsensusContext",
    "ConsensusState",
    "ConsensusStateMachine",
    "RoundResult",
    "SubtaskResult",
    "SubtaskSpec",
    "SynthesisResult",
    "build_challenge_prompt",
    "build_decompose_prompt",
    "build_propose_prompt",
    "build_revise_prompt",
    "check_convergence",
    "detect_sycophancy",
    "handle_challenge",
    "handle_commit",
    "handle_decompose",
    "handle_propose",
    "handle_revise",
    "schedule_subtasks",
    "select_challengers",
    "select_proposer",
    "synthesize",
    "validate_subtask_dag",
]
