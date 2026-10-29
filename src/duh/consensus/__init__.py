"""Consensus engine — multi-model agreement protocol."""

from duh.consensus.convergence import check_convergence
from duh.consensus.decompose import (
    build_decompose_prompt,
    handle_decompose,
    validate_subtask_dag,
)
from duh.consensus.engine import (
    ChallengeCompleted,
    ChallengeFailed,
    Completed,
    ConsensusEvent,
    ConsensusResult,
    ContributionUsage,
    EngineOptions,
    PhaseCompleted,
    PhaseStarted,
    RoundCommitted,
    run_consensus,
    stream_consensus,
)
from duh.consensus.handlers import (
    _FRAMING_ORDER,
    build_challenge_prompt,
    build_propose_prompt,
    build_revise_prompt,
    detect_sycophancy,
    generate_followups,
    generate_overview,
    handle_challenge,
    handle_commit,
    handle_propose,
    handle_revise,
    select_challengers,
    select_proposer,
    validate_challenge_framings,
)
from duh.consensus.handlers import (
    _call_challenger as call_challenger,
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

CHALLENGE_FRAMINGS = tuple(_FRAMING_ORDER)

__all__ = [
    "CHALLENGE_FRAMINGS",
    "ChallengeCompleted",
    "ChallengeFailed",
    "ChallengeResult",
    "Completed",
    "ConsensusContext",
    "ConsensusEvent",
    "ConsensusResult",
    "ConsensusState",
    "ConsensusStateMachine",
    "ContributionUsage",
    "EngineOptions",
    "PhaseCompleted",
    "PhaseStarted",
    "RoundCommitted",
    "RoundResult",
    "SubtaskResult",
    "SubtaskSpec",
    "SynthesisResult",
    "build_challenge_prompt",
    "build_decompose_prompt",
    "build_propose_prompt",
    "build_revise_prompt",
    "call_challenger",
    "check_convergence",
    "detect_sycophancy",
    "generate_followups",
    "generate_overview",
    "handle_challenge",
    "handle_commit",
    "handle_decompose",
    "handle_propose",
    "handle_revise",
    "run_consensus",
    "schedule_subtasks",
    "select_challengers",
    "select_proposer",
    "stream_consensus",
    "synthesize",
    "validate_challenge_framings",
    "validate_subtask_dag",
]
