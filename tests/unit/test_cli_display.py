"""Tests for the Rich consensus display module."""

from __future__ import annotations

import io
import time

from rich.console import Console

from duh.cli.display import ConsensusDisplay, _truncate
from duh.consensus.machine import ChallengeResult


def _make_display() -> tuple[ConsensusDisplay, io.StringIO]:
    """Create a display with captured output."""
    buf = io.StringIO()
    console = Console(file=buf, width=80, no_color=True)
    display = ConsensusDisplay(console=console)
    return display, buf


def _output(buf: io.StringIO) -> str:
    """Read captured output."""
    return buf.getvalue()


# ── Truncation ────────────────────────────────────────────────


class TestTruncate:
    def test_short_text_unchanged(self) -> None:
        assert _truncate("hello", 10) == "hello"

    def test_exact_limit_unchanged(self) -> None:
        text = "a" * 500
        assert _truncate(text) == text

    def test_over_limit_truncated(self) -> None:
        text = "a" * 600
        result = _truncate(text)
        assert len(result) < 600
        assert result.endswith("...")

    def test_custom_limit(self) -> None:
        text = "hello world"
        result = _truncate(text, 5)
        assert result == "hello ..."

    def test_empty_string(self) -> None:
        assert _truncate("") == ""


# ── Lifecycle ─────────────────────────────────────────────────


class TestLifecycle:
    def test_elapsed_before_start(self) -> None:
        display, _ = _make_display()
        assert display.elapsed == 0.0

    def test_elapsed_after_start(self) -> None:
        display, _ = _make_display()
        display.start()
        time.sleep(0.05)
        assert display.elapsed > 0.0


# ── Round header ──────────────────────────────────────────────


class TestRoundHeader:
    def test_round_header_content(self) -> None:
        display, buf = _make_display()
        display.round_header(1, 3)
        out = _output(buf)
        assert "Round 1/3" in out

    def test_round_header_different_values(self) -> None:
        display, buf = _make_display()
        display.round_header(2, 5)
        out = _output(buf)
        assert "Round 2/5" in out


# ── Phase status ──────────────────────────────────────────────


class TestPhaseStatus:
    def test_returns_context_manager(self) -> None:
        display, _ = _make_display()
        status = display.phase_status("PROPOSE", "mock:model-a")
        # Status should be usable as a context manager
        assert hasattr(status, "__enter__")
        assert hasattr(status, "__exit__")

    def test_status_without_detail(self) -> None:
        display, _ = _make_display()
        status = display.phase_status("CHALLENGE")
        assert hasattr(status, "__enter__")


# ── show_propose ──────────────────────────────────────────────


class TestShowPropose:
    def test_shows_model_and_content(self) -> None:
        display, buf = _make_display()
        display.show_propose("mock:model-a", "Use PostgreSQL for scale.")
        out = _output(buf)
        assert "PROPOSE" in out
        assert "mock:model-a" in out
        assert "Use PostgreSQL for scale." in out

    def test_truncates_long_content(self) -> None:
        display, buf = _make_display()
        long_text = "x" * 600
        display.show_propose("mock:model-a", long_text)
        out = _output(buf)
        assert "..." in out
        assert "x" * 600 not in out


# ── show_challenges ───────────────────────────────────────────


class TestShowChallenges:
    def test_shows_all_challenges(self) -> None:
        display, buf = _make_display()
        challenges = [
            ChallengeResult(
                model_ref="mock:model-a",
                content="I disagree with the approach.",
                sycophantic=False,
            ),
            ChallengeResult(
                model_ref="mock:model-b",
                content="The scalability concern is valid.",
                sycophantic=False,
            ),
        ]
        display.show_challenges(challenges)
        out = _output(buf)
        assert "CHALLENGE" in out
        assert "mock:model-a" in out
        assert "I disagree" in out
        assert "mock:model-b" in out
        assert "scalability" in out

    def test_flags_sycophantic(self) -> None:
        display, buf = _make_display()
        challenges = [
            ChallengeResult(
                model_ref="mock:model-a",
                content="Great answer, and also consider...",
                sycophantic=True,
            ),
        ]
        display.show_challenges(challenges)
        out = _output(buf)
        assert "sycophantic" in out

    def test_sycophancy_warning_shown(self) -> None:
        display, buf = _make_display()
        challenges = [
            ChallengeResult(
                model_ref="mock:model-a",
                content="Great answer!",
                sycophantic=True,
            ),
            ChallengeResult(
                model_ref="mock:model-b",
                content="I disagree.",
                sycophantic=False,
            ),
        ]
        display.show_challenges(challenges)
        out = _output(buf)
        assert "1/2" in out
        assert "sycophantic" in out

    def test_no_warning_when_all_genuine(self) -> None:
        display, buf = _make_display()
        challenges = [
            ChallengeResult(
                model_ref="mock:model-a",
                content="I disagree.",
                sycophantic=False,
            ),
        ]
        display.show_challenges(challenges)
        out = _output(buf)
        assert "Warning" not in out

    def test_truncates_long_challenge(self) -> None:
        display, buf = _make_display()
        challenges = [
            ChallengeResult(
                model_ref="mock:model-a",
                content="x" * 600,
                sycophantic=False,
            ),
        ]
        display.show_challenges(challenges)
        out = _output(buf)
        assert "..." in out


# ── show_revise ───────────────────────────────────────────────


class TestShowRevise:
    def test_shows_model_and_content(self) -> None:
        display, buf = _make_display()
        display.show_revise("mock:model-a", "Revised answer here.")
        out = _output(buf)
        assert "REVISE" in out
        assert "mock:model-a" in out
        assert "Revised answer here." in out

    def test_truncates_long_content(self) -> None:
        display, buf = _make_display()
        display.show_revise("mock:model-a", "y" * 600)
        out = _output(buf)
        assert "..." in out


# ── show_commit ───────────────────────────────────────────────


class TestShowCommit:
    def test_shows_confidence(self) -> None:
        display, buf = _make_display()
        display.show_commit(0.85, 1.0, "Some dissent here.")
        out = _output(buf)
        assert "COMMIT" in out
        assert "85%" in out

    def test_shows_no_dissent_marker(self) -> None:
        display, buf = _make_display()
        display.show_commit(1.0, 1.0, None)
        out = _output(buf)
        assert "no dissent" in out

    def test_confidence_formatting(self) -> None:
        display, buf = _make_display()
        display.show_commit(0.5, 1.0, "dissent text")
        out = _output(buf)
        assert "50%" in out


# ── show_sycophancy_warning ───────────────────────────────────


class TestShowSycophancyWarning:
    def test_warning_text(self) -> None:
        display, buf = _make_display()
        display.show_sycophancy_warning(2, 3)
        out = _output(buf)
        assert "Warning" in out
        assert "2/3" in out
        assert "sycophantic" in out


# ── round_footer ──────────────────────────────────────────────


class TestRoundFooter:
    def test_footer_content(self) -> None:
        display, buf = _make_display()
        display.start()
        time.sleep(0.01)
        display.round_footer(1, 2, 3, 0.0234)
        out = _output(buf)
        assert "Round 1/2" in out
        assert "3 models" in out
        assert "$0.0234" in out

    def test_footer_different_values(self) -> None:
        display, buf = _make_display()
        display.start()
        display.round_footer(3, 5, 4, 1.2345)
        out = _output(buf)
        assert "Round 3/5" in out
        assert "4 models" in out
        assert "$1.2345" in out


# ── show_final_decision ───────────────────────────────────────


class TestShowFinalDecision:
    def test_shows_decision_text(self) -> None:
        display, buf = _make_display()
        display.show_final_decision("Use SQLite for v0.1.", 0.85, 1.0, 0.0042, None)
        out = _output(buf)
        assert "Use SQLite for v0.1." in out
        assert "Decision" in out

    def test_shows_confidence_and_cost(self) -> None:
        display, buf = _make_display()
        display.show_final_decision("Answer.", 1.0, 1.0, 0.0042, None)
        out = _output(buf)
        assert "Confidence: 100%" in out
        assert "Cost: $0.0042" in out

    def test_shows_dissent_when_present(self) -> None:
        display, buf = _make_display()
        display.show_final_decision(
            "Answer.",
            0.75,
            1.0,
            0.01,
            "[model-a]: PostgreSQL would be better for scale.",
        )
        out = _output(buf)
        assert "Dissent" in out
        assert "PostgreSQL would be better" in out

    def test_no_dissent_panel_when_none(self) -> None:
        display, buf = _make_display()
        display.show_final_decision("Answer.", 1.0, 1.0, 0.0, None)
        out = _output(buf)
        assert "Dissent" not in out

    def test_decision_not_truncated(self) -> None:
        display, buf = _make_display()
        long_decision = "x" * 1000
        display.show_final_decision(long_decision, 0.9, 1.0, 0.05, None)
        out = _output(buf)
        # Final decision should NOT be truncated
        assert "..." not in out


# ── Full round rendering ─────────────────────────────────────


class TestFullRound:
    def test_complete_round_display(self) -> None:
        """Verify a complete round renders all phases."""
        display, buf = _make_display()
        display.start()

        display.round_header(1, 2)
        display.show_propose("mock:model-a", "Initial proposal text.")
        display.show_challenges(
            [
                ChallengeResult(
                    model_ref="mock:model-b",
                    content="I disagree with the framing.",
                    sycophantic=False,
                ),
                ChallengeResult(
                    model_ref="mock:model-c",
                    content="Great point, also...",
                    sycophantic=True,
                ),
            ]
        )
        display.show_revise("mock:model-a", "Revised with challenges.")
        display.show_commit(0.75, 1.0, "Some dissent.")
        display.round_footer(1, 2, 3, 0.05)
        display.show_final_decision(
            "Final consensus answer.", 0.75, 1.0, 0.05, "Some dissent."
        )

        out = _output(buf)

        # All phases present
        assert "Round 1/2" in out
        assert "PROPOSE" in out
        assert "CHALLENGE" in out
        assert "REVISE" in out
        assert "COMMIT" in out
        assert "Decision" in out

        # Content present
        assert "Initial proposal" in out
        assert "I disagree" in out
        assert "Revised with challenges" in out
        assert "Final consensus answer" in out

        # Sycophancy flagged
        assert "sycophantic" in out
        assert "1/2" in out

        # Stats
        assert "3 models" in out
        assert "$0.0500" in out
