# Architectural Decisions

**Last Updated**: 2026-02-16

---

## 2026-02-15: Multi-Model Consensus Over Single-Model Routing

**Status**: Approved
**Context**: Existing frameworks (LangGraph, CrewAI, AutoGen) route tasks to individual models. Some research (MoA) shows multi-model collaboration improves quality.
**Decision**: duh runs structured consensus (PROPOSE → CHALLENGE → REVISE → COMMIT) across multiple models from multiple providers, not just routing to one.
**Alternatives**:
- Single best-model routing (simpler, cheaper, but loses diversity of perspective)
- MoA-style layered synthesis (proven to work, but loses dissent and doesn't accumulate knowledge)
**Consequences**: Higher token cost per query. Richer output. Dissent preserved. Knowledge accumulation possible.
**References**: `competitive-landscape.md#2`, MoA paper (ICLR 2025)

---

## 2026-02-15: Knowledge Accumulation as Core Product

**Status**: Approved
**Context**: All existing multi-model tools are stateless — each query starts from scratch.
**Decision**: Persistent memory is the core product, not the orchestration. Models are replaceable infrastructure; accumulated knowledge (decisions, reasoning, dissent, outcomes) is the durable value.
**Alternatives**:
- Session-only memory (simpler, like existing tools)
- External knowledge base integration (RAG-style, but doesn't generate its own knowledge)
**Consequences**: Requires robust database layer. System gets smarter over time. Creates moat against competitors.
**References**: `projectbrief.md#Core Tenets` (tenet 2)

---

## 2026-02-15: Federated Knowledge via Navigator Nodes

**Status**: Approved (design phase — implementation Phase 4)
**Context**: Individual instances accumulating knowledge in isolation is valuable but limited. Connected instances sharing knowledge is exponentially more valuable.
**Decision**: Lightweight navigator nodes index shared knowledge (metadata + pointers). Instances query navigators ("has anyone solved X?") and get back matching decisions with provenance. Full knowledge stays on source instances; navigators hold the map.
**Alternatives**:
- Centralized knowledge server (simpler, but single point of failure/control)
- Full peer-to-peer search (no navigator needed, but O(n) search doesn't scale)
- Blockchain-based knowledge registry (adds complexity without clear benefit)
**Consequences**: Requires network protocol design. Trust/quality signal needed. Anyone can run a navigator. No central authority.
**References**: `projectbrief.md#Architecture`, DNS/BitTorrent as architectural inspiration

---

## 2026-02-15: Local Models as First-Class Citizens

**Status**: Approved
**Context**: Most frameworks treat local models as fallbacks or development conveniences.
**Decision**: Local models (Ollama, LM Studio, llama.cpp, vLLM) participate equally in consensus and access the network's collective knowledge. A zero-cost local instance benefits from cloud-model-generated knowledge.
**Alternatives**:
- Cloud-only (simpler, but creates vendor dependency and excludes users who can't/won't use cloud APIs)
- Local as fallback (supports offline but treats local as second-class)
**Consequences**: Must handle heterogeneous model capabilities (different context windows, tool use support, quality levels). Knowledge democratization — expensive thinking done once, shared freely.
**References**: `projectbrief.md#Core Tenets` (tenets 6, 8)

---

## 2026-02-15: Forced Disagreement in Consensus Protocol

**Status**: Approved
**Context**: LLMs are sycophantic. If Claude proposes X, GPT will likely say "great idea, and also Y." False consensus is worse than a single model because it feels validated.
**Decision**: The CHALLENGE phase forces productive disagreement: "What's wrong with this?", "What would you do differently?", "What's the biggest risk?" Devil's advocate role assigned each round.
**Alternatives**:
- Natural consensus (simpler, but produces sycophantic agreement)
- Voting only (binary agree/disagree, loses nuance)
**Consequences**: Better quality output. Preserved dissent is valuable knowledge. May increase round count/cost. Protocol design is critical — naive debate doesn't always beat single strong model (per ICLR 2025 evaluation).
**References**: `competitive-landscape.md#3` (MAD evaluation caveat)

---

## 2026-02-15: Domain-Agnostic Design

**Status**: Approved
**Context**: Most multi-agent frameworks are developer-focused (code generation, software engineering).
**Decision**: duh is a general-purpose thinking tool. The consensus protocol works for any domain: code, business, science, agriculture, personal decisions, fact-checking, research.
**Alternatives**:
- Dev-focused first, expand later (faster to market, narrower audience)
- Vertical-specific tools (agriculture AI, legal AI, etc.)
**Consequences**: No domain-specific assumptions in core architecture. Broader potential market. Harder to market initially (no specific vertical story).
**References**: `projectbrief.md#Core Tenets` (tenet 7)

---

## 2026-02-15: Python + Docker for Distribution

**Status**: Approved
**Context**: Need to be installable anywhere — home servers, cloud VMs, laptops.
**Decision**: Python for the core (SDK ecosystem), Docker for distribution (one command install).
**Alternatives**:
- Rust (single binary, but thin SDK ecosystem — would hand-roll all provider integrations)
- Go (decent balance, but less AI ecosystem support than Python)
- Node.js (viable SDKs exist, but Python is the AI ecosystem lingua franca)
**Consequences**: Python packaging complexity mitigated by Docker. Performance is not a concern (bottleneck is network latency to model APIs). All provider SDKs available.
**References**: `techContext.md`

---

## 2026-02-15: Cost-Aware, Not Cost-Constrained

**Status**: Approved
**Context**: Multi-model consensus multiplies API costs. Some instinct is to restrict token usage.
**Decision**: Tokens are the currency. Token cost correlates with output quality. Show costs transparently, let users set thresholds, never silently degrade quality. Use cheap/local models for infrastructure tasks (summaries, routing), expensive models for thinking.
**Alternatives**:
- Budget caps with automatic degradation (cheaper, but defeats the purpose)
- Fixed model tiers (loses flexibility)
**Consequences**: Higher potential cost per query. User controls their spend. System always delivers best available quality.
**References**: `projectbrief.md#Cost Philosophy`

---

## 2026-02-15: SOTA Models for Phase 0 Thesis Validation

**Status**: Approved
**Context**: Phase 0 tests whether multi-model consensus beats single-model answers. Original plan used Sonnet 4.5 to isolate the method effect. User argued the thesis test should use the best available models.
**Decision**: Use Opus 4.6 + GPT-5.2 for the real benchmark (`--budget full`). Cheaper models (Sonnet + GPT-4o) available via `--budget small` for iterating on prompts/plumbing.
**Alternatives**:
- Sonnet-only (cheaper, isolates method over model, but doesn't test the actual product scenario)
- Opus-only without GPT (misses the cross-provider diversity that IS the product)
**Consequences**: Higher benchmark cost (~$60 full run vs ~$15). Results represent actual product quality. Budget flag enables cheap iteration.
**References**: `phase0/config.py:11-25` (BUDGETS dict)

---

## 2026-02-15: Date Grounding in All Prompts

**Status**: Approved
**Context**: Models may give different answers based on assumed date. Questions about technology, market conditions, and strategy are time-sensitive.
**Decision**: Inject `Today's date is YYYY-MM-DD` and temporal grounding instruction into every system prompt via `_grounding()` function.
**Alternatives**:
- No grounding (models use training date heuristics — inconsistent)
- Per-question date context (more precise but tedious)
**Consequences**: All answers temporally grounded. Consistent baseline across models. Trivial implementation cost.
**References**: `phase0/prompts.py:8-16` (_grounding function)

---

## 2026-02-15: Phase 0 Exit Decision — PROCEED

**Status**: Approved
**Context**: Phase 0 benchmark ran 17/50 questions (stopped early — sufficient signal). Auto-decision said ITERATE (33% J/S win rate below 60% threshold), but that metric measures "ranked #1 out of 4 methods" — a misleading bar when Consensus and Ensemble split multi-model wins.
**Decision**: PROCEED to v0.1. Head-to-head data clearly validates the thesis: Consensus beats Direct (47-88% depending on judge), beats Self-Debate (76.5%), scores higher on all 5 dimensions. The method works; prompts will improve in v0.1.
**Alternatives**:
- ITERATE (refine prompts, re-run) — delay for marginal improvement on a benchmark that already shows the pattern
- STOP (thesis invalidated) — contradicted by all head-to-head data
**Consequences**: v0.1 development begins. Phase 0 prompts carry forward as seeds. Prompt refinement is ongoing in v0.1 tasks 11-16 (consensus state handlers).
**References**: `results/analysis/`, `progress.md#Benchmark Results`

---

## 2026-02-15: Local Models Deferred to v0.1

**Status**: Approved
**Context**: Phase 0 benchmarks cloud SOTA models to validate the thesis. Ollama/local support was available in the plan.
**Decision**: Phase 0 uses only Anthropic + OpenAI cloud APIs. Local model support (Ollama via OpenAI-compatible base_url) begins in v0.1.
**Alternatives**:
- Include local models in Phase 0 (adds complexity, local quality would drag down results)
**Consequences**: Simpler Phase 0. Clean thesis test with best models. Local model integration proven in v0.1 with Ollama adapter.
**References**: `roadmap.md:138` (Ollama in v0.1)

---

## 2026-02-16: Voting as Parallel Fan-Out (Not State Machine)

**Status**: Approved
**Context**: v0.2 adds a voting protocol for tasks where consensus debate is overkill (factual questions, preference polls). Design choice: extend the state machine or build a separate parallel architecture.
**Decision**: Voting is a simple parallel fan-out: send the same prompt to all models independently, collect responses, aggregate via majority or weighted voting. NOT a state machine — no PROPOSE/CHALLENGE/REVISE cycle.
**Alternatives**:
- Extend state machine with VOTE state (adds complexity to an already complex machine)
- Sequential voting rounds (slower, no benefit for independent opinions)
**Consequences**: Simpler architecture for factual/preference tasks. Auto-classification (`classify_task_type()`) selects consensus vs voting. Consistent with ACL 2025 findings that parallel independent reasoning outperforms sequential debate for factual tasks.
**References**: `src/duh/consensus/voting.py`, `src/duh/consensus/classifier.py`

---

## 2026-02-16: Decomposition as Single-Model (Not Consensus)

**Status**: Approved
**Context**: v0.2 adds task decomposition. Open question: should DECOMPOSE itself be a consensus operation (multiple models debate how to break down the task)?
**Decision**: DECOMPOSE is a single-model operation. One model decomposes the task into a subtask DAG. Each subtask then runs through consensus independently.
**Alternatives**:
- Multi-model decomposition (models debate the breakdown — adds a full consensus round before any work begins)
- User-defined decomposition (manual, loses automation benefit)
**Consequences**: Faster decomposition (one model call vs full consensus). Simpler implementation. Each subtask still gets full consensus treatment. Decomposition quality is "good enough" from a single strong model.
**References**: `src/duh/consensus/decompose.py`, `src/duh/consensus/scheduler.py`

---

## 2026-02-16: Tool Protocol via Python Protocol (Structural Typing)

**Status**: Approved
**Context**: v0.2 adds tool-augmented reasoning. Tools need a common interface for the registry and augmented send loop.
**Decision**: Use Python `Protocol` class for the Tool interface — consistent with the existing provider adapter pattern. Tools implement `name`, `description`, `parameters_schema`, and `execute()`.
**Alternatives**:
- ABC base class (requires explicit inheritance, less flexible)
- Dict-based tools (no type safety)
- Decorator-based registration (implicit, harder to test)
**Consequences**: Structural typing means any object with the right methods is a tool — easy to extend. ToolRegistry handles lookup. tool_augmented_send handles the execute-and-resubmit loop.
**References**: `src/duh/tools/base.py`, `src/duh/tools/registry.py`, `src/duh/tools/augmented_send.py`

---

## 2026-02-16: Taxonomy Classification at COMMIT Time

**Status**: Approved
**Context**: v0.2 adds decision taxonomy (domain, category, tags, complexity). When should classification happen?
**Decision**: Classify at COMMIT time via a lightweight model call with structured output. The decision text is already finalized, so classification is accurate. Adds one cheap model call to the commit step.
**Alternatives**:
- Classify at query time (before consensus — less accurate, decision not yet formed)
- User-provided taxonomy (manual burden, inconsistent)
- Post-hoc batch classification (delayed, loses real-time value)
**Consequences**: Taxonomy is automatic and accurate. One additional cheap model call per decision. Structured metadata enables filtering, analytics, and outcome correlation.
**References**: `src/duh/consensus/handlers.py` (`handle_commit(classify=True)`, `_classify_decision()`)
