# duh

**Multi-model consensus engine** -- because one LLM opinion isn't enough.

duh asks multiple LLMs the same question, forces them to challenge each other's answers, and produces a single revised response that's stronger than any individual model could generate alone.

## What it does

- **Proposes** -- The strongest available model answers your question
- **Challenges** -- Other models find genuine flaws (forced disagreement, no sycophancy allowed)
- **Revises** -- The proposer addresses every valid challenge and produces an improved answer

## Quick start

```bash
uv add duh
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
duh ask "What database should I use for a new SaaS product?"
```

## Features

- **Multi-model consensus** -- Claude and GPT debate. Sycophantic challenges are detected and flagged.
- **Voting protocol** -- Fan out to all models in parallel, aggregate answers via majority or weighted synthesis.
- **Query decomposition** -- Break complex questions into subtask DAGs, solve in parallel, synthesize results.
- **Decision taxonomy** -- Auto-classify decisions by intent, category, and genus for structured recall.
- **Outcome tracking** -- Record success/failure/partial feedback on past decisions.
- **Tool-augmented reasoning** -- Models can call web search, read files, and execute code during consensus.
- **Persistent memory** -- Every thread, contribution, decision, vote, and subtask stored in SQLite. Search with `duh recall`.
- **Cost tracking** -- Per-model token costs in real-time. Configurable warn threshold and hard limit.
- **Local models** -- Ollama and LM Studio via the OpenAI-compatible API. Mix cloud + local.
- **Rich CLI** -- Styled panels, spinners, and formatted output.

## Commands

```bash
duh ask "question"                      # Run consensus query
duh ask "question" --decompose          # Decompose into subtasks first
duh ask "question" --protocol voting    # Use voting protocol instead
duh ask "question" --protocol auto      # Auto-select protocol by question type
duh ask "question" --tools              # Enable tool use (web search, file read, code exec)
duh feedback <thread-id> --result success   # Record outcome for a decision
duh recall "keyword"                    # Search past decisions
duh threads                             # List past threads
duh show <thread-id>                    # Inspect full debate history
duh models                              # List available models
duh cost                                # Show cumulative costs
```

## How consensus works

```
PROPOSE  -->  CHALLENGE  -->  REVISE  -->  COMMIT
```

1. Strongest model proposes an answer
2. Other models challenge with forced disagreement (4 framing types: flaw, alternative, risk, devil's advocate)
3. Proposer revises, addressing each valid challenge
4. Decision extracted with confidence score and preserved dissent

Convergence detection (Jaccard similarity >= 0.7) stops early when challenges repeat.

### Voting protocol

```
FAN-OUT (all models)  -->  AGGREGATE (majority / weighted)
```

All models answer independently in parallel. A meta-judge (strongest model) picks the best answer (majority) or synthesizes all answers weighted by capability (weighted).

### Decomposition

```
DECOMPOSE  -->  SCHEDULE (topological sort)  -->  SYNTHESIZE
```

Complex questions are broken into a subtask DAG. Independent subtasks run in parallel. Results are synthesized into a final answer by the strongest model.

## Phase 0 benchmark

Before building duh, we validated the thesis: 50 questions, 4 methods, blind LLM-as-judge evaluation. Consensus consistently outperformed direct answers, self-debate, and ensemble approaches -- especially on questions requiring nuanced judgment and multi-perspective analysis. See [full benchmark results](docs/reference/benchmarks.md).

## Documentation

Full documentation: [docs/](docs/index.md)

- [Installation](docs/getting-started/installation.md)
- [Quickstart](docs/getting-started/quickstart.md)
- [How Consensus Works](docs/concepts/how-consensus-works.md)
- [CLI Reference](docs/cli/index.md)
- [Python API](docs/python-api/library-usage.md)
- [Docker Guide](docs/guides/docker.md)
- [Config Reference](docs/reference/config-reference.md)

## License

TBD
