# Tasks — February 2026

## v0.1 Development

### 2026-02-15: Project Scaffolding (Task 1)
- Created `src/duh/` package layout with cli/, consensus/, providers/, memory/, config/, core/
- Configured pyproject.toml with all v0.1 deps + tooling (pytest, ruff, mypy, coverage)
- 4 smoke tests, CI pipeline, Dockerfile, Alembic skeleton
- See: [150215_project-scaffolding.md](./150215_project-scaffolding.md)

### 2026-02-15: Core Error Hierarchy (Task 2)
- Created `src/duh/core/errors.py` with 11 exception classes
- DuhError base, ProviderError (5 subclasses), ConsensusError (2 subclasses), ConfigError, StorageError
- 17 tests covering hierarchy, attributes, formatting
- See: [150215_core-errors.md](./150215_core-errors.md)

### 2026-02-15: Provider Adapter Interface (Task 3)
- Created `src/duh/providers/base.py` with 6 data classes + `ModelProvider` protocol
- ModelCapability, ModelInfo, TokenUsage, ModelResponse, StreamChunk, PromptMessage
- 27 tests covering instantiation, immutability, protocol conformance
- See: [150215_provider-interface.md](./150215_provider-interface.md)

### 2026-02-15: Configuration (Task 4)
- Created TOML config loading with Pydantic validation
- 7 config models, file discovery (XDG + project-local + env var), deep merge, API key resolution
- 31 tests covering defaults, validation, TOML loading, env var precedence, file discovery
- See: [150215_configuration.md](./150215_configuration.md)

### 2026-02-15: Mock Provider + Test Fixtures (Task 5)
- Created MockProvider (protocol-conformant, deterministic, call logging)
- 4 canned response sets, shared conftest fixtures
- 34 tests covering protocol, send, stream, health, fixtures
- See: [150215_mock-provider.md](./150215_mock-provider.md)

### 2026-02-15: Anthropic Adapter (Task 6)
- Created AnthropicProvider with send, stream, health_check, error mapping
- 3 known Claude models, dependency-injectable SDK client, cache token extraction
- 27 tests with mocked SDK client
- See: [150215_anthropic-adapter.md](./150215_anthropic-adapter.md)

### 2026-02-15: OpenAI Adapter (Task 7)
- Created OpenAIProvider with send, stream, health_check, error mapping, base_url support
- 3 known models (GPT-5.2, GPT-5 mini, o3), covers GPT + Ollama via base_url
- Updated Anthropic model pricing/output tokens to match current official rates
- 32 tests with mocked SDK client
- See: [150215_openai-adapter.md](./150215_openai-adapter.md)

### 2026-02-15: Retry with Backoff (Task 8)
- Created `src/duh/core/retry.py` with RetryConfig, is_retryable, retry_with_backoff
- Exponential backoff with jitter, retry_after respect, non-retryable fail-fast
- 29 tests covering config, retryability, delay computation, full retry behavior
- See: [150215_retry-backoff.md](./150215_retry-backoff.md)

### 2026-02-15: Provider Manager (Task 9)
- Created `src/duh/providers/manager.py` — ProviderManager class
- Registration, model discovery, routing by model_ref, cost accumulation with hard-limit enforcement
- 25 tests covering registration, discovery, routing, cost tracking, hard limit, reset
- See: [150215_provider-manager.md](./150215_provider-manager.md)

### 2026-02-15: SQLAlchemy Models (Task 10)
- Created `src/duh/memory/models.py` — Base + 6 ORM models (Thread, Turn, Contribution, TurnSummary, ThreadSummary, Decision)
- Relationships, cascades, unique constraints, FK indexes, UUID PKs, UTC timestamps
- Wired alembic `target_metadata` to Base.metadata
- 36 tests covering creation, relationships, constraints, indexes, round-trip persistence
- See: [150215_sqlalchemy-models.md](./150215_sqlalchemy-models.md)

### 2026-02-15: Memory Repository (Task 11)
- Created `src/duh/memory/repository.py` — MemoryRepository with async CRUD, keyword search, thread listing
- Eager loading via selectinload, upsert summaries, search across questions + decisions
- Promoted `db_session` fixture to shared `tests/conftest.py`
- 30 tests covering CRUD, search, pagination, empty results, save/load cycles
- See: [150215_memory-repository.md](./150215_memory-repository.md)

### 2026-02-15: Consensus State Machine (Task 12)
- Created `src/duh/consensus/machine.py` — ConsensusState enum, ChallengeResult, RoundResult, ConsensusContext, ConsensusStateMachine
- Pure logic (no IO): 7 states, valid transition map, guard conditions, context mutation, round archival
- 71 tests covering enum, dataclasses, valid/invalid transitions, terminal states, guards, context mutation
- See: [150215_consensus-state-machine.md](./150215_consensus-state-machine.md)

### 2026-02-16: PROPOSE Handler (Task 13)
- Created `src/duh/consensus/handlers.py` — build_propose_prompt, select_proposer, handle_propose
- Prompts adapted from validated phase0/prompts.py, model selection by output cost
- 19 tests covering prompt building, model selection, handler execution, e2e flow
- See: [160216_propose-handler.md](./160216_propose-handler.md)

### 2026-02-16: CHALLENGE Handler (Task 14)
- Extended `src/duh/consensus/handlers.py` — parallel fan-out, forced disagreement, sycophancy detection
- Added `sycophantic` field to ChallengeResult, asyncio.gather for parallel execution
- 29 tests covering prompts, model selection, sycophancy detection, graceful degradation, e2e
- See: [160216_challenge-handler.md](./160216_challenge-handler.md)

### 2026-02-16: REVISE Handler (Task 15)
- Extended `src/duh/consensus/handlers.py` — synthesis prompt with all challenges, proposer-revises-own-work default
- 21 tests covering prompt building, handler execution, model defaulting, validation, e2e
- See: [160216_revise-handler.md](./160216_revise-handler.md)

### 2026-02-16: COMMIT Handler (Task 16)
- Extended `src/duh/consensus/handlers.py` — decision extraction, confidence scoring, dissent preservation
- No model call — pure extraction and scoring step
- 21 tests covering confidence computation, dissent extraction, handler execution, e2e, DB round-trip
- See: [160216_commit-handler.md](./160216_commit-handler.md)

### 2026-02-16: Convergence Detection (Task 17)
- Created `src/duh/consensus/convergence.py` — Jaccard word-overlap similarity, cross-round comparison, early stopping
- Pure computation, no model calls, configurable threshold (default 0.7)
- 22 tests covering similarity math, threshold edges, convergence logic, e2e with state machine
- See: [160216_convergence-detection.md](./160216_convergence-detection.md)

### 2026-02-16: Context Builder (Task 18)
- Created `src/duh/memory/context.py` — token estimation, thread summary + decisions assembly with budget
- Pure functions, no DB access — caller provides data
- 16 tests covering token estimation, assembly, budget truncation, DB integration
- See: [160216_context-builder.md](./160216_context-builder.md)

### 2026-02-16: Summary Generator (Task 19)
- Created `src/duh/memory/summary.py` — turn/thread summaries via cheapest model, regeneration upsert
- Extended MockProvider with `input_cost`/`output_cost` params for cost-sensitive tests
- 16 tests covering model selection, prompts, generation, regeneration, e2e persistence
- See: [160216_summary-generator.md](./160216_summary-generator.md)

### 2026-02-16: Integration Tests (Task 20)
- Created `tests/integration/test_consensus_loop.py` — full consensus loop with mock providers
- 14 tests: single/multi-round, convergence, failure, cost, ensemble, sycophancy, cross-round context
- See: [160216_integration-tests.md](./160216_integration-tests.md)

### 2026-02-16: Sycophancy Test Suite (Task 21)
- Created `tests/sycophancy/` suite — 98 tests for sycophancy detection, known-flaw scenarios, confidence impact
- 3 new known-flaw response fixtures (eval() security, MD5 passwords, rsync deploy)
- Exhaustive marker coverage (14 markers x 3 positions), boundary tests, false-positive resistance
- Known-flaw proposals: genuine challenges (confidence 1.0), sycophantic (0.5), mixed (0.75)
- See: [160216_sycophancy-tests.md](./160216_sycophancy-tests.md)

### 2026-02-16: CLI App (Task 22)
- Rewrote `src/duh/cli/app.py` — 6 Click commands: ask, recall, threads, show, models, cost
- Async wrappers with `asyncio.run()`, config loading, DB session setup, error handling
- `ask` runs full consensus loop; `show` supports UUID prefix matching; `cost` aggregates from DB
- 30 tests via Click CliRunner (unit + DB integration with StaticPool)
- See: [160216_cli-app.md](./160216_cli-app.md)

### 2026-02-16: CLI Display (Task 23)
- Created `src/duh/cli/display.py` — ConsensusDisplay with Rich panels, spinners, phase formatters
- Integrated into `_run_consensus` (progress) and `ask` (final output) in app.py
- Green/yellow/blue panels for PROPOSE/CHALLENGE/REVISE, sycophancy warnings, round stats
- 32 tests with captured Console output via StringIO
- See: [160216_cli-display.md](./160216_cli-display.md)

### 2026-02-16: Docker (Task 24)
- Improved Dockerfile (OCI labels, container config, `/data` volume ownership)
- Created docker-compose.yml, .dockerignore, docker/config.toml
- Fixed bug: providers now auto-discovered from env vars (default config was empty)
- See: [160216_docker.md](./160216_docker.md)

---

## v0.2 Development

### 2026-02-16: Alembic Migrations (v0.2 Task 1)
- Created `001_v01_baseline.py` and `002_v02_schema.py` migration scripts
- Outcome, Subtask tables; taxonomy fields (domain, category, tags, complexity) on Decision
- Files: `alembic/versions/001_v01_baseline.py`, `alembic/versions/002_v02_schema.py`

### 2026-02-16: Structured Output (v0.2 Task 2)
- Added `response_format`, `tools`, `tool_calls` parameters to all provider adapters
- Extended MockProvider with structured output support
- Files: `src/duh/providers/base.py`, `src/duh/providers/anthropic.py`, `src/duh/providers/openai.py`, `src/duh/providers/google.py`

### 2026-02-16: JSON Extract (v0.2 Task 3)
- Created `src/duh/consensus/json_extract.py` for reliable JSON extraction from model responses
- Handles markdown code blocks, partial JSON, nested structures

### 2026-02-16: Challenge Framings (v0.2 Task 4)
- Added 4 challenge framing types: flaw, alternative, risk, devils_advocate
- Round-robin assignment in `_CHALLENGE_FRAMINGS`
- Added `ChallengeResult.framing` field
- Files: `src/duh/consensus/handlers.py`

### 2026-02-16: Tool Framework (v0.2 Task 5)
- Created Tool protocol and ToolRegistry
- Files: `src/duh/tools/base.py`, `src/duh/tools/registry.py`

### 2026-02-16: Tool-Augmented Send (v0.2 Task 6)
- Created `tool_augmented_send()` loop: send -> detect tool_calls -> execute -> re-send
- Files: `src/duh/tools/augmented_send.py`

### 2026-02-16: Config Schema (v0.2 Task 7)
- Added `ToolsConfig`, `VotingConfig`, `DecomposeConfig`, `TaxonomyConfig`
- Added `GeneralConfig.protocol` and `GeneralConfig.decompose` fields
- Files: `src/duh/config/schema.py`

### 2026-02-16: Models + Repository (v0.2 Task 8)
- Added `Outcome`, `Subtask`, `Vote` ORM models
- Added taxonomy fields to `Decision` model
- Extended `MemoryRepository` with full CRUD for new models
- Files: `src/duh/memory/models.py`, `src/duh/memory/repository.py`

### 2026-02-16: Taxonomy at COMMIT (v0.2 Task 9)
- `handle_commit(classify=True)` triggers `_classify_decision()` via lightweight model call
- Structured output for domain, category, tags, complexity
- Files: `src/duh/consensus/handlers.py`

### 2026-02-16: Feedback CLI (v0.2 Task 10)
- `duh feedback <thread_id> --result --notes` command
- Records real-world outcomes for knowledge accumulation
- Files: `src/duh/cli/app.py`

### 2026-02-16: Outcome Context (v0.2 Task 11)
- `build_context(outcomes=...)` injects `[OUTCOME: result]` format into context
- Files: `src/duh/memory/context.py`

### 2026-02-16: Display Updates (v0.2 Task 12)
- Added `show_taxonomy()`, `show_outcome()` methods
- Updated `show` command with taxonomy and outcome display
- Files: `src/duh/cli/display.py`, `src/duh/cli/app.py`

### 2026-02-16: DECOMPOSE State + Handler (v0.2 Task 13)
- Added `ConsensusState.DECOMPOSE`, `SubtaskSpec` dataclass
- Created `handle_decompose()` and `validate_subtask_dag()`
- Files: `src/duh/consensus/machine.py`, `src/duh/consensus/decompose.py`

### 2026-02-16: Scheduler (v0.2 Task 14)
- Created `schedule_subtasks()` with `TopologicalSorter` + `asyncio.gather`
- Respects dependency DAG, parallel execution of independent subtasks
- Files: `src/duh/consensus/scheduler.py`

### 2026-02-16: Synthesis (v0.2 Task 15)
- Created `synthesize()` with merge/prioritize strategies
- Files: `src/duh/consensus/synthesis.py`

### 2026-02-16: Decomposition CLI (v0.2 Task 16)
- `duh ask --decompose` flag triggers DECOMPOSE -> schedule -> synthesize flow
- Display: `show_decompose()`, `show_subtask_progress()`, `show_synthesis()`
- Files: `src/duh/cli/app.py`, `src/duh/cli/display.py`

### 2026-02-16: Voting + Classifier (v0.2 Task 17)
- Created `run_voting()` with majority/weighted aggregation
- Created `classify_task_type()` and `TaskType` enum for auto protocol selection
- Files: `src/duh/consensus/voting.py`, `src/duh/consensus/classifier.py`

### 2026-02-16: Voting CLI + Persistence (v0.2 Task 18)
- `duh ask --protocol consensus|voting|auto` flag
- Auto mode calls `classify_task_type()` to select protocol
- Display: `show_votes()`, `show_voting_result()`
- Migration `003_v02_votes.py` for Vote persistence
- Files: `src/duh/cli/app.py`, `src/duh/cli/display.py`, `alembic/versions/003_v02_votes.py`

### 2026-02-16: Tool Implementations (v0.2 Task 19)
- `web_search.py` — DuckDuckGo search via `duckduckgo-search>=7.0`
- `code_exec.py` — asyncio subprocess with timeout and truncation
- `file_read.py` — path traversal rejection, binary rejection, 100KB max
- Files: `src/duh/tools/web_search.py`, `src/duh/tools/code_exec.py`, `src/duh/tools/file_read.py`

### 2026-02-16: Provider Tool Call Parsing (v0.2 Task 20)
- All 3 providers parse `tool_calls` from responses
- Verified `tools` parameter forwarded correctly
- Files: `src/duh/providers/anthropic.py`, `src/duh/providers/openai.py`, `src/duh/providers/google.py`

### 2026-02-16: Tool Integration in Handlers (v0.2 Task 21)
- `handle_propose()` + `handle_challenge()` accept optional `tool_registry`
- Use `tool_augmented_send()` when tools provided
- Files: `src/duh/consensus/handlers.py`

### 2026-02-16: Tool CLI Setup (v0.2 Task 22)
- `duh ask --tools` flag enables tool-augmented reasoning
- `_setup_tools(config)` creates ToolRegistry from config
- `show_tool_use()` display method
- Files: `src/duh/cli/app.py`, `src/duh/cli/display.py`

### 2026-02-16: v0.2 Integration Tests + Docs (Phase 6)
- Integration tests: taxonomy_outcomes, decompose_loop, voting_loop, tool_augmented
- README and MkDocs documentation updated
- Version bumped to 0.2.0
- **Final count: 1093 tests, 39 source files, 4 providers**

---

## Post-v0.2 Polish

### 2026-02-16: Subtask Progress Display
- Threaded `ConsensusDisplay` through the decompose scheduler for real-time subtask progress
- Added `subtask_header()` and `subtask_footer()` to `ConsensusDisplay`
- Added `display` param to `_run_mini_consensus()`, `_execute_subtask()`, `schedule_subtasks()`
- Each subtask now shows PROPOSE/CHALLENGE/REVISE/COMMIT panels with model names and spinners
- Added `cost: float` field to `SubtaskResult` for per-subtask cost tracking
- Files: `src/duh/consensus/scheduler.py`, `src/duh/cli/display.py`, `src/duh/cli/app.py`
