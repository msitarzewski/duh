"""Tests for the epistemic confidence scoring system.

Tests the renamed _compute_rigor(), new _domain_cap(), and the
combined confidence = min(domain_cap, rigor) formula.
"""

from __future__ import annotations

import pytest

from duh.consensus.handlers import (
    DOMAIN_CAPS,
    _compute_rigor,
    _domain_cap,
)
from duh.consensus.machine import ChallengeResult

# ── Rigor computation (renamed from _compute_confidence) ─────


class TestComputeRigor:
    def test_all_genuine(self) -> None:
        challenges = [
            ChallengeResult("m1", "real issue"),
            ChallengeResult("m2", "another issue"),
        ]
        assert _compute_rigor(challenges) == 1.0

    def test_all_sycophantic(self) -> None:
        challenges = [
            ChallengeResult("m1", "great", sycophantic=True),
            ChallengeResult("m2", "good", sycophantic=True),
        ]
        assert _compute_rigor(challenges) == 0.5

    def test_mixed(self) -> None:
        challenges = [
            ChallengeResult("m1", "real issue"),
            ChallengeResult("m2", "great", sycophantic=True),
        ]
        assert _compute_rigor(challenges) == 0.75

    def test_empty(self) -> None:
        assert _compute_rigor([]) == 0.5

    def test_range_always_half_to_one(self) -> None:
        for n_genuine in range(5):
            for n_syc in range(5):
                if n_genuine + n_syc == 0:
                    continue
                challenges = [
                    ChallengeResult(f"g{i}", "issue") for i in range(n_genuine)
                ] + [
                    ChallengeResult(f"s{i}", "good", sycophantic=True)
                    for i in range(n_syc)
                ]
                rigor = _compute_rigor(challenges)
                assert 0.5 <= rigor <= 1.0, f"{n_genuine}g/{n_syc}s -> {rigor}"


# ── Domain cap lookup ────────────────────────────────────────


class TestDomainCap:
    def test_factual(self) -> None:
        assert _domain_cap("factual") == 0.95

    def test_technical(self) -> None:
        assert _domain_cap("technical") == 0.90

    def test_creative(self) -> None:
        assert _domain_cap("creative") == 0.85

    def test_judgment(self) -> None:
        assert _domain_cap("judgment") == 0.80

    def test_strategic(self) -> None:
        assert _domain_cap("strategic") == 0.70

    def test_unknown_intent(self) -> None:
        assert _domain_cap("nonexistent") == 0.85

    def test_none_intent(self) -> None:
        assert _domain_cap(None) == 0.85

    def test_all_caps_below_one(self) -> None:
        for intent, cap in DOMAIN_CAPS.items():
            assert cap < 1.0, f"{intent} cap {cap} >= 1.0"

    def test_all_caps_above_zero(self) -> None:
        for intent, cap in DOMAIN_CAPS.items():
            assert cap > 0.0, f"{intent} cap {cap} <= 0.0"


# ── Combined epistemic confidence ────────────────────────────


class TestEpistemicConfidence:
    """Test the formula: confidence = min(domain_cap, rigor)."""

    def test_factual_all_genuine(self) -> None:
        """Capital of France: rigor=1.0, cap=0.95 -> confidence=0.95."""
        rigor = _compute_rigor(
            [
                ChallengeResult("m1", "real issue"),
                ChallengeResult("m2", "another issue"),
            ]
        )
        assert rigor == 1.0
        cap = _domain_cap("factual")
        confidence = min(cap, rigor)
        assert confidence == 0.95

    def test_strategic_all_genuine(self) -> None:
        """Will X happen by 2035: rigor=1.0, cap=0.70 -> confidence=0.70."""
        rigor = _compute_rigor(
            [
                ChallengeResult("m1", "real issue"),
                ChallengeResult("m2", "another issue"),
            ]
        )
        assert rigor == 1.0
        cap = _domain_cap("strategic")
        confidence = min(cap, rigor)
        assert confidence == 0.70

    def test_rigor_below_cap(self) -> None:
        """When rigor < cap, confidence = rigor."""
        rigor = _compute_rigor(
            [
                ChallengeResult("m1", "issue"),
                ChallengeResult("m2", "great", sycophantic=True),
            ]
        )
        assert rigor == 0.75
        cap = _domain_cap("factual")
        confidence = min(cap, rigor)
        assert confidence == 0.75  # rigor is the binding constraint

    def test_unknown_domain_capped(self) -> None:
        """Unknown intent uses default cap of 0.85."""
        rigor = 1.0
        cap = _domain_cap(None)
        assert min(cap, rigor) == 0.85

    @pytest.mark.parametrize(
        ("intent", "expected_cap"),
        [
            ("factual", 0.95),
            ("technical", 0.90),
            ("creative", 0.85),
            ("judgment", 0.80),
            ("strategic", 0.70),
            (None, 0.85),
        ],
    )
    def test_max_confidence_per_intent(
        self, intent: str | None, expected_cap: float
    ) -> None:
        """With perfect rigor, confidence equals the domain cap."""
        rigor = 1.0  # all genuine challenges
        confidence = min(_domain_cap(intent), rigor)
        assert confidence == expected_cap
