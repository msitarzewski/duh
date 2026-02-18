"""Confidence calibration analysis.

Computes calibration metrics for decisions with tracked outcomes.
Buckets decisions by confidence range and compares predicted
confidence against actual accuracy (ECE metric).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from duh.memory.models import Decision


@dataclass(frozen=True)
class CalibrationBucket:
    """One confidence range bucket with accuracy stats."""

    range_lo: float
    range_hi: float
    count: int
    with_outcomes: int
    success: int
    failure: int
    partial: int
    accuracy: float
    mean_confidence: float


@dataclass(frozen=True)
class CalibrationResult:
    """Full calibration analysis result."""

    buckets: list[CalibrationBucket] = field(default_factory=list)
    total_decisions: int = 0
    total_with_outcomes: int = 0
    overall_accuracy: float = 0.0
    ece: float = 0.0


def compute_calibration(
    decisions: Sequence[Decision],
    *,
    n_buckets: int = 10,
) -> CalibrationResult:
    """Compute calibration metrics from decisions with outcomes.

    Buckets decisions by confidence into ``n_buckets`` equal-width bins.
    For each bucket, accuracy = (success + 0.5 * partial) / with_outcomes.
    ECE is the weighted average of |accuracy - mean_confidence| across
    non-empty buckets.

    Args:
        decisions: Sequence of Decision model instances (with .outcome loaded).
        n_buckets: Number of equal-width confidence bins (default 10).

    Returns:
        CalibrationResult with per-bucket stats and overall ECE.
    """
    if n_buckets < 1:
        n_buckets = 1

    # Initialize per-bucket accumulators
    bucket_counts = [0] * n_buckets
    bucket_with_outcomes = [0] * n_buckets
    bucket_success = [0] * n_buckets
    bucket_failure = [0] * n_buckets
    bucket_partial = [0] * n_buckets
    bucket_conf_sum = [0.0] * n_buckets

    total = len(decisions)

    for d in decisions:
        # Determine bucket index from confidence
        idx = int(d.confidence * n_buckets)
        if idx >= n_buckets:
            idx = n_buckets - 1
        if idx < 0:
            idx = 0

        bucket_counts[idx] += 1
        bucket_conf_sum[idx] += d.confidence

        if d.outcome is not None:
            result = d.outcome.result
            bucket_with_outcomes[idx] += 1
            if result == "success":
                bucket_success[idx] += 1
            elif result == "failure":
                bucket_failure[idx] += 1
            elif result == "partial":
                bucket_partial[idx] += 1

    # Build bucket objects
    width = 1.0 / n_buckets
    buckets: list[CalibrationBucket] = []
    total_with_outcomes = 0
    total_accuracy_sum = 0.0
    ece_sum = 0.0
    ece_weight_sum = 0

    for i in range(n_buckets):
        lo = round(i * width, 10)
        hi = round((i + 1) * width, 10)
        count = bucket_counts[i]
        with_out = bucket_with_outcomes[i]
        s = bucket_success[i]
        f = bucket_failure[i]
        p = bucket_partial[i]

        mean_conf = bucket_conf_sum[i] / count if count > 0 else (lo + hi) / 2
        accuracy = (s + 0.5 * p) / with_out if with_out > 0 else 0.0

        buckets.append(
            CalibrationBucket(
                range_lo=lo,
                range_hi=hi,
                count=count,
                with_outcomes=with_out,
                success=s,
                failure=f,
                partial=p,
                accuracy=accuracy,
                mean_confidence=mean_conf,
            )
        )

        total_with_outcomes += with_out
        total_accuracy_sum += s + 0.5 * p

        if with_out > 0:
            ece_sum += with_out * abs(accuracy - mean_conf)
            ece_weight_sum += with_out

    overall_accuracy = (
        total_accuracy_sum / total_with_outcomes if total_with_outcomes > 0 else 0.0
    )
    ece = ece_sum / ece_weight_sum if ece_weight_sum > 0 else 0.0

    return CalibrationResult(
        buckets=buckets,
        total_decisions=total,
        total_with_outcomes=total_with_outcomes,
        overall_accuracy=overall_accuracy,
        ece=ece,
    )
