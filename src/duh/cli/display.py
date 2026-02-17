"""Rich display for consensus visualization.

Renders consensus phases with styled panels, spinners for active
phases, and formatted statistics. Used by the ``ask`` command to
show real-time progress during consensus rounds.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

if TYPE_CHECKING:
    from collections.abc import Sequence

    from rich.status import Status

    from duh.consensus.machine import ChallengeResult, SubtaskSpec
    from duh.consensus.scheduler import SubtaskResult
    from duh.consensus.synthesis import SynthesisResult
    from duh.consensus.voting import VoteResult, VotingAggregation

_TRUNCATE_LEN = 500


def _truncate(text: str, limit: int = _TRUNCATE_LEN) -> str:
    """Truncate text to *limit* characters with an ellipsis."""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " ..."


class ConsensusDisplay:
    """Rich display for consensus visualization.

    Provides phase-level rendering with spinners during active phases
    and styled panels for completed phases.  Accepts an optional
    :class:`~rich.console.Console` for dependency injection in tests.
    """

    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console()
        self._start_time: float = 0.0

    # ── Lifecycle ─────────────────────────────────────────────

    def start(self) -> None:
        """Record the start time for elapsed calculations."""
        self._start_time = time.monotonic()

    @property
    def elapsed(self) -> float:
        """Seconds elapsed since :meth:`start` was called."""
        if self._start_time == 0.0:
            return 0.0
        return time.monotonic() - self._start_time

    # ── Round structure ───────────────────────────────────────

    def round_header(self, round_num: int, max_rounds: int) -> None:
        """Print a round separator with the round number."""
        self._console.print()
        self._console.rule(
            f"[bold]Round {round_num}/{max_rounds}[/bold]",
            style="cyan",
        )

    def round_footer(
        self,
        round_num: int,
        max_rounds: int,
        model_count: int,
        cost: float,
    ) -> None:
        """Print round statistics."""
        elapsed = self.elapsed
        parts = [
            f"Round {round_num}/{max_rounds}",
            f"{model_count} models",
            f"${cost:.4f}",
            f"{elapsed:.1f}s",
        ]
        self._console.print()
        self._console.print(" | ".join(parts), style="dim")

    # ── Phase spinner ─────────────────────────────────────────

    def phase_status(self, phase: str, detail: str = "") -> Status:
        """Return a :class:`~rich.status.Status` spinner for a phase.

        Use as a context manager around the async handler call::

            with display.phase_status("PROPOSE", model_ref):
                await handle_propose(ctx, pm, proposer)
        """
        label = f"[bold cyan]{phase}[/bold cyan]"
        if detail:
            label += f" ({detail})"
        label += " thinking..."
        return self._console.status(label, spinner="dots")

    # ── Phase results ─────────────────────────────────────────

    def show_propose(self, model_ref: str, content: str) -> None:
        """Display the proposal in a panel (truncated)."""
        self._console.print(
            Panel(
                _truncate(content),
                title=f"[bold green]PROPOSE[/bold green] ({model_ref})",
                border_style="green",
            )
        )

    def show_challenges(self, challenges: Sequence[ChallengeResult]) -> None:
        """Display all challenges in a single panel."""
        parts: list[Text] = []
        sycophantic_count = 0

        for i, ch in enumerate(challenges):
            if i > 0:
                parts.append(Text())  # blank line separator

            header = Text(ch.model_ref, style="bold")
            if ch.sycophantic:
                header.append("  ")
                header.append("sycophantic", style="bold yellow")
                sycophantic_count += 1
            parts.append(header)
            parts.append(Text(_truncate(ch.content)))

        body = Text("\n").join(parts)
        self._console.print(
            Panel(
                body,
                title="[bold yellow]CHALLENGE[/bold yellow]",
                border_style="yellow",
            )
        )

        if sycophantic_count:
            self.show_sycophancy_warning(sycophantic_count, len(challenges))

    def show_revise(self, model_ref: str, content: str) -> None:
        """Display the revision in a panel (truncated)."""
        self._console.print(
            Panel(
                _truncate(content),
                title=f"[bold blue]REVISE[/bold blue] ({model_ref})",
                border_style="blue",
            )
        )

    def show_commit(self, confidence: float, dissent: str | None) -> None:
        """Display commit result line."""
        check = "[bold green]\\u2713[/bold green]"
        line = f"{check} COMMIT  Confidence: {confidence:.0%}"
        if dissent is None:
            line += "  (no dissent)"
        self._console.print(line)

    def show_sycophancy_warning(self, sycophantic_count: int, total: int) -> None:
        """Display a warning about sycophantic challenges."""
        self._console.print(
            f"[bold yellow]Warning:[/bold yellow] "
            f"{sycophantic_count}/{total} challenges flagged as sycophantic"
        )

    # ── Taxonomy & Outcome ─────────────────────────────────────

    def show_taxonomy(
        self,
        intent: str | None,
        category: str | None,
        genus: str | None,
    ) -> None:
        """Display taxonomy classification fields."""
        parts: list[str] = []
        if intent:
            parts.append(f"Intent: {intent}")
        if category:
            parts.append(f"Category: {category}")
        if genus:
            parts.append(f"Genus: {genus}")
        if not parts:
            return
        self._console.print(
            Panel(
                "\n".join(parts),
                title="[bold magenta]Taxonomy[/bold magenta]",
                border_style="magenta",
            )
        )

    def show_outcome(self, result: str, notes: str | None) -> None:
        """Display outcome result and optional notes."""
        body = f"Result: {result}"
        if notes:
            body += f"\nNotes: {notes}"
        self._console.print(
            Panel(
                body,
                title="[bold cyan]Outcome[/bold cyan]",
                border_style="cyan",
            )
        )

    # ── Decomposition ─────────────────────────────────────────

    def subtask_header(
        self,
        label: str,
        index: int,
        total: int,
        deps: Sequence[str],
    ) -> None:
        """Print a header for a subtask about to execute."""
        title = f"[bold]Subtask {index}/{total}: {label}[/bold]"
        if deps:
            title += f" (needs: {', '.join(deps)})"
        self._console.print()
        self._console.rule(title, style="magenta")

    def subtask_footer(
        self,
        label: str,
        index: int,
        total: int,
        cost: float,
    ) -> None:
        """Print a footer after a subtask completes."""
        elapsed = self.elapsed
        parts = [
            f"Subtask {index}/{total}",
            f"${cost:.4f}",
            f"{elapsed:.1f}s",
        ]
        self._console.print(" | ".join(parts), style="dim")

    def show_decompose(self, subtask_specs: Sequence[SubtaskSpec]) -> None:
        """Display the decomposition plan showing subtasks and deps."""
        parts: list[str] = []
        for i, spec in enumerate(subtask_specs, 1):
            dep_text = ", ".join(spec.dependencies) if spec.dependencies else "none"
            parts.append(
                f"{i}. \\[{spec.label}] {spec.description}\n   Dependencies: {dep_text}"
            )
        body = "\n".join(parts)
        self._console.print(
            Panel(
                body,
                title=(
                    f"[bold magenta]DECOMPOSE[/bold magenta]"
                    f" ({len(subtask_specs)} subtasks)"
                ),
                border_style="magenta",
            )
        )

    def show_subtask_progress(self, subtask_result: SubtaskResult) -> None:
        """Display a completed subtask result."""
        check = "[bold green]\\u2713[/bold green]"
        self._console.print(
            f"{check} [{subtask_result.label}]  "
            f"Confidence: {subtask_result.confidence:.0%}"
        )
        self._console.print(
            Panel(
                _truncate(subtask_result.decision),
                title=f"[bold cyan]{subtask_result.label}[/bold cyan]",
                border_style="cyan",
            )
        )

    def show_synthesis(self, synthesis_result: SynthesisResult) -> None:
        """Display the synthesis result merging all subtask answers."""
        self._console.print()
        self._console.print(
            Panel(
                synthesis_result.content,
                title=(
                    f"[bold bright_white]SYNTHESIS[/bold bright_white]"
                    f" ({synthesis_result.strategy})"
                ),
                border_style="bright_white",
            )
        )
        self._console.print(f"Aggregate confidence: {synthesis_result.confidence:.0%}")

    # ── Voting ─────────────────────────────────────────────────

    def show_votes(self, votes: Sequence[VoteResult]) -> None:
        """Display individual model votes in a panel."""
        parts: list[Text] = []
        for i, vote in enumerate(votes):
            if i > 0:
                parts.append(Text())  # blank line separator
            header = Text(vote.model_ref, style="bold")
            parts.append(header)
            parts.append(Text(_truncate(vote.content)))

        body = Text("\n").join(parts)
        self._console.print(
            Panel(
                body,
                title="[bold cyan]VOTES[/bold cyan]",
                border_style="cyan",
            )
        )

    def show_voting_result(self, result: VotingAggregation, cost: float) -> None:
        """Display aggregated voting result with confidence."""
        self._console.print()
        self._console.rule(style="bright_white")
        self._console.print(
            Panel(
                result.decision,
                title="[bold bright_white]Decision[/bold bright_white]",
                border_style="bright_white",
            )
        )
        self._console.print(
            f"Strategy: {result.strategy} | "
            f"Confidence: {result.confidence:.0%} | "
            f"Votes: {len(result.votes)} | "
            f"Cost: ${cost:.4f}"
        )

    # ── Tool use ───────────────────────────────────────────────

    def show_tool_use(self, tool_calls_log: list[dict[str, str]]) -> None:
        """Display a summary of tool calls made during consensus."""
        if not tool_calls_log:
            return

        parts: list[str] = []
        for entry in tool_calls_log:
            phase = entry.get("phase", "unknown")
            tool = entry.get("tool", "unknown")
            args = entry.get("arguments", "")
            parts.append(f"  [{phase}] {tool}({args})")

        body = "\n".join(parts)
        self._console.print(
            Panel(
                body,
                title=(f"[bold cyan]TOOLS[/bold cyan] ({len(tool_calls_log)} calls)"),
                border_style="cyan",
            )
        )

    # ── Final output ──────────────────────────────────────────

    def show_final_decision(
        self,
        decision: str,
        confidence: float,
        cost: float,
        dissent: str | None,
    ) -> None:
        """Display the final consensus decision (full, untruncated)."""
        self._console.print()
        self._console.rule(style="bright_white")
        self._console.print(
            Panel(
                decision,
                title="[bold bright_white]Decision[/bold bright_white]",
                border_style="bright_white",
            )
        )
        self._console.print(f"Confidence: {confidence:.0%} | Cost: ${cost:.4f}")

        if dissent:
            self._console.print()
            self._console.print(
                Panel(
                    dissent,
                    title="[bold yellow]Dissent[/bold yellow]",
                    border_style="yellow",
                )
            )
