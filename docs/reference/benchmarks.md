# Benchmarks

Phase 0 benchmark results validating the core thesis: does multi-model consensus produce better answers than a single model?

## Methodology

50 questions across 5 categories, 4 methods compared:

| Method | Description | Models |
|--------|-------------|--------|
| **(A) Direct** | Single model, direct answer | Sonnet |
| **(B) Self-debate** | Same model proposes, critiques itself, synthesizes | Sonnet |
| **(C) Consensus** | Claude proposes, GPT challenges (forced disagreement), Claude revises | Sonnet + GPT-4o |
| **(D) Ensemble** | 3 parallel samples synthesized | Sonnet |

Evaluation used blind LLM-as-judge with two independent judges (GPT-4o + Sonnet).

## Results

The consensus method (C) consistently outperformed all other approaches:

- **Consensus vs Direct**: Consensus produced more thorough, nuanced answers with better coverage of trade-offs and practical considerations
- **Consensus vs Self-debate**: Cross-model challenge found genuine blind spots that self-critique missed
- **Consensus vs Ensemble**: Forced disagreement was more effective than statistical averaging of similar responses

## Key findings

1. **Cross-model challenges work** -- GPT finds real flaws in Claude's answers (and vice versa) that self-critique misses
2. **Forced disagreement is essential** -- Without explicit instructions to disagree, challengers tend toward sycophantic agreement
3. **Revision quality depends on challenge quality** -- Genuine challenges produce better revisions than polite suggestions
4. **Cost is reasonable** -- Consensus costs ~3x a direct answer but the quality improvement justifies it for important questions

## Exit criteria

The benchmark established clear thresholds:

- **PROCEED**: Consensus (C) clearly beats Direct (A) on judgment/strategy (>60% win rate)
- **ITERATE**: Consensus only marginally beats Self-Debate (B) -- refine prompts, re-test
- **STOP**: Consensus consistently loses -- thesis invalidated

Result: **PROCEED** -- consensus demonstrated clear advantages, especially on questions requiring nuanced judgment, risk assessment, and multi-perspective analysis.

## Running the benchmark

The benchmark suite is in the `phase0/` directory:

```bash
uv sync
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...

# Pilot run (5 questions)
uv run python -m phase0.runner --pilot

# Full benchmark (50 questions)
uv run python -m phase0.runner

# Judge results
uv run python -m phase0.judge

# Generate report
uv run python -m phase0.analyze
```

## Next steps

- [How Consensus Works](../concepts/how-consensus-works.md) -- The protocol built from these findings
- [Getting Started](../getting-started/quickstart.md) -- Try consensus yourself
