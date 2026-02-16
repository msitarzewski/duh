"""Tests for sycophancy impact on confidence scoring and dissent.

Verifies the mathematical relationship between sycophantic challenge
counts and resulting confidence, and that dissent extraction correctly
filters out sycophantic responses.
"""

from __future__ import annotations

from duh.consensus.handlers import _compute_confidence, _extract_dissent
from duh.consensus.machine import ChallengeResult

# ── Helpers ──────────────────────────────────────────────────────


def _genuine(
    model_ref: str = "model-a",
    content: str = "I disagree.",
) -> ChallengeResult:
    return ChallengeResult(model_ref=model_ref, content=content, sycophantic=False)


def _sycophantic(
    model_ref: str = "model-b",
    content: str = "Great answer!",
) -> ChallengeResult:
    return ChallengeResult(model_ref=model_ref, content=content, sycophantic=True)


# ── Confidence computation ───────────────────────────────────────


class TestConfidenceComputation:
    def test_all_genuine_two_challengers(self) -> None:
        """2/2 genuine → 0.5 + (2/2)*0.5 = 1.0."""
        challenges = [_genuine("a"), _genuine("b")]
        assert _compute_confidence(challenges) == 1.0

    def test_all_sycophantic_two_challengers(self) -> None:
        """0/2 genuine → 0.5 + (0/2)*0.5 = 0.5."""
        challenges = [_sycophantic("a"), _sycophantic("b")]
        assert _compute_confidence(challenges) == 0.5

    def test_one_genuine_one_sycophantic(self) -> None:
        """1/2 genuine → 0.5 + (1/2)*0.5 = 0.75."""
        challenges = [_genuine("a"), _sycophantic("b")]
        assert _compute_confidence(challenges) == 0.75

    def test_empty_challenges(self) -> None:
        """No challenges → 0.5 (untested)."""
        assert _compute_confidence([]) == 0.5

    def test_single_genuine(self) -> None:
        """1/1 genuine → 1.0."""
        assert _compute_confidence([_genuine()]) == 1.0

    def test_single_sycophantic(self) -> None:
        """0/1 genuine → 0.5."""
        assert _compute_confidence([_sycophantic()]) == 0.5

    def test_three_challengers_two_genuine(self) -> None:
        """2/3 genuine → 0.5 + (2/3)*0.5 ≈ 0.833."""
        challenges = [_genuine("a"), _genuine("b"), _sycophantic("c")]
        result = _compute_confidence(challenges)
        assert abs(result - (0.5 + (2 / 3) * 0.5)) < 1e-10

    def test_three_challengers_one_genuine(self) -> None:
        """1/3 genuine → 0.5 + (1/3)*0.5 ≈ 0.667."""
        challenges = [_genuine("a"), _sycophantic("b"), _sycophantic("c")]
        result = _compute_confidence(challenges)
        assert abs(result - (0.5 + (1 / 3) * 0.5)) < 1e-10

    def test_confidence_always_between_half_and_one(self) -> None:
        """Confidence is always in [0.5, 1.0]."""
        for n_genuine in range(5):
            for n_syc in range(5):
                if n_genuine + n_syc == 0:
                    continue
                challenges = [_genuine(f"g{i}") for i in range(n_genuine)] + [
                    _sycophantic(f"s{i}") for i in range(n_syc)
                ]
                conf = _compute_confidence(challenges)
                assert 0.5 <= conf <= 1.0, f"{n_genuine}g/{n_syc}s → {conf}"

    def test_confidence_monotonic_with_genuine_ratio(self) -> None:
        """More genuine challenges → higher confidence."""
        total = 4
        prev = 0.0
        for n_genuine in range(total + 1):
            n_syc = total - n_genuine
            challenges = [_genuine(f"g{i}") for i in range(n_genuine)] + [
                _sycophantic(f"s{i}") for i in range(n_syc)
            ]
            conf = _compute_confidence(challenges)
            assert conf >= prev, f"Not monotonic at {n_genuine}/{total}"
            prev = conf


# ── Dissent extraction ───────────────────────────────────────────


class TestDissentExtraction:
    def test_all_genuine_produces_dissent(self) -> None:
        challenges = [
            _genuine("a", "First disagreement."),
            _genuine("b", "Second disagreement."),
        ]
        dissent = _extract_dissent(challenges)
        assert dissent is not None
        assert "[a]" in dissent
        assert "[b]" in dissent
        assert "First disagreement" in dissent
        assert "Second disagreement" in dissent

    def test_all_sycophantic_produces_no_dissent(self) -> None:
        challenges = [
            _sycophantic("a", "Great work!"),
            _sycophantic("b", "Excellent!"),
        ]
        assert _extract_dissent(challenges) is None

    def test_mixed_only_genuine_in_dissent(self) -> None:
        challenges = [
            _genuine("critic", "The approach is flawed."),
            _sycophantic("fan", "Beautiful analysis!"),
        ]
        dissent = _extract_dissent(challenges)
        assert dissent is not None
        assert "[critic]" in dissent
        assert "flawed" in dissent
        assert "Beautiful" not in dissent
        assert "[fan]" not in dissent

    def test_empty_challenges_no_dissent(self) -> None:
        assert _extract_dissent([]) is None

    def test_dissent_format_includes_model_ref(self) -> None:
        challenges = [_genuine("anthropic:opus", "I disagree because...")]
        dissent = _extract_dissent(challenges)
        assert dissent is not None
        assert "[anthropic:opus]" in dissent

    def test_multiple_genuine_separated(self) -> None:
        """Multiple genuine challenges are separated by double newlines."""
        challenges = [
            _genuine("a", "Point one."),
            _genuine("b", "Point two."),
            _genuine("c", "Point three."),
        ]
        dissent = _extract_dissent(challenges)
        assert dissent is not None
        # Should have 2 separators for 3 entries
        assert dissent.count("\n\n") == 2
