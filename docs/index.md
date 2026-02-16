# duh -- Better answers through disagreement

**duh** is a multi-model consensus engine. It asks multiple LLMs the same question, forces them to challenge each other's answers, and produces a single revised response that's stronger than any individual model could generate alone.

## Why duh?

Every LLM has blind spots. Claude might miss a practical risk that GPT catches. GPT might oversimplify something Claude handles with nuance. When you ask one model, you get one perspective -- and no way to know what it missed.

duh fixes this by making models debate. The strongest model proposes an answer, other models challenge it with forced disagreement (no sycophantic "great answer!" allowed), and the proposer revises based on genuine criticism. The result is a consensus decision with tracked confidence and preserved dissent.

## How it works

```
PROPOSE  -->  CHALLENGE  -->  REVISE  -->  COMMIT
   |              |              |            |
   v              v              v            v
 Strongest    Other models    Proposer     Extract
  model       find flaws     addresses    decision,
 answers      (forced        challenges   confidence,
              disagreement)               dissent
```

If challenges in consecutive rounds are too similar (Jaccard similarity >= 0.7), duh detects convergence and stops early. Otherwise it runs up to the configured maximum rounds.

## Key features

- **Multi-model consensus** -- Claude and GPT (and local models) debate to produce better answers
- **Sycophancy detection** -- Flags challenges that defer to the proposal instead of genuinely disagreeing
- **Persistent memory** -- Every thread, contribution, and decision is stored in SQLite for later recall
- **Cost tracking** -- Per-model token costs displayed in real-time, with configurable warn/hard limits
- **Local model support** -- Use Ollama or LM Studio via the OpenAI-compatible API
- **Docker ready** -- Run in a container with persistent volume storage
- **Rich CLI** -- Styled panels, spinners, and formatted output via Rich

## Quick start

```bash
uv add duh
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
duh ask "What database should I use for a new SaaS product?"
```

## Learn more

- [Installation](getting-started/installation.md) -- Get duh running in 2 minutes
- [Quickstart](getting-started/quickstart.md) -- Your first consensus query
- [How Consensus Works](concepts/how-consensus-works.md) -- The 4-phase protocol explained
- [CLI Reference](cli/index.md) -- All commands and options
- [Python API](python-api/library-usage.md) -- Use duh as a library
