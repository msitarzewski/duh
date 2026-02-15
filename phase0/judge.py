"""Blind LLM-as-judge evaluator.

Protocol:
1. Randomize answer order per question (different shuffle each time)
2. Label as "Answer A", "Answer B", etc. — no method names
3. Judge rates on 5 dimensions (1-10)
4. Judge also ranks answers best-to-worst
5. Two independent judges: GPT-4o primary, Claude Sonnet secondary
6. Low temperature (0.3) for consistent judging
7. JSON structured output
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from phase0.config import BenchmarkConfig, CostTracker
from phase0.models import ModelClient
from phase0.prompts import JUDGE_SYSTEM, JUDGE_USER

logger = logging.getLogger(__name__)
console = Console()

LABELS = ["A", "B", "C", "D"]
METHOD_ORDER = ["direct", "self_debate", "consensus", "ensemble"]


def load_answers(results_dir: Path, question_id: str) -> dict[str, str]:
    """Load all method answers for a question."""
    answers = {}
    for method in METHOD_ORDER:
        path = results_dir / "raw" / question_id / f"{method}.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            if data.get("final_answer"):
                answers[method] = data["final_answer"]
    return answers


def build_judge_input(
    question: str, answers: dict[str, str]
) -> tuple[str, dict[str, str]]:
    """Shuffle answers and build the judge prompt. Returns (prompt, label_to_method mapping)."""
    methods = list(answers.keys())
    random.shuffle(methods)

    label_to_method = {}
    answer_blocks = []
    for i, method in enumerate(methods):
        label = LABELS[i]
        label_to_method[label] = method
        answer_blocks.append(f"--- Answer {label} ---\n{answers[method]}")

    answers_block = "\n\n".join(answer_blocks)
    prompt = JUDGE_USER.format(question=question, answers_block=answers_block)
    return prompt, label_to_method


def parse_judgment(content: str) -> dict | None:
    """Parse JSON judgment from judge response, handling markdown fences."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (fences)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse judge JSON: {text[:200]}...")
        return None


async def judge_question(
    question_id: str,
    question_text: str,
    answers: dict[str, str],
    client: ModelClient,
    config: BenchmarkConfig,
) -> dict:
    """Run both judges on a single question."""
    prompt, label_to_method = build_judge_input(question_text, answers)
    method_to_label = {v: k for k, v in label_to_method.items()}

    # Run both judges in parallel
    gpt_resp, sonnet_resp = await asyncio.gather(
        client.send(
            model=config.judge_gpt_model,
            system=JUDGE_SYSTEM,
            user=prompt,
            temperature=config.judge_temperature,
        ),
        client.send(
            model=config.judge_claude_model,
            system=JUDGE_SYSTEM,
            user=prompt,
            temperature=config.judge_temperature,
        ),
    )

    gpt_judgment = parse_judgment(gpt_resp.content)
    sonnet_judgment = parse_judgment(sonnet_resp.content)

    return {
        "question_id": question_id,
        "question": question_text,
        "label_to_method": label_to_method,
        "method_to_label": method_to_label,
        "gpt_judge": {
            "raw": gpt_resp.content,
            "parsed": gpt_judgment,
            "model": gpt_resp.model,
            "tokens": gpt_resp.input_tokens + gpt_resp.output_tokens,
            "cost": gpt_resp.cost_usd,
        },
        "claude_judge": {
            "raw": sonnet_resp.content,
            "parsed": sonnet_judgment,
            "model": sonnet_resp.model,
            "tokens": sonnet_resp.input_tokens + sonnet_resp.output_tokens,
            "cost": sonnet_resp.cost_usd,
        },
    }


async def run_judging(config: BenchmarkConfig, cost_tracker: CostTracker) -> None:
    """Judge all completed benchmark results."""
    results_dir = Path(config.results_dir)
    judgments_dir = results_dir / "judgments"
    judgments_dir.mkdir(parents=True, exist_ok=True)

    client = ModelClient(config, cost_tracker)

    # Find all questions with complete results
    raw_dir = results_dir / "raw"
    if not raw_dir.exists():
        console.print("[red]No raw results found. Run the benchmark first.[/red]")
        return

    question_dirs = sorted(raw_dir.iterdir())
    questions_to_judge = []

    for qdir in question_dirs:
        if not qdir.is_dir():
            continue
        question_id = qdir.name
        # Skip if already judged
        judgment_path = judgments_dir / f"{question_id}.json"
        if judgment_path.exists():
            continue
        # Check all methods have results
        answers = load_answers(results_dir, question_id)
        if len(answers) == len(METHOD_ORDER):
            # Load the question text from any result file
            with open(qdir / "direct.json") as f:
                question_text = json.load(f)["question"]
            questions_to_judge.append((question_id, question_text, answers))

    if not questions_to_judge:
        console.print("[yellow]No questions to judge (all done or incomplete).[/yellow]")
        return

    console.print(f"[bold]Judging {len(questions_to_judge)} questions with 2 judges each[/bold]")

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )
    task = progress.add_task("Judging", total=len(questions_to_judge))

    with Live(progress, console=console, refresh_per_second=4):
        for question_id, question_text, answers in questions_to_judge:
            progress.update(task, description=f"Judging {question_id} (${cost_tracker.total_cost_usd:.2f})")

            judgment = await judge_question(question_id, question_text, answers, client, config)

            judgment_path = judgments_dir / f"{question_id}.json"
            with open(judgment_path, "w") as f:
                json.dump(judgment, f, indent=2)

            progress.advance(task)

    console.print(f"\n[bold green]Judging complete. ${cost_tracker.total_cost_usd:.4f} spent.[/bold green]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 0 Judge")
    parser.add_argument("--budget", choices=["small", "full"], default="full",
                        help="Model budget: small (Sonnet+GPT-4o) or full (Opus+GPT-5.2)")
    parser.add_argument("--results-dir", default="results", help="Results directory")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    if args.verbose:
        logging.getLogger("phase0").setLevel(logging.DEBUG)

    config = BenchmarkConfig.with_budget(args.budget, results_dir=args.results_dir)

    if not config.anthropic_api_key or not config.openai_api_key:
        console.print("[red]Error: Both ANTHROPIC_API_KEY and OPENAI_API_KEY must be set[/red]")
        sys.exit(1)

    cost_tracker = CostTracker()
    start = time.monotonic()
    asyncio.run(run_judging(config, cost_tracker))
    elapsed = time.monotonic() - start
    console.print(f"Done in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
