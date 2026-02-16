# Progress

**Last Updated**: 2026-02-15

---

## Current State: Phase 0 COMPLETE — Exit Decision PROCEED — Starting v0.1

### What's Built

Phase 0 benchmark framework — fully functional, pilot-tested on 5 questions.

**Files** (`phase0/`):
- `config.py` — Pydantic config, budget presets (`--budget small|full`), cost tracking with per-model pricing
- `models.py` — Async `ModelClient` wrapping `anthropic.AsyncAnthropic` + `openai.AsyncOpenAI`, retries with backoff, normalized `ModelResponse`
- `prompts.py` — All prompt templates with date grounding injected into every system prompt. Forced disagreement challenger, self-debate critic, ensemble synthesizer, blind judge
- `methods.py` — 4 benchmark methods: Direct (A), Self-Debate (B), Consensus (C), Ensemble (D)
- `questions.py` — Question loader with pilot selection (one per category)
- `questions.json` — 50 benchmark questions across 5 categories (15 judgment/strategy, 10 risk, 10 factual reasoning, 10 creative, 5 adversarial)
- `runner.py` — Orchestrator with checkpointing (resume from interrupts), Rich progress display, `--pilot`/`--budget` flags
- `judge.py` — Blind LLM-as-judge: randomized answer order, 2 independent judges, JSON structured output, `--budget` flag
- `analyze.py` — Win rates, head-to-head, per-category breakdown, dimension scores, inter-judge agreement, cost summary, auto exit decision

**Project root**:
- `pyproject.toml` — `uv`-managed, deps: anthropic, openai, pydantic, pydantic-settings, rich
- `.gitignore` — Python, .env, results/
- `README.md` — Setup + usage

### Pilot Run Results

- 5 questions (one per category), `--budget small` (Sonnet + GPT-4o)
- 55 API calls, 168,862 tokens, $1.64, ~31 minutes
- Runner checkpointing works, progress display clean (httpx logs suppressed)
- First results looked promising — user said "The first test was amazing"

### Budget Presets

| Preset | Claude Model | GPT Model | Est. Pilot Cost | Est. Full Cost |
|--------|-------------|-----------|-----------------|----------------|
| `small` | Sonnet 4.5 | GPT-4o | ~$2 | ~$15 |
| `full` | Opus 4.6 | GPT-5.2 | ~$10 | ~$60 |

### Benchmark Results

- 17 questions evaluated (partial 50-question run, stopped early — sufficient signal)
- Methods run with `--budget full` (Opus 4.6 + GPT-5.2), judging with `--budget small` (Sonnet + GPT-4o)
- **Consensus beats Direct** head-to-head: 47% vs 41% (GPT judge), 88% vs 6% (Opus judge)
- **Consensus beats Self-Debate**: 76.5% wins — cross-model challenge > self-critique
- Consensus higher on all dimensions: accuracy, completeness, nuance, specificity, overall
- Total cost: $7.19 (methods $6.01 + judging $1.17)
- **Exit decision: PROCEED**

---

## Milestone History

| Date | Milestone | Status |
|------|-----------|--------|
| 2026-02-15 | Memory bank + roadmap created by 4-agent team | Done |
| 2026-02-15 | Phase 0 implementation complete | Done |
| 2026-02-15 | Pilot run successful (5 Qs, small budget) | Done |
| 2026-02-15 | Benchmark run (17 Qs) + exit decision: PROCEED | Done |
| 2026-02-15 | v0.1 Task 1: Project scaffolding | Done |
| 2026-02-15 | v0.1 Task 2: Core error hierarchy | Done |
| 2026-02-15 | v0.1 Task 3: Provider adapter interface | Done |
| 2026-02-15 | v0.1 Task 4: Configuration | Done |
| 2026-02-15 | v0.1 Task 5: Mock provider + test fixtures | Done |
| 2026-02-15 | v0.1 Task 6: Anthropic adapter | Done |
| 2026-02-15 | v0.1 Task 7: OpenAI adapter (GPT + Ollama) | Done |
| 2026-02-15 | v0.1 Task 8: Retry with backoff utility | Done |
| TBD | v0.1.0 — "It Works & Remembers" | In Progress |
