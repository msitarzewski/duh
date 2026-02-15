"""Question loader for Phase 0 benchmark."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Question:
    """A benchmark question."""

    id: str
    category: str
    question: str
    why: str  # Why this question tests consensus


def load_questions(path: Path | None = None) -> list[Question]:
    """Load questions from JSON file."""
    if path is None:
        path = Path(__file__).parent / "questions.json"
    with open(path) as f:
        data = json.load(f)
    return [
        Question(id=q["id"], category=q["category"], question=q["question"], why=q["why"])
        for q in data["questions"]
    ]


def load_pilot_questions(count: int = 5, path: Path | None = None) -> list[Question]:
    """Load first N questions for pilot run."""
    questions = load_questions(path)
    # Pick one from each category for diversity
    by_category: dict[str, list[Question]] = {}
    for q in questions:
        by_category.setdefault(q.category, []).append(q)

    pilot: list[Question] = []
    for category in sorted(by_category.keys()):
        if len(pilot) >= count:
            break
        pilot.append(by_category[category][0])
    return pilot
