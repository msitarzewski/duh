"""Exhaustive tests for sycophancy detection.

Covers all 14 markers individually, boundary conditions at the
200-character window, case sensitivity, and false-positive resistance.
"""

from __future__ import annotations

import pytest

from duh.consensus.handlers import _SYCOPHANCY_MARKERS, detect_sycophancy

# ── Individual marker coverage ───────────────────────────────────


class TestAllMarkers:
    """Each of the 14 sycophancy markers should trigger detection."""

    @pytest.mark.parametrize("marker", _SYCOPHANCY_MARKERS)
    def test_marker_detected_at_start(self, marker: str) -> None:
        text = f"{marker.capitalize()}. The rest of the response continues here."
        assert detect_sycophancy(text) is True

    @pytest.mark.parametrize("marker", _SYCOPHANCY_MARKERS)
    def test_marker_detected_in_opening_sentence(self, marker: str) -> None:
        text = f"Overall, {marker} and I have nothing to add."
        assert detect_sycophancy(text) is True

    @pytest.mark.parametrize("marker", _SYCOPHANCY_MARKERS)
    def test_marker_uppercase(self, marker: str) -> None:
        text = f"{marker.upper()}! Nothing else to say."
        assert detect_sycophancy(text) is True


# ── 200-character boundary ───────────────────────────────────────


class TestBoundaryWindow:
    def test_marker_at_position_199_detected(self) -> None:
        """Marker ending just inside the 200-char window."""
        marker = "great answer"
        padding = "x" * (199 - len(marker))
        text = padding + marker + " and more text after the window"
        assert detect_sycophancy(text) is True

    def test_marker_starting_at_position_201_not_detected(self) -> None:
        """Marker entirely outside the 200-char window."""
        padding = "I disagree with this. " + "x" * 200
        text = padding + "great answer though"
        assert detect_sycophancy(text) is False

    def test_marker_straddling_boundary_detected(self) -> None:
        """Marker that starts inside but ends outside the window.

        detect_sycophancy truncates to 200 chars, so a marker that
        starts before char 200 but extends beyond it will be partially
        cut off and NOT detected. This is expected behavior.
        """
        marker = "excellent analysis"
        # Place marker so it starts at position 190 (inside window)
        # but extends to ~207 (outside window)
        padding = "x" * 190
        text = padding + marker + " and more"
        # The truncated opening is padding + "excellent a" (200 chars)
        # "excellent analysis" is not fully present → not detected
        assert detect_sycophancy(text) is False

    def test_exactly_200_chars(self) -> None:
        """Text exactly 200 chars with marker at the end."""
        marker = "good point"
        padding = "x" * (200 - len(marker))
        text = padding + marker
        assert len(text) == 200
        assert detect_sycophancy(text) is True

    def test_empty_string(self) -> None:
        assert detect_sycophancy("") is False

    def test_short_string_no_marker(self) -> None:
        assert detect_sycophancy("I disagree.") is False


# ── Case insensitivity ───────────────────────────────────────────


class TestCaseHandling:
    def test_lowercase(self) -> None:
        assert detect_sycophancy("great answer! solid work.") is True

    def test_uppercase(self) -> None:
        assert detect_sycophancy("GREAT ANSWER! SOLID WORK.") is True

    def test_mixed_case(self) -> None:
        assert detect_sycophancy("Great Answer! Solid work.") is True

    def test_title_case(self) -> None:
        assert detect_sycophancy("Excellent Analysis of the problem.") is True


# ── False-positive resistance ────────────────────────────────────


class TestFalsePositiveResistance:
    """Genuine challenges should NOT be flagged as sycophantic."""

    def test_disagree_opener(self) -> None:
        text = "I disagree with the fundamental premise of this proposal."
        assert detect_sycophancy(text) is False

    def test_critical_gap_opener(self) -> None:
        text = "A critical gap is the lack of security analysis."
        assert detect_sycophancy(text) is False

    def test_flaw_opener(self) -> None:
        text = "The flaw in this approach is the O(n^2) complexity."
        assert detect_sycophancy(text) is False

    def test_wrong_opener(self) -> None:
        text = "The answer gets wrong the cost estimation entirely."
        assert detect_sycophancy(text) is False

    def test_risk_opener(self) -> None:
        text = "The risk is that this approach fails under concurrent load."
        assert detect_sycophancy(text) is False

    def test_alternative_opener(self) -> None:
        text = "An alternative approach would be to use message queues."
        assert detect_sycophancy(text) is False

    def test_concern_opener(self) -> None:
        text = "My primary concern is the absence of error handling."
        assert detect_sycophancy(text) is False

    def test_problem_opener(self) -> None:
        text = "The problem with this recommendation is scalability."
        assert detect_sycophancy(text) is False

    def test_marker_word_in_genuine_context(self) -> None:
        """'good point' as part of a genuine rebuttal reference."""
        # This WILL trigger because the marker is in the opening
        text = "While the good point about caching is noted, the approach fails."
        assert detect_sycophancy(text) is True

    def test_marker_only_after_200_chars(self) -> None:
        """Genuine challenge that mentions praise only in conclusion."""
        opening = "I disagree strongly with this approach for three reasons. "
        padding = "x" * (200 - len(opening))
        text = opening + padding + " That said, good point about the timeline."
        assert detect_sycophancy(text) is False


# ── Whitespace handling ──────────────────────────────────────────


class TestWhitespace:
    def test_leading_whitespace_stripped(self) -> None:
        text = "   great answer! Everything is correct."
        assert detect_sycophancy(text) is True

    def test_leading_newlines_stripped(self) -> None:
        text = "\n\ngreat answer! Everything is correct."
        assert detect_sycophancy(text) is True

    def test_leading_tabs_stripped(self) -> None:
        text = "\t\tgreat answer! Everything is correct."
        assert detect_sycophancy(text) is True
