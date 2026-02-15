# duh — Phase 0: Prove the Thesis

Does multi-model consensus actually produce better answers than a single model?

Before building any product, we validate the core thesis: if making Claude and GPT debate a question doesn't consistently beat asking Claude alone, the product should not be built.

## Benchmark

50 questions across 5 categories, 4 methods compared:

- **(A) Direct**: Single model, direct answer (Sonnet)
- **(B) Self-debate**: Same model proposes, critiques itself, synthesizes (Sonnet)
- **(C) Consensus**: Claude proposes, GPT challenges (forced disagreement), Claude revises (Sonnet + GPT-4o)
- **(D) Ensemble**: 3 parallel samples synthesized (Sonnet)

Blind LLM-as-judge evaluation with two independent judges (GPT-4o + Sonnet).

## Setup

```bash
uv sync
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
```

## Run

```bash
# Pilot run (5 questions)
uv run python -m phase0.runner --pilot

# Full benchmark (50 questions)
uv run python -m phase0.runner

# Judge results
uv run python -m phase0.judge

# Generate report
uv run python -m phase0.analyze
```

## Exit Criteria

- **PROCEED**: Consensus (C) clearly beats Direct (A) on judgment/strategy (>60% win rate)
- **ITERATE**: Consensus only marginally beats Self-Debate (B) — refine prompts, re-test
- **STOP**: Consensus consistently loses — thesis invalidated
