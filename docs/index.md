# duh -- Better answers through disagreement

**duh** is a multi-model consensus engine. It asks multiple LLMs the same question, forces them to challenge each other's answers, and produces a single revised response that's stronger than any individual model could generate alone.

## Why duh?

Every LLM has blind spots. Claude might miss a practical risk that GPT catches. GPT might oversimplify something Claude handles with nuance. When you ask one model, you get one perspective -- and no way to know what it missed.

duh fixes this by making models debate. The strongest model proposes an answer, other models challenge it with forced disagreement (no sycophantic "great answer!" allowed), and the proposer revises based on genuine criticism. The result is a consensus decision with tracked confidence and preserved dissent.

## How it works

**Consensus protocol** (default):

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

**Voting protocol** (`--protocol voting`): Fan out the question to all models in parallel, then a meta-judge picks or synthesizes the best answer.

**Decomposition** (`--decompose`): Break a complex question into a DAG of subtasks, solve each independently, and merge the results.

## Key features

- **Multi-model consensus** -- Claude, GPT, and Gemini (and local models) debate to produce better answers
- **Voting protocol** -- Fan out a question to all models in parallel and aggregate the best answer (majority or weighted)
- **Query decomposition** -- Break complex questions into subtask DAGs, solve each with consensus, and synthesize a final answer
- **Tool-augmented reasoning** -- Models can use web search, code execution, and file read during PROPOSE and CHALLENGE phases
- **Decision taxonomy** -- Auto-classify decisions by intent, category, and genus for structured recall
- **Outcome tracking** -- Record whether a past decision led to success, failure, or partial results with `duh feedback`
- **Sycophancy detection** -- Flags challenges that defer to the proposal instead of genuinely disagreeing
- **Persistent memory** -- Every thread, contribution, decision, vote, and outcome is stored in SQLite for later recall
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
