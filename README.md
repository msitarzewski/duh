# duh

**The trust layer for AI applications.**

duh is a multi-model consensus engine that sits between your application and LLM providers — arbitrating, verifying, and scoring AI outputs before they reach your users. Think of it as the Cloudflare of AI: a verification and routing layer that makes the models behind it trustworthy.

## Why this exists

Single-model answers are fragile. They hallucinate. They carry training bias. They give you no way to audit why a conclusion was reached. And if your only provider goes down or changes behavior, you're exposed.

Models are commoditizing. The value is moving above the model layer — into orchestration, verification, and trust. duh captures that layer.

The output isn't "an AI answer." It's confidence-scored analysis with adversarial fact-checking and preserved dissent. Every decision records who proposed what, who challenged it, what survived review, and what the dissenting positions were. This is transformative synthesis, not answer aggregation.

## What it does

```
PROPOSE  -->  CHALLENGE  -->  REVISE  -->  COMMIT
```

1. **Propose** -- The strongest available model answers your question
2. **Challenge** -- Other models find genuine flaws (forced disagreement, no sycophancy allowed)
3. **Revise** -- The proposer addresses every valid challenge
4. **Commit** -- Decision extracted with confidence score, intent classification, and preserved dissent

Every step is stored. Every challenge is attributed. Every confidence score is domain-capped and calibrated against historical outcomes.

## How to use it

duh runs anywhere in your stack:

| Interface | Use case |
|-----------|----------|
| **CLI** | `duh ask "question"` -- interactive consensus from the terminal |
| **REST API** | `POST /api/ask` -- integrate into any application, any language |
| **WebSocket** | Real-time streaming -- watch models debate live |
| **Python client** | `pip install duh-client` -- async and sync wrappers |
| **MCP server** | `duh mcp` -- AI agent integration via Model Context Protocol |
| **Web UI** | `duh serve` -- consensus streaming, thread browser, 3D decision space |

## Quick start

```bash
uv add duh
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GOOGLE_API_KEY=AIza...          # optional: Gemini models
export PERPLEXITY_API_KEY=pplx-...     # optional: Sonar models (challenger-only)
duh ask "What database should I use for a new SaaS product?"
```

Or use a `.env` file (see `.env.example`).

## Features

### Consensus & reasoning
- **Multi-model consensus** -- Claude, GPT, Gemini, Mistral, and Perplexity debate. Sycophantic challenges detected and flagged.
- **Voting protocol** -- Fan out to all models in parallel, aggregate via majority or weighted synthesis.
- **Query decomposition** -- Break complex questions into subtask DAGs, solve in parallel, synthesize results.
- **Protocol auto-selection** -- Classifies your question and routes to consensus (reasoning) or voting (judgment) automatically.
- **Question refinement** -- Pre-consensus clarification step catches ambiguous questions before they waste model calls.
- **Convergence detection** -- Early exit when challenges repeat (Jaccard similarity >= 0.7). No wasted rounds.

### Trust & verification
- **Epistemic confidence** -- Rigor scoring (0.5-1.0) + domain-capped confidence (factual 95%, technical 90%, creative 85%, judgment 80%, strategic 70%). Calibrated against historical outcomes via ECE tracking.
- **Sycophancy detection** -- Identifies deference markers in challenges. Rubber-stamp agreements are flagged, not counted.
- **Preserved dissent** -- Minority positions are extracted and attributed by model. Disagreement is a feature, not a bug.
- **Decision taxonomy** -- Auto-classify decisions by intent, category, and genus for structured recall.
- **Outcome tracking** -- Record success/failure/partial feedback. Calibration improves over time.

### Grounding & tools
- **Native web search** -- Anthropic, Google, Mistral, and Perplexity search server-side during consensus. Citations extracted, persisted, and displayed with domain grouping.
- **Tool-augmented reasoning** -- Web search, file read, and code execution available to models during any phase.
- **Citations** -- Deduplicated, grouped by hostname, attributed by phase (propose/challenge/revise). Displayed in CLI, Web UI, and API responses.

### Web UI
- **Live consensus streaming** -- Watch models debate in real-time via WebSocket. Challengers stream in as they finish (parallel, not batched).
- **Thread browser** -- Search, filter, and revisit past consensus threads with full debate history. Thread detail view mirrors the live consensus view with phase-grouped rendering and phase-level navigation.
- **3D decision space** -- Interactive scatter plot of decisions by confidence, rigor, and category. InstancedMesh handles 1000+ points.
- **Calibration dashboard** -- ECE analysis, accuracy by confidence bucket, overall calibration rating.
- **Shareable threads** -- Public share links for consensus results (no auth required).
- **Executive overview** -- Auto-generated summary of key decision points after consensus completes.

### Infrastructure
- **17 models across 5 providers** -- Claude (Opus/Sonnet/Haiku), GPT (5.4/5.2/5 mini/o3), Gemini (3.1 Pro/3 Pro/3 Flash/2.5 Pro/2.5 Flash), Mistral (Large/Medium/Small/Codestral), Perplexity (Sonar/Sonar Pro/Reasoning Pro/Deep Research).
- **Local models** -- Ollama and LM Studio via the OpenAI-compatible API. Mix cloud and local in the same consensus.
- **Authentication** -- JWT auth with user accounts, RBAC (admin/contributor/viewer), password reset via SMTP email.
- **Persistent memory** -- SQLite or PostgreSQL. Every thread, turn, contribution, decision, vote, subtask, and citation stored.
- **Cost tracking** -- Per-model token costs in real-time with warn thresholds and hard limits.
- **Export** -- Threads as JSON, Markdown, or PDF. PDF features branded cover page, styled table of contents with dot-leader links, colored section headers, phase-grouped contributions (PROPOSE/CHALLENGE/REVISE), confidence/rigor meters, and consolidated sources with clickable URLs.
- **Batch processing** -- Process multiple questions from a file with any protocol.
- **Backup & restore** -- SQLite copy or JSON export, with merge mode for restores.

## Protocols

### Consensus (default)

```
PROPOSE  -->  CHALLENGE  -->  REVISE  -->  COMMIT
```

Strongest model proposes. Others challenge with forced disagreement (4 framing types: flaw, alternative, risk, devil's advocate). Proposer revises, addressing each valid challenge. Decision extracted with confidence score and preserved dissent.

Convergence detection (Jaccard similarity >= 0.7) stops early when challenges repeat.

### Voting

```
FAN-OUT (all models)  -->  AGGREGATE (majority / weighted)
```

All models answer independently in parallel. A meta-judge picks the best answer (majority) or synthesizes all answers weighted by capability (weighted).

### Decomposition

```
DECOMPOSE  -->  SCHEDULE (topological sort)  -->  SYNTHESIZE
```

Complex questions are broken into a subtask DAG. Independent subtasks run in parallel. Results synthesized by the strongest model.

## Commands

### Consensus

```bash
duh ask "question"                        # Run consensus (default protocol)
duh ask "question" --refine               # Clarify ambiguous questions first
duh ask "question" --decompose            # Decompose into subtasks first
duh ask "question" --protocol voting      # Use voting protocol
duh ask "question" --protocol auto        # Auto-select by question type
duh ask "question" --tools                # Enable tool use (on by default)
duh ask "question" --no-tools             # Disable tool use
duh ask "question" --rounds 5             # Override max consensus rounds
duh ask "question" --proposer anthropic:claude-opus-4-6   # Override proposer
duh ask "question" --challengers openai:gpt-5.4,google:gemini-3.1-pro  # Override challengers
duh ask "question" --panel anthropic:claude-opus-4-6,openai:gpt-5.4    # Restrict model panel
```

### Memory & recall

```bash
duh recall "keyword"                      # Search past decisions
duh recall "keyword" --limit 20           # Limit results
duh threads                               # List past threads
duh threads --status complete --limit 50  # Filter by status
duh show <thread-id>                      # Full debate history (prefix match OK)
duh feedback <id> --result success        # Record outcome
duh feedback <id> --result failure --notes "..."  # With notes
```

### Export & data

```bash
duh export <thread-id>                    # Export as JSON (default)
duh export <thread-id> --format markdown  # Export as Markdown
duh export <thread-id> --format pdf -o report.pdf  # Export as PDF
duh export <thread-id> --content decision # Decision only (vs full)
duh export <thread-id> --no-dissent       # Suppress dissent section
duh backup ./backup.db                    # Backup database
duh backup ./backup.json --format json    # Backup as JSON
duh restore ./backup.db                   # Restore (replace)
duh restore ./backup.db --merge           # Restore (merge with existing)
```

### Models & cost

```bash
duh models                                # List all available models
duh cost                                  # Cumulative cost breakdown by model
```

### Calibration

```bash
duh calibration                           # Confidence calibration analysis
duh calibration --category technical      # Filter by category
duh calibration --since 2026-01-01        # Filter by date range
```

### Server & integrations

```bash
duh serve                                 # Start REST API + Web UI
duh serve --host 0.0.0.0 --port 9000     # Custom host/port
duh serve --reload                        # Auto-reload for development
duh mcp                                   # Start MCP server for AI agents
duh batch questions.txt                   # Batch consensus (text file)
duh batch questions.jsonl --format json   # Batch with JSON output
duh batch questions.txt --protocol voting # Batch with voting protocol
```

### User management

```bash
duh user-create --email u@x.com --password ...  # Create user
duh user-list                             # List users
```

## REST API

```
POST /api/ask              Consensus query (any protocol)
POST /api/refine           Analyze question for ambiguity
POST /api/enrich           Rewrite question with clarifications
GET  /api/threads          List threads (filter by status)
GET  /api/threads/:id      Thread with full debate history + citations
GET  /api/share/:token     Public thread view (no auth)
GET  /api/threads/:id/export  Export as PDF or Markdown
GET  /api/recall           Search past decisions
POST /api/feedback         Record outcome
GET  /api/models           List available models
GET  /api/cost             Cost breakdown by model
GET  /api/calibration      Confidence calibration analysis
GET  /api/decisions/space  Decision space data (3D viz)
WS   /ws/ask               Stream consensus in real-time
```

API key auth, rate limiting, and JWT authentication included. Full reference: [docs/api-reference.md](docs/api-reference.md).

## Supported models

| Provider | Models | Context | Notes |
|----------|--------|---------|-------|
| **Anthropic** | Claude Opus 4.6, Sonnet 4.6, Sonnet 4.5, Haiku 4.5 | 200K | Native web search |
| **OpenAI** | GPT-5.4, GPT-5.2, GPT-5 mini, o3 | 200K-1M | Search on select models |
| **Google** | Gemini 3.1 Pro, 3 Pro, 3 Flash, 2.5 Pro, 2.5 Flash | 1M | Native grounding search |
| **Mistral** | Large, Medium, Small, Codestral | 128-256K | Native web search |
| **Perplexity** | Sonar, Sonar Pro, Reasoning Pro, Deep Research | 128-200K | Always searches (challenger-only) |
| **Local** | Any Ollama or LM Studio model | Varies | Via OpenAI-compatible API |

Set API keys as environment variables or in `.env`. Models are auto-discovered from available keys.

## Phase 0 benchmark

Before building duh, we validated the thesis: 50 questions, 4 methods, blind LLM-as-judge evaluation. Consensus consistently outperformed direct answers, self-debate, and ensemble approaches -- especially on questions requiring nuanced judgment and multi-perspective analysis. See [full benchmark results](docs/reference/benchmarks.md).

## Documentation

Full documentation: [docs/](docs/index.md)

- [Installation](docs/getting-started/installation.md)
- [Quickstart](docs/getting-started/quickstart.md)
- [How Consensus Works](docs/concepts/how-consensus-works.md)
- [CLI Reference](docs/cli/index.md)
- [REST API Reference](docs/api-reference.md)
- [Python Client](docs/python-client.md)
- [MCP Server](docs/mcp-server.md)
- [Batch Mode](docs/batch-mode.md)
- [Export](docs/export.md)
- [Python API](docs/python-api/library-usage.md)
- [Docker Guide](docs/guides/docker.md)
- [Authentication](docs/guides/authentication.md)
- [Config Reference](docs/reference/config-reference.md)

## Hosted service

**[duh.bot](https://duh.bot)** -- commercial hosted consensus. Pay-per-question, no infrastructure to manage. Same engine, managed for you.

## Sponsor

If duh is useful to you, consider [sponsoring the project](https://github.com/sponsors/msitarzewski).

## License

[AGPL-3.0](LICENSE) -- Run it yourself (open source) or use the hosted service at [duh.bot](https://duh.bot).
