"""Analysis and report generation for Phase 0 benchmark results."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()

METHOD_ORDER = ["direct", "self_debate", "consensus", "ensemble"]
METHOD_LABELS = {
    "direct": "(A) Direct",
    "self_debate": "(B) Self-Debate",
    "consensus": "(C) Consensus",
    "ensemble": "(D) Ensemble",
}
DIMENSIONS = ["accuracy", "completeness", "nuance", "specificity", "overall"]

CATEGORY_LABELS = {
    "judgment_strategy": "Judgment/Strategy",
    "risk_assessment": "Risk Assessment",
    "factual_reasoning": "Factual Reasoning",
    "creative_open": "Creative/Open-ended",
    "adversarial_tricky": "Adversarial/Tricky",
}


def load_judgments(results_dir: Path) -> list[dict]:
    """Load all judgment files."""
    judgments_dir = results_dir / "judgments"
    if not judgments_dir.exists():
        return []
    judgments = []
    for path in sorted(judgments_dir.glob("*.json")):
        with open(path) as f:
            judgments.append(json.load(f))
    return judgments


def load_question_categories(results_dir: Path) -> dict[str, str]:
    """Load question ID to category mapping from raw results or questions.json."""
    # Try questions.json first
    questions_path = Path(__file__).parent / "questions.json"
    if questions_path.exists():
        with open(questions_path) as f:
            data = json.load(f)
        return {q["id"]: q["category"] for q in data["questions"]}
    return {}


def extract_scores(judgment: dict, judge_key: str) -> dict[str, dict[str, int]] | None:
    """Extract per-method scores from a judgment. Returns {method: {dimension: score}}."""
    judge_data = judgment.get(judge_key, {})
    parsed = judge_data.get("parsed")
    if not parsed or "evaluations" not in parsed:
        return None

    label_to_method = judgment["label_to_method"]
    scores: dict[str, dict[str, int]] = {}

    for label, evals in parsed["evaluations"].items():
        method = label_to_method.get(label)
        if method:
            scores[method] = {dim: evals.get(dim, 0) for dim in DIMENSIONS}

    return scores


def extract_ranking(judgment: dict, judge_key: str) -> list[str] | None:
    """Extract ranking as list of methods (best to worst)."""
    judge_data = judgment.get(judge_key, {})
    parsed = judge_data.get("parsed")
    if not parsed or "ranking" not in parsed:
        return None

    label_to_method = judgment["label_to_method"]
    ranking = []
    for label in parsed["ranking"]:
        method = label_to_method.get(label)
        if method:
            ranking.append(method)
    return ranking


def compute_win_rates(judgments: list[dict], judge_key: str, category_filter: str | None = None) -> dict[str, float]:
    """Compute win rate (% of times each method is ranked #1)."""
    categories = load_question_categories(Path("results"))
    wins: dict[str, int] = defaultdict(int)
    total = 0

    for j in judgments:
        qid = j["question_id"]
        if category_filter and categories.get(qid) != category_filter:
            continue
        ranking = extract_ranking(j, judge_key)
        if ranking:
            wins[ranking[0]] += 1
            total += 1

    if total == 0:
        return {}
    return {method: wins[method] / total * 100 for method in METHOD_ORDER}


def compute_head_to_head(judgments: list[dict], judge_key: str, method_a: str, method_b: str, category_filter: str | None = None) -> dict[str, float]:
    """Head-to-head: % of times method_a beats method_b on overall score."""
    categories = load_question_categories(Path("results"))
    a_wins = 0
    b_wins = 0
    ties = 0

    for j in judgments:
        qid = j["question_id"]
        if category_filter and categories.get(qid) != category_filter:
            continue
        scores = extract_scores(j, judge_key)
        if not scores or method_a not in scores or method_b not in scores:
            continue
        sa = scores[method_a]["overall"]
        sb = scores[method_b]["overall"]
        if sa > sb:
            a_wins += 1
        elif sb > sa:
            b_wins += 1
        else:
            ties += 1

    total = a_wins + b_wins + ties
    if total == 0:
        return {"a_wins": 0, "b_wins": 0, "ties": 0, "total": 0}
    return {
        "a_wins": a_wins / total * 100,
        "b_wins": b_wins / total * 100,
        "ties": ties / total * 100,
        "total": total,
    }


def compute_avg_scores(judgments: list[dict], judge_key: str, category_filter: str | None = None) -> dict[str, dict[str, float]]:
    """Average dimension scores per method."""
    categories = load_question_categories(Path("results"))
    sums: dict[str, dict[str, float]] = {m: {d: 0.0 for d in DIMENSIONS} for m in METHOD_ORDER}
    counts: dict[str, int] = {m: 0 for m in METHOD_ORDER}

    for j in judgments:
        qid = j["question_id"]
        if category_filter and categories.get(qid) != category_filter:
            continue
        scores = extract_scores(j, judge_key)
        if not scores:
            continue
        for method in METHOD_ORDER:
            if method in scores:
                for dim in DIMENSIONS:
                    sums[method][dim] += scores[method].get(dim, 0)
                counts[method] += 1

    avgs: dict[str, dict[str, float]] = {}
    for method in METHOD_ORDER:
        if counts[method] > 0:
            avgs[method] = {dim: sums[method][dim] / counts[method] for dim in DIMENSIONS}
    return avgs


def compute_inter_judge_agreement(judgments: list[dict]) -> float:
    """Compute agreement rate between GPT and Sonnet judges on the winner."""
    agree = 0
    total = 0
    for j in judgments:
        gpt_ranking = extract_ranking(j, "gpt_judge")
        sonnet_ranking = extract_ranking(j, "claude_judge")
        if gpt_ranking and sonnet_ranking:
            if gpt_ranking[0] == sonnet_ranking[0]:
                agree += 1
            total += 1
    return agree / total * 100 if total > 0 else 0


def compute_cost_summary(results_dir: Path) -> dict[str, float]:
    """Compute total cost per method from raw results."""
    costs: dict[str, float] = defaultdict(float)
    raw_dir = results_dir / "raw"
    if not raw_dir.exists():
        return {}
    for qdir in raw_dir.iterdir():
        if not qdir.is_dir():
            continue
        for method in METHOD_ORDER:
            path = qdir / f"{method}.json"
            if path.exists():
                with open(path) as f:
                    data = json.load(f)
                costs[method] += data.get("total_cost_usd", 0)
    return dict(costs)


def generate_report(results_dir: Path) -> str:
    """Generate the full analysis report as markdown."""
    judgments = load_judgments(results_dir)
    categories = load_question_categories(results_dir)

    if not judgments:
        return "# Phase 0 Analysis\n\nNo judgments found. Run the judge first."

    lines: list[str] = []
    lines.append("# Phase 0 Benchmark Results")
    lines.append("")
    lines.append(f"**Questions evaluated**: {len(judgments)}")
    lines.append(f"**Methods**: {', '.join(METHOD_LABELS.values())}")
    lines.append(f"**Judges**: GPT-4o (primary), Claude Opus (secondary)")
    lines.append("")

    # --- Win Rates ---
    lines.append("## Overall Win Rates (% ranked #1)")
    lines.append("")
    for judge_key, judge_name in [("gpt_judge", "GPT-4o Judge"), ("claude_judge", "Opus Judge")]:
        lines.append(f"### {judge_name}")
        lines.append("")
        win_rates = compute_win_rates(judgments, judge_key)
        lines.append("| Method | Win Rate |")
        lines.append("|--------|----------|")
        for method in METHOD_ORDER:
            rate = win_rates.get(method, 0)
            marker = " **" if method == "consensus" else ""
            lines.append(f"| {METHOD_LABELS[method]} | {rate:.1f}%{marker}{'**' if marker else ''} |")
        lines.append("")

    # --- Win Rates by Category ---
    lines.append("## Win Rates by Category (GPT-4o Judge)")
    lines.append("")
    for cat, cat_label in CATEGORY_LABELS.items():
        win_rates = compute_win_rates(judgments, "gpt_judge", category_filter=cat)
        if not win_rates:
            continue
        lines.append(f"### {cat_label}")
        lines.append("")
        lines.append("| Method | Win Rate |")
        lines.append("|--------|----------|")
        for method in METHOD_ORDER:
            rate = win_rates.get(method, 0)
            lines.append(f"| {METHOD_LABELS[method]} | {rate:.1f}% |")
        lines.append("")

    # --- Head-to-Head: Consensus vs Direct ---
    lines.append("## Head-to-Head: Consensus (C) vs Direct (A)")
    lines.append("")
    lines.append("*The core thesis test: does multi-model consensus beat a single model?*")
    lines.append("")
    for judge_key, judge_name in [("gpt_judge", "GPT-4o"), ("claude_judge", "Opus")]:
        h2h = compute_head_to_head(judgments, judge_key, "consensus", "direct")
        lines.append(f"**{judge_name}**: Consensus wins {h2h['a_wins']:.1f}%, Direct wins {h2h['b_wins']:.1f}%, Ties {h2h['ties']:.1f}% (n={int(h2h['total'])})")
    lines.append("")

    # By category
    lines.append("### By Category (GPT-4o)")
    lines.append("")
    lines.append("| Category | Consensus Wins | Direct Wins | Ties |")
    lines.append("|----------|---------------|-------------|------|")
    for cat, cat_label in CATEGORY_LABELS.items():
        h2h = compute_head_to_head(judgments, "gpt_judge", "consensus", "direct", category_filter=cat)
        if h2h["total"] > 0:
            lines.append(f"| {cat_label} | {h2h['a_wins']:.1f}% | {h2h['b_wins']:.1f}% | {h2h['ties']:.1f}% |")
    lines.append("")

    # --- Head-to-Head: Consensus vs Self-Debate ---
    lines.append("## Head-to-Head: Consensus (C) vs Self-Debate (B)")
    lines.append("")
    lines.append("*Why not just one model? Does cross-model challenge add value over self-critique?*")
    lines.append("")
    for judge_key, judge_name in [("gpt_judge", "GPT-4o"), ("claude_judge", "Opus")]:
        h2h = compute_head_to_head(judgments, judge_key, "consensus", "self_debate")
        lines.append(f"**{judge_name}**: Consensus wins {h2h['a_wins']:.1f}%, Self-Debate wins {h2h['b_wins']:.1f}%, Ties {h2h['ties']:.1f}% (n={int(h2h['total'])})")
    lines.append("")

    # --- Average Dimension Scores ---
    lines.append("## Average Scores by Dimension (GPT-4o Judge)")
    lines.append("")
    avg_scores = compute_avg_scores(judgments, "gpt_judge")
    if avg_scores:
        header = "| Method | " + " | ".join(d.capitalize() for d in DIMENSIONS) + " |"
        sep = "|--------|" + "|".join("-------" for _ in DIMENSIONS) + "|"
        lines.append(header)
        lines.append(sep)
        for method in METHOD_ORDER:
            if method in avg_scores:
                scores_str = " | ".join(f"{avg_scores[method][d]:.2f}" for d in DIMENSIONS)
                lines.append(f"| {METHOD_LABELS[method]} | {scores_str} |")
        lines.append("")

    # --- Inter-Judge Agreement ---
    agreement = compute_inter_judge_agreement(judgments)
    lines.append("## Inter-Judge Agreement")
    lines.append("")
    lines.append(f"GPT-4o and Sonnet agree on the winner **{agreement:.1f}%** of the time.")
    lines.append("")

    # --- Cost ---
    lines.append("## Cost Summary")
    lines.append("")
    costs = compute_cost_summary(results_dir)
    total_method_cost = sum(costs.values())
    lines.append("| Method | Cost |")
    lines.append("|--------|------|")
    for method in METHOD_ORDER:
        lines.append(f"| {METHOD_LABELS[method]} | ${costs.get(method, 0):.4f} |")
    lines.append(f"| **Total (methods)** | **${total_method_cost:.4f}** |")
    lines.append("")

    # Judging costs
    judge_cost = sum(
        j.get("gpt_judge", {}).get("cost", 0) + j.get("claude_judge", {}).get("cost", 0)
        for j in judgments
    )
    lines.append(f"Judging cost: ${judge_cost:.4f}")
    lines.append(f"**Grand total: ${total_method_cost + judge_cost:.4f}**")
    lines.append("")

    # --- Exit Decision ---
    lines.append("## Exit Decision")
    lines.append("")
    consensus_js_win = compute_win_rates(judgments, "gpt_judge", category_filter="judgment_strategy")
    consensus_rate = consensus_js_win.get("consensus", 0)
    h2h_vs_direct = compute_head_to_head(judgments, "gpt_judge", "consensus", "direct", category_filter="judgment_strategy")
    h2h_vs_self = compute_head_to_head(judgments, "gpt_judge", "consensus", "self_debate")

    lines.append(f"- Consensus win rate on Judgment/Strategy: **{consensus_rate:.1f}%** (target: >60%)")
    lines.append(f"- Consensus vs Direct on J/S: **{h2h_vs_direct['a_wins']:.1f}%** wins")
    lines.append(f"- Consensus vs Self-Debate overall: **{h2h_vs_self['a_wins']:.1f}%** wins")
    lines.append("")

    if h2h_vs_direct["a_wins"] >= 60:
        lines.append("**PROCEED** — Consensus clearly beats Direct on judgment/strategy tasks.")
    elif h2h_vs_direct["a_wins"] >= 45:
        lines.append("**ITERATE** — Consensus shows promise but needs prompt refinement.")
    else:
        lines.append("**STOP** — Consensus does not beat Direct. Thesis not validated with current approach.")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 0 Analysis")
    parser.add_argument("--results-dir", default="results", help="Results directory")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    report = generate_report(results_dir)

    # Save report
    analysis_dir = results_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    report_path = analysis_dir / "report.md"
    with open(report_path, "w") as f:
        f.write(report)

    console.print(report)
    console.print(f"\n[bold green]Report saved to {report_path}[/bold green]")


if __name__ == "__main__":
    main()
