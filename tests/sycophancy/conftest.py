"""Shared fixtures for the sycophancy test suite."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from duh.consensus.machine import (
    ConsensusContext,
    ConsensusState,
    ConsensusStateMachine,
)

if TYPE_CHECKING:
    from tests.fixtures.providers import MockProvider


def _make_ctx(**kwargs: object) -> ConsensusContext:
    defaults: dict[str, object] = {
        "thread_id": "t-syc",
        "question": "How should we handle user input parsing?",
        "max_rounds": 3,
    }
    defaults.update(kwargs)
    return ConsensusContext(**defaults)  # type: ignore[arg-type]


def _challenge_ctx(**kwargs: object) -> ConsensusContext:
    """Create a context in CHALLENGE state with a proposal set."""
    ctx = _make_ctx(**kwargs)
    sm = ConsensusStateMachine(ctx)
    sm.transition(ConsensusState.PROPOSE)
    ctx.proposal = "Use eval() for JSON parsing."
    ctx.proposal_model = "mock:proposer"
    sm.transition(ConsensusState.CHALLENGE)
    return ctx


async def setup_pm(provider: MockProvider) -> Any:
    """Register a mock provider and return a ProviderManager."""
    from duh.providers.manager import ProviderManager

    pm = ProviderManager()
    await pm.register(provider)
    return pm


@pytest.fixture
def known_flaw_genuine_provider() -> MockProvider:
    """Provider with known-flaw proposal + genuine challenges."""
    from tests.fixtures.providers import MockProvider
    from tests.fixtures.responses import KNOWN_FLAW_GENUINE

    return MockProvider(provider_id="mock", responses=KNOWN_FLAW_GENUINE)


@pytest.fixture
def known_flaw_sycophantic_provider() -> MockProvider:
    """Provider with known-flaw proposal + sycophantic challenges."""
    from tests.fixtures.providers import MockProvider
    from tests.fixtures.responses import KNOWN_FLAW_SYCOPHANTIC

    return MockProvider(provider_id="mock", responses=KNOWN_FLAW_SYCOPHANTIC)


@pytest.fixture
def known_flaw_mixed_provider() -> MockProvider:
    """Provider with known-flaw proposal + one genuine, one sycophantic."""
    from tests.fixtures.providers import MockProvider
    from tests.fixtures.responses import KNOWN_FLAW_MIXED

    return MockProvider(provider_id="mock", responses=KNOWN_FLAW_MIXED)
