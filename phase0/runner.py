"""Benchmark runner with checkpointing and Rich progress display."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from phase0.config import BenchmarkConfig, CostTracker
from phase0.methods import METHODS, MethodResult
from phase0.models import ModelClient
from phase0.questions import Question, load_pilot_questions, load_questions

logger = logging.getLogger(__name__)
console = Console()


def result_path(results_dir: Path, question_id: str, method: str) -> Path:
    """Path for a single result file."""
    d = results_dir / "raw" / question_id
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{method}.json"


def save_result(path: Path, result: MethodResult) -> None:
    """Save a method result to JSON."""
    data = {
        "method": result.method,
        "question": result.question,
        "final_answer": result.final_answer,
        "total_input_tokens": result.total_input_tokens,
        "total_output_tokens": result.total_output_tokens,
        "total_cost_usd": result.total_cost_usd,
        "steps": [
            {"name": s.name, "model": s.model, "content": s.content}
            for s in result.steps
        ],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def is_complete(results_dir: Path, question_id: str, method: str) -> bool:
    """Check if a result already exists (for checkpoint resumption)."""
    return result_path(results_dir, question_id, method).exists()


async def run_benchmark(
    questions: list[Question],
    config: BenchmarkConfig,
    cost_tracker: CostTracker,
) -> None:
    """Run all methods on all questions with progress display."""
    results_dir = Path(config.results_dir)
    client = ModelClient(config, cost_tracker)
    methods = list(METHODS.items())
    total_tasks = len(questions) * len(methods)

    # Count already-completed tasks
    skipped = sum(
        1 for q in questions for m, _ in methods
        if is_complete(results_dir, q.id, m)
    )

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )
    overall = progress.add_task("Benchmark", total=total_tasks, completed=skipped)

    with Live(progress, console=console, refresh_per_second=4):
        for qi, question in enumerate(questions):
            for method_name, method_fn in methods:
                # Checkpoint: skip if already done
                if is_complete(results_dir, question.id, method_name):
                    continue

                progress.update(
                    overall,
                    description=f"[{qi + 1}/{len(questions)}] {question.id} / {method_name} (${cost_tracker.total_cost_usd:.2f})",
                )

                try:
                    result = await method_fn(question.question, client, config)
                    path = result_path(results_dir, question.id, method_name)
                    save_result(path, result)
                except Exception as e:
                    logger.error(f"Failed: {question.id}/{method_name}: {e}")
                    # Save error record so we can retry later
                    path = result_path(results_dir, question.id, method_name)
                    error_data = {
                        "method": method_name,
                        "question": question.question,
                        "error": str(e),
                        "final_answer": None,
                    }
                    with open(path.with_suffix(".error.json"), "w") as f:
                        json.dump(error_data, f, indent=2)

                progress.advance(overall)

    console.print()
    console.print(Panel(cost_tracker.summary(), title="Cost Summary", border_style="green"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 0 Benchmark Runner")
    parser.add_argument("--pilot", action="store_true", help="Run pilot (5 questions only)")
    parser.add_argument("--budget", choices=["small", "full"], default="full",
                        help="Model budget: small (Sonnet+GPT-4o, cheap) or full (Opus+GPT-5.2, SOTA)")
    parser.add_argument("--results-dir", default="results", help="Results directory")
    parser.add_argument("--questions", default=None, help="Path to questions.json")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Suppress httpx request logs that pollute the Rich live display
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    if args.verbose:
        logging.getLogger("phase0").setLevel(logging.DEBUG)

    config = BenchmarkConfig.with_budget(args.budget, results_dir=args.results_dir)

    if not config.anthropic_api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
        sys.exit(1)
    if not config.openai_api_key:
        console.print("[red]Error: OPENAI_API_KEY not set[/red]")
        sys.exit(1)

    questions_path = Path(args.questions) if args.questions else None
    if args.pilot:
        questions = load_pilot_questions(path=questions_path)
        console.print(f"[bold]Pilot run: {len(questions)} questions[/bold]")
    else:
        questions = load_questions(path=questions_path)
        console.print(f"[bold]Full benchmark: {len(questions)} questions[/bold]")

    console.print(f"Budget: [bold]{args.budget}[/bold] (claude={config.claude_model}, gpt={config.gpt_model})")
    console.print(f"Methods: {', '.join(METHODS.keys())}")
    console.print(f"Total tasks: {len(questions) * len(METHODS)}")
    console.print()

    cost_tracker = CostTracker()
    start = time.monotonic()
    asyncio.run(run_benchmark(questions, config, cost_tracker))
    elapsed = time.monotonic() - start

    console.print(f"\n[bold green]Done in {elapsed:.1f}s[/bold green]")


if __name__ == "__main__":
    main()
