# duh Roadmap

**Version**: 1.3
**Date**: 2026-02-16
**Status**: Draft for review
**Synthesized from**: Product Strategy, Systems Architecture, Devil's Advocate Review, Competitive Research Analysis

---

## Preamble: What This Roadmap Represents

This roadmap was produced by an agent team of four specialists who debated and challenged each other:

- **Product Strategist** defined releases, milestones, and go-to-market
- **Systems Architect** designed the technical blueprint
- **Devil's Advocate** challenged every decision and found gaps
- **Research Analyst** cross-referenced against competitive landscape and academic research

Key adjustments from the debate:

1. **Added Phase 0**: The devil's advocate argued — convincingly — that the core thesis must be validated with a simple script before any product code is written. The ICLR 2025 MAD evaluation and the Self-MoA paper (Princeton 2025) both challenge naive multi-model debate. We prove it works first.
2. **Reduced scope for 1.0**: The original plan had 10 releases reaching federation and knowledge base. The devil's advocate correctly identified this as "three products, not one." 1.0 is now a complete single-instance product. Federation and knowledge base are 2.0.
3. **Incorporated Self-MoA finding**: The research analyst surfaced a Princeton 2025 paper showing same-model ensembles outperform multi-model mixing by 6.6%. The consensus engine now supports both modes.
4. **Added sycophancy detection**: Research (CONSENSAGENT, ACL 2025) shows sycophancy is a measured engineering problem. Static challenge prompts aren't enough.
5. **Added hybrid decision protocol**: ACL 2025 research shows voting beats consensus by 13.2% on reasoning tasks. The engine supports both.
6. **Accelerated knowledge accumulation**: The research analyst identified persistent knowledge as the strongest differentiator. Some v0.2 features pulled into v0.1.
7. **Extended timeline**: Recalibrated for autonomous AI development (see below).
8. **Testing mandate**: Every public function and method gets unit tests. No exceptions. Tests are written alongside code, not after. Coverage gates enforced in CI.

### Labor Model & Timeline Basis

**This project will be built by autonomous AI agents (Claude Code with full autonomy). No human will likely touch the code.** All timelines are in AI-time — continuous autonomous execution sessions, not human work-weeks.

AI-time characteristics:
- An agent can scaffold a module, write implementation, write tests, and iterate on failures in a single session
- The bottleneck is thinking quality and architectural coherence, not typing speed
- A "day" of AI-time is roughly 4-8 hours of autonomous execution (accounting for rate limits, tool latency, and human review checkpoints)
- Complex integration work and debugging still takes real time — async calls to external APIs, provider-specific edge cases, UI rendering issues

---

## Table of Contents

1. [Phase 0: Prove the Thesis](#phase-0-prove-the-thesis)
2. [Release Plan (v0.1.0 - v1.0.0)](#release-plan)
3. [Technical Architecture Summary](#technical-architecture-summary)
4. [Risk Register](#risk-register)
5. [Go-to-Market Strategy](#go-to-market-strategy)
6. [Success Metrics](#success-metrics)
7. [Open Questions](#open-questions)
8. [Appendix: Competitive Position](#appendix-competitive-position)

---

## Phase 0: Prove the Thesis

**AI-time**: 1-2 sessions (1-2 days)
**Cost**: ~$50-100 in API credits + agent compute
**Output**: Published benchmark results

Before writing any product code, validate the core thesis with a 100-line script.

### What to Build

```
minimum_viable_proof.py (~100 lines)
- Takes a question as input
- Gets proposals from Claude and GPT
- Each model challenges the other's proposal (forced disagreement)
- A synthesizer model produces a final answer
- Saves results for comparison
```

### Benchmark Protocol

1. Curate 50 diverse questions across categories:
   - Judgment calls (architecture decisions, strategy, trade-offs)
   - Factual reasoning (multi-step logic, math, science)
   - Risk assessment (what could go wrong scenarios)
   - Creative/open-ended (design, brainstorming)
2. For each question, generate four outputs:
   - (A) Single model, direct answer (Claude Opus)
   - (B) Single model, self-debate (Claude prompted to argue multiple perspectives)
   - (C) Multi-model consensus (Claude + GPT, structured debate)
   - (D) Same-model ensemble (Claude x3 with high temperature, synthesized)
3. Blind evaluation: 5+ evaluators rate outputs without knowing which method produced them
4. Publish results — this becomes the launch blog post

### Exit Criteria

- If (C) multi-model consensus clearly beats (A) single model on judgment/strategy questions: **proceed to v0.1.0**
- If (C) only marginally beats (B) self-debate: **pivot protocol design, iterate prompts, re-test**
- If (C) consistently loses to (A) or (B): **stop — the thesis is invalidated for the current approach**

### Why This Matters

The devil's advocate correctly identified this as the existential risk: "If this script doesn't consistently produce better answers than asking Claude alone, the product should not be built." The ICLR 2025 MAD evaluation found current frameworks "fail to consistently outperform simple single-agent test-time computation strategies." We must prove we're different before building infrastructure.

---

## Release Plan

### Overview

| Version | Theme | Key Deliverable | AI-Time Estimate | Status |
|---------|-------|-----------------|-----------------|--------|
| **0.1.0** | It Works & Remembers | Consensus CLI with basic persistence | 5-8 days | **COMPLETE** |
| **0.2.0** | It Thinks Deeper | Task decomposition, outcome tracking | 4-6 days | **COMPLETE** |
| **0.3.0** | It's Accessible | REST API, MCP server, Python client | 4-6 days | |
| **0.4.0** | It Has a Face | Web UI with real-time consensus display | 6-10 days | |
| **0.5.0** | It Scales | Multi-user, PostgreSQL, production hardening | 4-6 days | |
| **1.0.0** | duh. | Stable APIs, documentation, security audit | 5-8 days | |

**Total AI-time**: ~30-46 days of autonomous execution (not calendar days — depends on session frequency and human review cadence)

**Calendar time**: With daily sessions and periodic human review, roughly 6-10 weeks to 1.0. With less frequent sessions, longer. The bottleneck is human review checkpoints, not AI execution speed.

**Post-1.0 (2.0 cycle)**: Federation, knowledge base, research mode, navigator protocol

### Bootstrapping: When duh Builds Itself

See [Section: Self-Building Milestone](#self-building-milestone) below the release plan.

---

### v0.1.0 — "It Works & Remembers"

**AI-time**: 5-8 days (largest release — foundational scaffolding, all core abstractions, full test suite)
**Theme**: Prove consensus works as a product. Include basic knowledge accumulation from day one.

The devil's advocate argued v0.1 without persistence is "a novelty with no retention hook." The research analyst confirmed persistent knowledge is the strongest differentiator. Decision: merge basic decision storage and recall from the original v0.2 into v0.1.

#### What Ships

**Providers** (3):
- Anthropic (Claude) — best reasoning, project creator likely has key
- OpenAI (GPT) — largest install base, genuine perspective diversity
- OpenAI-compatible (Ollama) — proves local-first from day one

Provider order rationale: Anthropic + OpenAI cover the two most widely-held API keys. Ollama covers local models via the OpenAI-compatible API, requiring minimal adapter work.

**Consensus Engine**:
- State machine: PROPOSE -> CHALLENGE -> REVISE -> COMMIT (single task, no decomposition)
- Challenge phase with forced disagreement prompts (start with 2 framings: "What's wrong?" and "What would you do differently?")
- Configurable rounds (default 2, max 5)
- Convergence detection: if challenges in round N+1 repeat round N, commit early
- Sycophancy detection: flag low-disagreement consensus with user warning
- Parallel fan-out for challenges via asyncio
- Streaming output for proposals and revisions

**Research-informed protocol additions** (from research analyst):
- Support both multi-model debate AND same-model ensemble mode (configurable)
- Prompt caching optimization: stable system prompts across rounds
- Structured output (JSON mode) for reliable parsing where supported

**Memory** (SQLite, Layer 1 + basic Layer 2):
- Threads, turns, contributions (full Layer 1)
- Basic decision extraction after each thread (simplified Layer 2)
- `duh recall "topic"` — keyword search over past decisions
- Turn summaries via cheapest available model
- Thread summaries: regenerate only before PROPOSE, not after every turn (addresses devil's advocate O(n^2) concern)

**CLI** (Rich):
- Real-time streaming display showing model proposals, challenges, revisions
- Cost display per thread (tokens + USD)
- `duh ask "question"` — run consensus
- `duh recall "topic"` — search past decisions
- `duh threads` — list past threads
- `duh show <id>` — display thread with debate history
- `duh models` — list configured providers and models
- `duh cost` — cumulative cost report

**Configuration**: Minimal TOML config for provider API keys, model selection, round count. Environment variables for API keys. No elaborate config hierarchy in v0.1 — grow the config with the product.

**Distribution**: Docker + `uv`/`pip` install

**Testing** (non-negotiable — see Testing Mandate below):
- Every public function and method has unit tests
- Mock providers for deterministic consensus testing
- Sycophancy test suite with known-flaw proposals
- Integration tests for full consensus loop and memory persistence
- Coverage gate: 95%+ on `consensus/`, `providers/`, `memory/`, `config/`; 85%+ overall

#### What a User Can Do

```
$ duh ask "Should I use microservices or a monolith for a new SaaS with 3 engineers?"

PROPOSE (Claude Opus 4.6)
[streams proposal...]

CHALLENGE (parallel)
  GPT-5.2   [What's wrong with this?]  streaming...
  Llama 70B [What would you differently?]  streaming...

REVISE (Claude Opus 4.6)
[streams revision incorporating challenges...]

COMMIT
  Decision saved. 2 models agreed on monolith-first, 1 dissented (GPT argued for modular monolith).

Round 1/2 | 3 models | $0.08 | 34s

# Two weeks later:
$ duh recall "architecture"
  Thread #7: Monolith vs microservices for 3-person SaaS team
  Decision: Monolith-first, revisit at 10 engineers
  Dissent: GPT-5.2 argued for modular monolith from start

$ duh ask "We're hiring two more engineers. Should we start splitting the monolith?"
  [System automatically surfaces Thread #7 as prior context]
```

#### Acceptance Criteria

- [ ] `duh ask "question"` runs full consensus loop and returns result
- [ ] User sees real-time streaming of each model's contribution
- [ ] CHALLENGE phase produces genuine disagreement (validated against sycophancy test suite)
- [ ] Dissent preserved in committed decisions
- [ ] `duh recall "topic"` returns relevant past decisions
- [ ] Works with any 2 of 3 configured providers (graceful degradation)
- [ ] Cost displayed after each thread
- [ ] Same-model ensemble mode works when configured
- [ ] Low-disagreement warning displayed when models converge too quickly

#### Tasks

Tests are written alongside each module, not after. Every task below includes its own unit tests as part of the deliverable. A task is not complete until its tests pass.

1. **Project scaffolding** ~~DONE~~: `pyproject.toml`, `src/duh/` layout, pytest + pytest-asyncio + pytest-cov + ruff + mypy setup, CI pipeline with coverage gates, Docker skeleton
2. **Core error hierarchy + base types** ~~DONE~~: Exception hierarchy (DuhError, ProviderError tree, ConsensusError tree, ConfigError, StorageError). Tests: hierarchy, attributes, formatting
3. **Provider adapter interface + data classes** ~~DONE~~: `ModelProvider` protocol, `ModelInfo`, `ModelResponse`, `StreamChunk`, `TokenUsage`, `PromptMessage` data classes. Tests: instantiation, immutability, protocol conformance
4. **Configuration** ~~DONE~~: TOML loading, env var overrides, Pydantic validation, defaults, file discovery (XDG + project-local + env var). Tests: valid config, missing keys, env var precedence, invalid values
5. **Mock provider + test fixtures** ~~DONE~~: `MockProvider` with deterministic responses, canned response library, shared conftest fixtures. Tests: protocol conformance, send, stream, health, fixtures
6. **Anthropic adapter** ~~DONE~~: Send, stream, health check, model listing, error mapping, cache token extraction. Tests: request building, response parsing, error mapping, streaming (mocked SDK)
7. **OpenAI adapter** ~~DONE~~: Send, stream, health check (covers GPT + Ollama via base_url), error mapping. Tests: same coverage as Anthropic, plus base_url override
8. **Retry with backoff** ~~DONE~~: RetryConfig, is_retryable, retry_with_backoff. Exponential backoff with jitter, retry_after respect. Tests: config, retryability, delay computation, full retry behavior
9. **Provider manager** ~~DONE~~: Registration, model discovery, cost accumulator, routing by model_ref, hard-limit enforcement. Tests: multi-provider registration, cost calculation, model resolution, unknown model errors
10. **SQLAlchemy models** ~~DONE~~: Thread, Turn, Contribution, TurnSummary, ThreadSummary, Decision. Tests: model creation, relationships, constraints, indexes, round-trip persistence (in-memory SQLite)
11. **Memory repository** ~~DONE~~: CRUD operations, keyword search, thread listing, eager loading, upsert summaries. Tests: save/load cycles, search relevance, empty results, pagination
12. **Consensus state machine** ~~DONE~~: States enum, transitions, ConsensusContext dataclass, guard conditions, round archival. Tests: every valid transition, every invalid transition rejected, context mutation
13. **PROPOSE handler + tests** ~~DONE~~: Model selection (by output cost), prompt building (grounding + system + user), handle_propose. Tests: prompt construction, model selection strategies, handler execution, e2e flow
14. **CHALLENGE handler + tests** ~~DONE~~: Parallel fan-out (asyncio.gather), forced disagreement prompts, sycophancy detection (14 markers). Tests: parallel execution, provider failure graceful degradation, sycophancy flagging with known-mild challenges
15. **REVISE handler + tests** ~~DONE~~: Synthesis prompt with all challenges, proposer-revises-own-work default. Tests: prompt includes all challenges, handler execution, model defaulting, validation
16. **COMMIT handler + tests** ~~DONE~~: Decision extraction (decision=revision), confidence scoring from challenge quality, dissent preservation. No model call — pure extraction. Tests: confidence computation, dissent extraction, handler execution, e2e, DB round-trip
17. **Convergence detection + tests** ~~DONE~~: Jaccard word-overlap similarity, cross-round comparison, threshold 0.7. Tests: identical challenges trigger early stop, different challenges continue, threshold behavior
18. **Context builder + tests** ~~DONE~~: Thread summary + recent turns + past decisions assembled for model context. Tests: context fits within token budget, past decisions included when relevant, empty history handled
19. **Summary generator + tests** ~~DONE~~: Turn and thread summaries via cheapest model (by input cost), temp 0.3. Tests: summary produced, model selection (cheapest), regeneration-not-append behavior
20. **Consensus engine integration tests** ~~DONE~~: Full loop with mock providers — PROPOSE through COMMIT. 14 scenarios: single/multi-round, convergence, failure, cost, ensemble, sycophancy, cross-round context
21. **Sycophancy test suite** ~~DONE~~: 98 tests, 3 known-flaw fixtures (eval() security, MD5 passwords, rsync deploy). Exhaustive marker coverage, boundary tests, false-positive resistance, confidence impact scoring
22. **CLI app + tests** ~~DONE~~: 6 Click commands (ask, recall, threads, show, models, cost). Async wrappers, config loading, DB setup, prefix matching on show. 30 tests via CliRunner
23. **CLI display** ~~DONE~~: ConsensusDisplay with Rich panels (green/yellow/blue), spinners, sycophancy warnings, round stats. Integrated into _run_consensus + ask. 32 tests with captured Console
24. **Docker** ~~DONE~~: Multi-stage Dockerfile, docker-compose.yml, .dockerignore, docker/config.toml. OCI labels, non-root user, /data volume
25. **Documentation** ~~DONE~~: MkDocs Material site (19 pages), new README, GitHub Pages deployment. Installation, quickstart, config, concepts, CLI reference, guides, Python API, troubleshooting

#### Dependencies Between Tasks

```
1 (scaffolding)
  -> 2 (errors) + 3 (adapter interface) + 4 (config)
  -> 5 (mock provider) -> 6, 7 (Anthropic, OpenAI adapters)
  -> 8 (retry) + 9 (provider manager)
  -> 10 (SQLAlchemy models) -> 11 (memory repository)
9 (manager) + 11 (repo) -> 12 (state machine) -> 13-16 (handlers) + 17 (convergence)
13-17 (handlers + convergence) -> 18 (context builder) -> 19 (summaries)
12-19 -> 20 (integration tests) + 21 (sycophancy tests)
12-19 -> 22 (CLI app) + 23 (CLI display)
All -> 24 (Docker) -> 25 (docs)
```

---

### v0.2.0 — "It Thinks Deeper"

**AI-time**: 4-6 days
**Theme**: Complex multi-step reasoning and outcome tracking.

#### What Ships

- **Tool-augmented consensus**: Models can invoke tools during PROPOSE and CHALLENGE phases to ground answers in real-time data. Tool types: web search (verify claims, get current data), code execution (test assumptions, run calculations), file reading (analyze documents). Tool calls happen within the consensus loop -- a proposer can search before answering, a challenger can run code to disprove a claim. Tool results are injected into context for subsequent phases. Requires: tool registry, sandboxed execution, tool result formatting, token budget management for tool outputs.
- **Decision taxonomy**: Auto-classify every committed decision along three dimensions -- intent (question, decision, analysis, comparison), category (technical, strategic, creative, factual), and genus (domain-specific tags extracted from content). Classification happens during COMMIT via a lightweight model call. Stored as structured metadata on Decision records. Enables filtering, grouping, and the 3D Decision Space visualization in v0.4.
- **DECOMPOSE phase**: Strong model breaks complex queries into subtasks with dependencies
- **Sequential + parallel subtask consensus**: Each subtask runs its own debate loop, subtask results flow as context to dependents
- **Synthesis phase**: Final rollup of all subtask decisions
- **Outcome tracking**: `duh feedback <thread-id> --result success|failure --notes "..."` records whether decisions worked
- **Outcome injection**: Future threads surface relevant past outcomes ("Last time we chose X, it failed because Y")
- **Google Gemini adapter**: Third cloud provider for genuine model diversity
- **Hybrid decision protocol**: Voting mode for reasoning tasks, consensus mode for judgment tasks (per research analyst R1)
- **Structured output**: JSON mode for DECOMPOSE and decision extraction
- **Improved challenge prompts**: Iterated based on v0.1 sycophancy testing results, add "risk" and "devils_advocate" framings (total: 4)

#### Acceptance Criteria

- [x] Models can invoke web search during PROPOSE/CHALLENGE to ground claims in current data
- [x] Code execution tool available in sandboxed environment for verifying calculations/assumptions
- [x] Tool results visible in thread history (who searched what, what code ran, what results came back)
- [x] Every committed decision is auto-classified with intent, category, and genus tags
- [x] `duh threads --category technical` and `duh recall --intent decision` filter by taxonomy
- [x] Complex queries decompose into 2-7 subtasks automatically
- [x] Subtask results flow as context to dependent subtasks
- [x] `duh feedback` records and `duh recall` surfaces outcome data
- [x] Gemini participates alongside Claude, GPT, and local models
- [x] Voting mode available via `--mode vote` flag
- [x] Structured output produces reliable task lists from DECOMPOSE

#### Tasks

1. **Tool registry and execution framework** ~~DONE~~: Tool definition protocol, sandboxed code runner, web search adapter, file read tool
2. **Tool integration into consensus handlers** ~~DONE~~: Tool calls during PROPOSE/CHALLENGE/REVISE, result injection, token budget for tool outputs
3. **Decision taxonomy model and classifier** ~~DONE~~: Intent/category/genus schema, lightweight LLM classification at COMMIT, DB migration
4. **Taxonomy-aware filtering in CLI** ~~DONE~~: `--intent`, `--category`, `--genus` flags on `threads` and `recall`
5. **Task decomposition engine** ~~DONE~~: DECOMPOSE state handler
6. **Subtask dependency resolver and execution scheduler** ~~DONE~~: TopologicalSorter-based scheduler with parallel execution
7. **Synthesis phase** ~~DONE~~: Roll up subtask commitments into final answer
8. **Outcome model + repository methods** ~~DONE~~: Outcome tracking with feedback recording
9. **Outcome injection into context builder** ~~DONE~~: Past outcomes surfaced in future threads
10. **Google Gemini provider adapter** ~~DONE~~: (Shipped post-v0.1, pre-v0.2 development)
11. **Voting decision protocol** ~~DONE~~: Parallel fan-out + majority/weighted aggregation
12. **Task type classifier** ~~DONE~~: Reasoning vs. judgment protocol selection
13. **Structured output support** ~~DONE~~: JSON mode for DECOMPOSE and decision extraction
14. **Challenge prompt iteration** ~~DONE~~: 4 framing types (flaw/alternative/risk/devils_advocate), round-robin assignment (shipped post-v0.1)
15. **Unit tests** ~~DONE~~: Full coverage for all new modules (tool registry, tool execution, taxonomy classifier, decomposer, scheduler, synthesis, outcome repo, voting protocol, classifier, Gemini adapter)
16. **Integration tests** ~~DONE~~: Tool-augmented consensus loop, taxonomy classification, decomposition-to-synthesis, outcome feedback round-trip, voting vs consensus
17. **Documentation updates** ~~DONE~~: MkDocs site updated with all v0.2 features

> **v0.2.0 shipped 2026-02-16.** 1093 tests, 39 source files, 4 providers (Anthropic, OpenAI, Google Gemini, Ollama). All features delivered. Some items (Gemini adapter, challenge prompt iteration) shipped during late v0.1 development; all others completed in the v0.2 cycle.

---

### v0.3.0 — "It's Accessible"

**AI-time**: 4-6 days
**Theme**: API layer opens duh to integrations and programmatic use.

**Bootstrapping milestone**: At v0.3.0 (MCP server), duh can be used as a tool by the AI agents building it. See [Self-Building Milestone](#self-building-milestone).

#### What Ships

- **REST API**: FastAPI with OpenAPI spec — all CLI functionality as HTTP endpoints
- **WebSocket support**: Real-time streaming of consensus for web clients
- **API authentication**: Local API keys, self-managed
- **Python client library**: `pip install duh-client` for programmatic access
- **MCP server**: duh exposed as a tool for AI agents (following AAIF standards)
- **Mistral adapter**: Fourth cloud provider
- **Batch mode**: `duh batch questions.txt` for multiple queries
- **Export**: `duh export <thread-id> --format json|markdown`

#### Acceptance Criteria

- [ ] Full REST API with OpenAPI spec and WebSocket streaming
- [ ] MCP server exposes consensus as a callable tool
- [ ] Python client library published to PyPI
- [ ] API authentication and rate limiting functional
- [ ] Batch mode processes multiple queries

#### Tasks

1. FastAPI application with middleware (auth, CORS, rate limiting)
2. REST endpoints mirroring CLI commands
3. WebSocket endpoint for streaming consensus
4. API key management (create, revoke, list)
5. Python client library (`duh-client` package)
6. MCP server implementation (tools: ask, recall, threads)
7. Mistral provider adapter
8. Batch processing engine
9. Export formatters (JSON, Markdown)
10. Unit tests for every endpoint, middleware function, client method, MCP tool, batch processor, export formatter
11. Integration tests: API end-to-end, WebSocket streaming, MCP tool invocation, client library against live API, batch processing
12. Documentation: API reference, client quickstart, MCP guide

---

### v0.4.0 — "It Has a Face"

**AI-time**: 6-10 days (largest post-v0.1 release — frontend is a distinct skill domain, may require more iteration)
**Theme**: Web interface makes consensus visible and shareable.

#### What Ships

- **Web UI**: Real-time consensus visualization (the flagship demo experience)
- **Thread browser**: Search, filter, browse past threads and decisions
- **Decision explorer**: Drill into any decision's reasoning, dissent, outcome history
- **3D Decision Space**: Interactive 3D visualization plotting all decisions across three axes -- time (when), category (what kind), and genus (what domain). Renders as a navigable point cloud where each node is a decision. Click to drill in. Zoom to see clusters. Rotate to discover patterns. Reveals how your thinking evolves over time, which domains you revisit most, and where your blind spots are. Built with Three.js or similar WebGL library. Filter by intent, category, genus, confidence, cost. Color-code by outcome (if tracked). Animated timeline mode shows decisions appearing chronologically.
- **Share links**: Read-only links to specific threads/decisions
- **User preferences**: Default models, cost thresholds, consensus depth
- **Mobile-responsive design**
- **Docker Compose with web UI + API as default deployment**
- **Hosted demo**: `try.duh.dev` — free, rate-limited, pre-configured

#### Acceptance Criteria

- [ ] Web UI shows real-time consensus with streaming from each model
- [ ] Thread history browsable and searchable
- [ ] Decisions show full provenance (who proposed, who challenged, how resolved, dissent)
- [ ] 3D Decision Space renders all decisions with time, category, and genus axes
- [ ] Decision Space is interactive: click nodes, filter by taxonomy, animate timeline
- [ ] Share links work without authentication (read-only)
- [ ] `docker compose up` serves web UI + API in under 2 minutes
- [ ] `try.duh.dev` live and rate-limited

#### Tasks

1. Frontend framework selection and scaffolding
2. Real-time consensus display component (WebSocket-driven)
3. Thread browser with search and filtering
4. Decision detail view with debate provenance
5. 3D Decision Space renderer (Three.js/WebGL point cloud, axis mapping, camera controls)
6. Decision Space interaction layer (click-to-detail, taxonomy filtering, timeline animation, confidence/outcome coloring)
7. Decision Space API endpoint (aggregated decision data with taxonomy, optimized for rendering)
8. Share link generation and read-only viewer
9. User preferences UI and persistence
10. Responsive layout for mobile (Decision Space degrades to 2D scatter on small screens)
11. Docker Compose configuration for web + API + optional Postgres
12. Hosted demo deployment (try.duh.dev)
13. Unit tests for all frontend components, WebSocket handlers, share link logic, Decision Space data transforms
14. E2E tests: full flow from question input to consensus display to share link, Decision Space renders with real data
15. Documentation: self-hosting guide

---

### v0.5.0 — "It Scales"

**AI-time**: 4-6 days
**Theme**: Production hardening, multi-user, enterprise readiness.

#### What Ships

- **Multi-user support**: User accounts, per-user threads and decisions
- **Role-based access**: Admin, contributor, viewer
- **PostgreSQL recommended**: For production deployments (SQLite still supported)
- **Connection pooling, query optimization, caching**
- **Rate limiting per user and per provider**
- **Health checks, Prometheus metrics endpoint**
- **Backup/restore utilities**
- **Cohere adapter**: Fifth cloud provider
- **A2A protocol support** (agent-to-agent)

#### Acceptance Criteria

- [ ] Multi-user authentication works (local accounts)
- [ ] PostgreSQL deployment documented and tested
- [ ] Performance: consensus overhead < 500ms beyond model latency
- [ ] Metrics and monitoring operational
- [ ] Backup/restore tested and documented

#### Tasks

1. User model, authentication (session-based or JWT)
2. Role-based access control middleware
3. PostgreSQL deployment guide and testing
4. Connection pooling and query optimization
5. Per-user and per-provider rate limiting
6. Prometheus metrics exporter
7. Health check endpoints
8. Backup/restore CLI commands
9. Cohere provider adapter
10. A2A protocol integration
11. Unit tests for auth, RBAC, rate limiting, backup/restore, metrics, Cohere adapter, A2A protocol
12. Integration tests: multi-user isolation, PostgreSQL round-trip, rate limit enforcement, backup/restore cycle
13. Load testing
14. Documentation: production deployment guide, monitoring guide

---

### v1.0.0 — "duh."

**AI-time**: 5-8 days
**Theme**: Stable, documented, production-ready. The complete single-instance product.

#### What Ships

- **Stable APIs**: REST, WebSocket, MCP, A2A — semantic versioning commitment
- **Comprehensive documentation**: User guide, API reference, self-hosting guide, provider adapter guide
- **Plugin system for provider adapters**: External adapter packages (e.g., `duh-provider-cohere`)
- **Semantic search**: Vector embeddings over memory (sqlite-vss for SQLite, pgvector for PostgreSQL)
- **Performance benchmarks published**
- **Security audit completed**
- **Migration tooling**: Upgrade path from any 0.x to 1.0
- **Long-term stability guarantees**

#### Acceptance Criteria

- [ ] All APIs stable with semantic versioning
- [ ] Documentation covers all user paths (CLI, API, web, MCP, self-hosting, provider development)
- [ ] Vector search operational for semantic recall
- [ ] Security audit passed
- [ ] Performance benchmarks published
- [ ] Upgrade path from 0.x tested

---

### Post-1.0: The 2.0 Cycle

These features were deliberately deferred from 1.0 per the devil's advocate's challenge that the original roadmap tried to build "three products at once." Each is a major product investment.

| Feature | Description | AI-Time |
|---------|-------------|---------|
| **Federated Knowledge Sharing** | Navigator protocol, peer-to-peer decision sharing, privacy controls, trust signals | 10-15 days |
| **Browsable Knowledge Base** | Web interface over accumulated decisions, extends 3D Decision Space with full-text search and quality indicators | 6-10 days |
| **Fact-Checking Mode** | Structured claim decomposition, multi-model verification, citation tracking | 5-8 days |
| **Research Mode** | Extended multi-model investigation, iterative deepening, exportable reports | 5-8 days |
| **Navigator Auto-Discovery** | Automatic discovery of navigator nodes on the network | 3-5 days |

Note: Post-1.0 development benefits from duh's MCP integration — the build agent uses duh itself to debate design decisions, with accumulated knowledge from building v0.1-1.0.

---

## Testing Mandate

**This is non-negotiable. No code ships without tests. No function exists without a test that exercises it.**

Since no human will likely touch this code, the test suite IS the trust layer. Tests are the only mechanism for verifying correctness, preventing regressions, and enabling fearless refactoring. An autonomous agent can write code that looks right but subtly isn't — tests catch that.

### Rules

1. **Test-alongside, not test-after**: Every task deliverable includes its tests. A module is not complete until its tests pass. Never write implementation across multiple modules and then "add tests at the end."

2. **Every public function and method gets a unit test**: No exceptions. If a function exists in the public API of a module, it has at least one test exercising the happy path and at least one test exercising an error/edge case.

3. **Coverage gates enforced in CI**:
   - `consensus/` — 95% minimum (this is the core product logic)
   - `providers/` — 95% minimum (adapter correctness is critical)
   - `memory/` — 95% minimum (data integrity is non-negotiable)
   - `config/` — 90% minimum
   - `core/` — 90% minimum
   - `cli/` — 80% minimum (display code is harder to unit test)
   - Overall — 90% minimum
   - **Coverage can only go up between releases, never down**

4. **Test categories**:
   - **Unit tests** (`tests/unit/`): Fast, no I/O, no network. Mock everything external. One test file per source module. These run in seconds.
   - **Integration tests** (`tests/integration/`): Use in-memory SQLite, mock providers with canned responses. Test cross-module behavior. Full consensus loop end-to-end.
   - **Sycophancy tests** (`tests/sycophancy/`): Specialized test suite with known-flaw proposals. Verifies challenge prompts produce genuine disagreement. These are the "does the product actually work?" tests.
   - **Live tests** (`tests/live/`): Against real provider APIs. NOT in CI (expensive, non-deterministic). Run manually during development. Marked with `@pytest.mark.live`.

5. **Test naming convention**: `test_{module}_{function}_{scenario}`. Example: `test_consensus_engine_challenge_handler_all_providers_fail_raises`.

6. **No mock data in production code**: Test mocks and fixtures live in `tests/fixtures/`. Production code never contains fake/simulated data.

7. **Deterministic tests**: No flaky tests. No `time.sleep()`. No reliance on network. No shared state between tests. Each test creates and tears down its own state.

### Test Infrastructure (Built in v0.1.0, Task 1-3)

```python
# tests/fixtures/providers.py — MockProvider with deterministic responses
# tests/fixtures/responses.py — Canned model responses for each scenario
# tests/fixtures/database.py — In-memory SQLite session factory
# tests/conftest.py — Shared fixtures available to all tests

# CI pipeline:
# 1. ruff check (linting)
# 2. mypy (type checking)
# 3. pytest tests/unit/ (fast, always)
# 4. pytest tests/integration/ (slower, always)
# 5. pytest --cov=duh --cov-fail-under=90 (coverage gate)
# 6. pytest tests/sycophancy/ (consensus quality, always)
```

### Why This Aggressive

An autonomous AI building a system that orchestrates other AIs has a trust problem at every layer. The test suite is the proof that:
- Provider adapters correctly translate between duh's protocol and each provider's API
- The state machine transitions are correct and no invalid state is reachable
- Memory persistence doesn't lose or corrupt data
- Cost tracking is accurate (users are spending real money)
- The consensus protocol actually produces forced disagreement, not sycophantic agreement
- Error handling gracefully degrades rather than crashing

If any of these fail silently, the product is worse than useless — it's confidently wrong.

---

## Self-Building Milestone

**At what point can duh build itself?**

This is the bootstrapping question. duh is a multi-model consensus tool. The agents building it are single-model agents (Claude Code). At some point, the tool they're building becomes more capable than the process building it.

### Progressive Self-Use

| Milestone | When | How duh Helps Build duh |
|-----------|------|------------------------|
| **Architectural debate** | v0.1.0 (CLI works) | Use `duh ask` to debate architectural decisions for v0.2+. "Should decomposition be a consensus operation itself?" Run it through Claude + GPT + Llama and get a structured answer with dissent. Better than one agent deciding alone. |
| **Code review consensus** | v0.1.0 | Use `duh ask` to review proposed implementations. Paste a code diff and ask "What's wrong with this approach?" across multiple models. Catches blind spots a single-model review misses. |
| **Design decisions with memory** | v0.2.0 (knowledge accumulation) | duh remembers past architectural decisions. When debating v0.3 design choices, it surfaces "we decided X in v0.1 because Y" automatically. The tool's institutional memory benefits its own development. |
| **MCP integration** | v0.3.0 (MCP server) | duh becomes a tool that Claude Code can call directly via MCP. Instead of the agent making a solo decision, it invokes `duh.ask("Should I use FastAPI or Starlette for the API layer?")` and gets multi-model consensus as input to its own work. **This is the key inflection point.** |
| **Self-testing validation** | v0.3.0+ | Use duh to debate whether a proposed test suite is comprehensive. "Here are the tests for the CHALLENGE handler. What's missing?" Multiple models find gaps one model won't. |
| **Full self-building loop** | v0.3.0 (MCP) | The build agent uses duh (via MCP) for every non-trivial decision. duh's memory accumulates the project's architectural decisions. duh's consensus catches design flaws. The tool is now actively improving the quality of its own development. |

### The Honest Assessment

- **v0.1.0**: duh is useful for occasional architectural debates during development, but the agent still makes most decisions solo. It's a consultation tool, not an integrated part of the build process.
- **v0.3.0 (MCP)**: This is the real inflection point. When duh is callable as an MCP tool, the build agent can invoke multi-model consensus for any decision without context-switching. The friction drops to near-zero. At this point, duh is a first-class participant in its own development.
- **Post-v0.3.0**: Every subsequent version benefits from duh's accumulated knowledge about its own codebase, its own design patterns, and its own past mistakes. The tool gets smarter about itself with every session.

### What This Means for the Roadmap

The v0.1 -> v0.3 stretch is the "bootstrap gap" where duh can't yet help build itself meaningfully. After v0.3, development quality should measurably improve because:
1. Architectural decisions get multi-model review
2. Past decisions are recalled automatically
3. The build agent has a structured way to get second opinions
4. Design blind spots are caught by model diversity

**Recommendation**: Prioritize the MCP server in v0.3 not just for external users, but because it unlocks duh's ability to improve its own development. The sooner the tool can help build itself, the better every subsequent version becomes.

---

## Technical Architecture Summary

Full details in the systems architect's analysis. Key decisions:

### Project Structure

```
duh/
  src/duh/
    cli/          # Click CLI, Rich display panels
    consensus/    # State machine, handlers, challenge prompts
    providers/    # ModelProvider protocol, adapters (anthropic, openai, google, ollama)
    memory/       # SQLAlchemy models, repository, context builder, summarizer
    config/       # Pydantic schema, TOML loader
    core/         # Errors, events, cost tracking, logging
  tests/
    unit/         # State machine, providers, cost, config
    integration/  # Full consensus loop, memory persistence
    fixtures/     # Mock providers, canned responses, in-memory DB
  alembic/        # Database migrations
```

Package management: `uv`. Single installable package. No premature splitting.

### Provider Interface

```python
@runtime_checkable
class ModelProvider(Protocol):
    @property
    def provider_id(self) -> str: ...
    async def list_models(self) -> list[ModelInfo]: ...
    async def send(self, messages, model_id, **kwargs) -> ModelResponse: ...
    async def stream(self, messages, model_id, **kwargs) -> AsyncIterator[StreamChunk]: ...
    async def health_check(self) -> bool: ...
```

Using `typing.Protocol` (structural typing) over ABC. Stateless adapters. Cost tracked at the `ProviderManager` level.

### Consensus State Machine

```
INPUT -> DECOMPOSE -> PROPOSE -> CHALLENGE -> REVISE -> COMMIT -> NEXT
                        ^                                          |
                        +------ (more tasks) ----------------------+
                                                                   |
                                                          (no more tasks)
                                                                   v
                                                               COMPLETE
```

Key protocol features (research-informed):
- **Forced disagreement**: Each challenger gets an adversarial framing
- **Sycophancy detection**: Flags low-disagreement consensus
- **Convergence detection**: Commits early when challenges become repetitive
- **Hybrid protocol**: Voting for reasoning tasks, consensus for judgment tasks
- **Same-model ensemble**: Optional mode using multiple samples from one model

### Memory Schema (SQLAlchemy)

**Layer 1 (Operational)**: Thread, Turn, Contribution, TurnSummary, ThreadSummary
**Layer 2 (Institutional)**: Decision, Pattern, Outcome
**Layer 3 (Retrieval)**: Embedding (v1.0, sqlite-vss or pgvector)

Default: SQLite (zero-config). Scale path: PostgreSQL via connection string.

### Configuration

TOML format. Merge order: defaults < user config (`~/.config/duh/config.toml`) < project config (`./duh.toml`) < env vars < CLI flags.

### Error Handling

Provider failures handled gracefully — if one model fails, consensus continues with remaining models. Exponential backoff with jitter for rate limits. Cost guard with configurable warn and hard limits.

### Async Pattern

asyncio for I/O-bound parallelism. Key parallelism point: CHALLENGE phase fans out to all models simultaneously. PROPOSE and REVISE are sequential (streaming for UI). Database is the non-bottleneck.

---

## Risk Register

### Critical Risks

| Risk | Likelihood | Impact | Mitigation | Owner |
|------|-----------|--------|------------|-------|
| **Consensus doesn't beat single model** | Medium | Critical | Phase 0 validation. Benchmark before building. Fallback: self-debate and best-of-N modes. | Phase 0 |
| **Sycophantic agreement produces false confidence** | High | High | Forced disagreement prompts, sycophancy detection, low-disagreement warnings, sycophancy test suite | v0.1 |
| **Local models degrade consensus quality** | Medium | Medium | Don't claim equal quality. Weight local model influence. Position as optional "third voice." Validate with benchmarks. | v0.1 |
| **Adoption funnel too narrow** (requires multiple API keys + CLI) | Medium | High | Hosted demo (try.duh.dev) at v0.4. Consider bundled free tier with cheap models. | v0.4 |

### Research-Identified Risks

| Risk | Source | Mitigation |
|------|--------|------------|
| Self-MoA outperforms multi-model mixing | Princeton 2025 | Support both modes. Position as "right tool for the question." |
| More debate rounds can reduce quality | ACL 2025 | Convergence detection, default 2 rounds not 3. |
| Naive debate amplifies shared misconceptions | ICLR 2025 | Heterogeneous model panels, devil's advocate framing, convergence warnings. |
| Google ships "Gemini Consensus" | Market analysis | Multi-PROVIDER is the moat. No single vendor can include all models. Ship fast. |
| Latency 10x worse than direct model calls | Architecture analysis | Streaming to show progress. Position latency as "it thinks harder." Target compelling examples, not speed. |

### Competitive Risks

| Threat | Likelihood | Defense |
|--------|-----------|---------|
| OpenAI adds multi-model deliberation | Medium | Can't include Claude/Gemini. Multi-provider is structural advantage. |
| Google ships consensus feature | Medium-High | Same: single-provider limitation. |
| Together AI productizes MoA | Medium-High | Knowledge accumulation is the moat. MoA is stateless. |
| LangGraph adds consensus node | Low-Medium | duh is a product, not a framework. Different category. |

---

## Go-to-Market Strategy

### Positioning

**What we say**: "duh is a thinking tool, not a workflow tool. It makes multiple AI models debate your question, preserves the disagreements, and remembers what worked."

**What we don't say**: "AI agent framework" (commoditized), "LLM orchestration" (sounds like infrastructure), "better than [competitor]" (different category).

**Tagline**: "Why wouldn't you use all of them? ...duh."

### Launch Sequence

**Phase 0 launch** (before v0.1): Publish benchmark results as a blog post. "We made Claude and GPT debate 50 questions. Here's what happened." This generates interest before the product exists.

**v0.1 launch**:
- Hacker News Show HN
- r/LocalLLaMA (local models as first-class citizens)
- Twitter/X thread with live demo
- GitHub README as the pitch: show the CLI output, the debate, the dissent

**v0.4 launch** (web UI): Major launch moment. Hosted demo at try.duh.dev. Video demo. Shareable debate links for viral distribution.

### Early Adopter Profiles

1. **AI Power Users** (v0.1): People with 2+ API keys who already compare models manually. They're doing consensus by hand. ~1,000-5,000 people globally.
2. **Local Model Enthusiasts** (v0.1): r/LocalLLaMA community. Want their local models to be more useful alongside cloud models.
3. **Knowledge Workers** (v0.4): Researchers, analysts, consultants. Need the web UI — not CLI users. This is the broader market.
4. **Teams** (v0.5): Organizations wanting shared decision-making infrastructure.

### Community Building

Discord from day one:
- `#show-your-debates` — users share interesting consensus outputs
- `#challenge-prompts` — community improves challenge framings
- `#provider-adapters` — contributions for new providers
- `#local-models` — dedicated space for the local model community

Content strategy:
- Weekly "Debate of the Week" — run an interesting question, publish full debate
- Monthly "Consensus Report" — trending topic through multiple model combinations
- "How Claude, GPT, and Gemini disagree about X" — organic search driver

---

## Success Metrics

| Version | Primary Metric | Target |
|---------|---------------|--------|
| Phase 0 | Blind evaluation win rate (consensus vs single model) | >60% on judgment tasks |
| 0.1.0 | GitHub stars (30 days) | 500+ |
| 0.1.0 | Weekly active users | 50+ |
| 0.2.0 | Threads using past decision context | 30%+ |
| 0.3.0 | API integrations | 10+ |
| 0.4.0 | Web UI daily active users | 500+ |
| 0.5.0 | Team/org deployments | 20+ |
| 1.0.0 | Total active instances | 2,000+ |

---

## Open Questions

Surfaced by the team and not yet resolved:

1. **Proposer rotation**: Should the proposer rotate through models each task, or be user-configured? Current plan: configurable via `proposer_strategy`, default `round_robin`.

2. **Decomposition consensus**: When DECOMPOSE is added (v0.2), should decomposition itself be a consensus operation (multiple models decompose, then vote on task list)?

3. **Summary model routing**: If Ollama is configured with a local model, always prefer local for summaries (zero cost)? How explicit should this routing be?

4. **Licensing**: MIT or Apache 2.0? Need to decide before v0.1 launch.

5. **Output licensing**: When duh synthesizes outputs from multiple providers, what's the ownership? Critical for enterprise (v0.5+) and knowledge base (post-1.0). Needs legal review.

6. **Vector search for SQLite**: sqlite-vss vs ChromaDB sidecar vs FAISS in-process. Decision needed before v1.0 semantic search work.

7. **Hosted demo economics**: Who pays for the API credits on try.duh.dev? Rate limiting alone may not be sufficient. Consider using only cheap models (Haiku, Flash) for the demo.

8. **Testing framework**: pytest assumed. Confirm and set up quality gates (coverage thresholds, linting, type checking).

---

## Appendix: Competitive Position

### Validated Differentiators (confirmed novel by research analyst)

| Feature | Novelty Level | Phase |
|---------|--------------|-------|
| Dissent preservation as structured data | **Novel** | v0.1 |
| Persistent knowledge accumulation from consensus | **Novel** | v0.1 |
| Tool-augmented consensus (models search/execute during debate) | **Novel** | v0.2 |
| Decision taxonomy (auto-classified intent/category/genus) | **Novel** | v0.2 |
| 3D Decision Space visualization (time x category x genus) | **Strongly novel** | v0.4 |
| Federated knowledge sharing (navigator protocol) | **Strongly novel** | Post-1.0 |
| Browsable debate-as-content knowledge base | **Novel** | Post-1.0 |
| Outcome tracking on AI consensus decisions | **Novel** | v0.2 |
| Knowledge democratization (local accesses network) | **Novel** | Post-1.0 |
| Multi-provider structured debate (as product) | **Novel as product** | v0.1 |
| Same-model + multi-model hybrid consensus | **Novel** | v0.1 |

### Key Academic Papers Informing the Design

| Paper | Key Finding | Impact on duh |
|-------|------------|---------------|
| MoA (ICLR 2025) | Multi-model collaboration beats single models | Validates core thesis |
| Self-MoA (Princeton 2025) | Same-model ensemble beats multi-model mixing | Added same-model mode |
| MAD Evaluation (ICLR 2025) | Naive debate doesn't consistently win | Forced disagreement, convergence detection |
| Voting vs Consensus (ACL 2025) | Voting 13.2% better on reasoning tasks | Added hybrid protocol |
| CONSENSAGENT (ACL 2025) | Sycophancy measurably degrades debate | Added sycophancy detection |
| A-HMAD (2025) | Heterogeneous roles improve debate 4-6% | Challenge framings with distinct roles |
| VERIFAID (2025) | Growing knowledge bases have utility at scale | Validates knowledge accumulation approach |

### Competitive Gap Analysis

```
                    duh   LangGraph  CrewAI  AutoGen  MoA   Perplexity
Multi-model debate   Y      N         N       N       Y*      N
Tool-augmented       0.2    ~         ~       ~       N       Y
Persistent memory    Y      ~         ~       ~       N       ~
Decision taxonomy    0.2    N         N       N       N       N
3D Decision Space    0.4    N         N       N       N       N
Dissent preserved    Y      N         N       N       N       N
Federated sharing    2.0    N         N       N       N       N
Outcome tracking     Y      N         N       N       N       N
Domain-agnostic      Y      ~         N       ~       Y       Y
Local models equal   Y      ~         ~       ~       Y       N
Cost transparency    Y      ~         ~       ~       N       N

Y = yes, N = no, ~ = partial, * = research only, not product
```

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-15 | 1.0 | Initial roadmap synthesized from agent team |
| 2026-02-15 | 1.1 | Recalibrated timelines to AI-time. Added Testing Mandate. Added Self-Building Milestone. Elevated testing from afterthought to first-class development constraint. |
| 2026-02-16 | 1.2 | Added tool-augmented consensus (v0.2) and decision taxonomy (v0.2). Added 3D Decision Space visualization (v0.4). Updated competitive gap analysis. |
| 2026-02-16 | 1.3 | v0.2.0 complete. All features shipped. Updated acceptance criteria and task status. Added Status column to overview table. |

---

*This roadmap is a living document. It will be updated as Phase 0 results come in, user feedback shapes priorities, and the competitive landscape evolves. The core principle remains: **prove the thesis first, then build the product, then scale the platform.***
