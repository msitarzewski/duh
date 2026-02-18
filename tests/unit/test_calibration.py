"""Tests for duh.calibration — confidence calibration analysis."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from duh.calibration import compute_calibration


def _decision(confidence: float, outcome: str | None = None) -> SimpleNamespace:
    """Create a fake Decision with optional Outcome for testing."""
    out = None
    if outcome is not None:
        out = SimpleNamespace(result=outcome)
    return SimpleNamespace(confidence=confidence, outcome=out)


class TestComputeCalibration:
    def test_empty_input(self) -> None:
        result = compute_calibration([])
        assert result.total_decisions == 0
        assert result.total_with_outcomes == 0
        assert result.overall_accuracy == 0.0
        assert result.ece == 0.0
        assert len(result.buckets) == 10

    def test_no_outcomes(self) -> None:
        decisions = [_decision(0.5), _decision(0.8), _decision(0.3)]
        result = compute_calibration(decisions)  # type: ignore[arg-type]
        assert result.total_decisions == 3
        assert result.total_with_outcomes == 0
        assert result.overall_accuracy == 0.0
        assert result.ece == 0.0

    def test_single_success(self) -> None:
        decisions = [_decision(0.9, "success")]
        result = compute_calibration(decisions)  # type: ignore[arg-type]
        assert result.total_decisions == 1
        assert result.total_with_outcomes == 1
        assert result.overall_accuracy == 1.0
        # Bucket 9 (0.9-1.0): accuracy=1.0, mean_conf=0.9, |1.0-0.9|=0.1
        assert result.ece == pytest.approx(0.1)

    def test_single_failure(self) -> None:
        decisions = [_decision(0.7, "failure")]
        result = compute_calibration(decisions)  # type: ignore[arg-type]
        assert result.total_decisions == 1
        assert result.total_with_outcomes == 1
        assert result.overall_accuracy == 0.0
        # Bucket 7 (0.7-0.8): accuracy=0.0, mean_conf=0.7, |0.0-0.7|=0.7
        assert result.ece == pytest.approx(0.7)

    def test_partial_counts_as_half(self) -> None:
        decisions = [_decision(0.5, "partial")]
        result = compute_calibration(decisions)  # type: ignore[arg-type]
        assert result.total_with_outcomes == 1
        assert result.overall_accuracy == 0.5
        # Bucket 5 (0.5-0.6): accuracy=0.5, mean_conf=0.5, |0.5-0.5|=0.0
        assert result.ece == pytest.approx(0.0)

    def test_perfect_calibration(self) -> None:
        """When accuracy matches confidence, ECE should be near 0."""
        # Put 10 decisions at confidence 0.85:
        # 8 or 9 successes needed for accuracy ~0.85
        # With 10 decisions: 8 success + 1 partial + 1 failure
        # accuracy = (8 + 0.5) / 10 = 0.85 matches mean_conf=0.85
        decisions = (
            [_decision(0.85, "success")] * 8
            + [_decision(0.85, "partial")]
            + [_decision(0.85, "failure")]
        )
        result = compute_calibration(decisions)  # type: ignore[arg-type]
        assert result.total_decisions == 10
        assert result.total_with_outcomes == 10
        assert result.overall_accuracy == pytest.approx(0.85)
        assert result.ece == pytest.approx(0.0)

    def test_overconfident(self) -> None:
        """High confidence but all failures = high ECE."""
        decisions = [_decision(0.95, "failure")] * 10
        result = compute_calibration(decisions)  # type: ignore[arg-type]
        assert result.overall_accuracy == 0.0
        assert result.ece > 0.8  # ~0.95

    def test_multiple_buckets(self) -> None:
        decisions = [
            _decision(0.15, "success"),
            _decision(0.15, "failure"),
            _decision(0.85, "success"),
            _decision(0.85, "success"),
        ]
        result = compute_calibration(decisions)  # type: ignore[arg-type]
        assert result.total_decisions == 4
        assert result.total_with_outcomes == 4

        # Bucket 1 (0.1-0.2): 2 with_outcomes, 1 success, accuracy=0.5
        bucket1 = result.buckets[1]
        assert bucket1.count == 2
        assert bucket1.with_outcomes == 2
        assert bucket1.success == 1
        assert bucket1.accuracy == pytest.approx(0.5)

        # Bucket 8 (0.8-0.9): 2 with_outcomes, 2 success, accuracy=1.0
        bucket8 = result.buckets[8]
        assert bucket8.count == 2
        assert bucket8.with_outcomes == 2
        assert bucket8.success == 2
        assert bucket8.accuracy == pytest.approx(1.0)

    def test_custom_n_buckets(self) -> None:
        decisions = [_decision(0.5, "success")]
        result = compute_calibration(decisions, n_buckets=5)  # type: ignore[arg-type]
        assert len(result.buckets) == 5
        # confidence 0.5 -> bucket index 2 (0.4-0.6)
        assert result.buckets[2].count == 1
        assert result.buckets[2].with_outcomes == 1

    def test_boundary_zero(self) -> None:
        """Confidence 0.0 goes into the first bucket."""
        decisions = [_decision(0.0, "failure")]
        result = compute_calibration(decisions)  # type: ignore[arg-type]
        assert result.buckets[0].count == 1
        assert result.buckets[0].with_outcomes == 1
        assert result.buckets[0].accuracy == 0.0

    def test_boundary_one(self) -> None:
        """Confidence 1.0 goes into the last bucket."""
        decisions = [_decision(1.0, "success")]
        result = compute_calibration(decisions)  # type: ignore[arg-type]
        assert result.buckets[9].count == 1
        assert result.buckets[9].with_outcomes == 1
        assert result.buckets[9].accuracy == 1.0

    def test_boundary_exact_tenth(self) -> None:
        """Confidence exactly 0.1 goes into bucket 1 (0.1-0.2)."""
        decisions = [_decision(0.1, "success")]
        result = compute_calibration(decisions)  # type: ignore[arg-type]
        assert result.buckets[1].count == 1

    def test_overall_accuracy(self) -> None:
        decisions = [
            _decision(0.5, "success"),
            _decision(0.5, "failure"),
            _decision(0.5, "partial"),
            _decision(0.5, "success"),
        ]
        # accuracy = (2 + 0.5) / 4 = 0.625
        result = compute_calibration(decisions)  # type: ignore[arg-type]
        assert result.overall_accuracy == pytest.approx(0.625)

    def test_mixed_with_and_without_outcomes(self) -> None:
        decisions = [
            _decision(0.5, "success"),
            _decision(0.5),  # no outcome
            _decision(0.5, "failure"),
        ]
        result = compute_calibration(decisions)  # type: ignore[arg-type]
        assert result.total_decisions == 3
        assert result.total_with_outcomes == 2
        assert result.overall_accuracy == pytest.approx(0.5)
