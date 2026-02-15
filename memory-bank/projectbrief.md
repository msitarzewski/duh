# Project Brief: duh

## Vision

A general-purpose decision and knowledge infrastructure that orchestrates multiple AI models — cloud and local — through structured consensus, accumulates knowledge over time, and connects instances into a federated network where collective intelligence becomes accessible to everyone.

Not a developer tool. A thinking tool. Domain-agnostic. The answer to "why wouldn't you use all of them?" is... duh.

## Core Tenets

1. **Knowledge accumulates** — for itself, its users, humanity. Nothing learned is lost. Every interaction makes the system smarter.
2. **Models are the workforce, memory is the asset** — Models come and go. Next year's models will be better. Knowledge persists and compounds.
3. **Local-first, connected by choice** — Your instance, your data. Share when you want to, with whom you want to. Works offline with local models.
4. **Quality through diversity** — Multiple perspectives produce better decisions than any single model. Cloud, local, specialized, general — all contribute.
5. **Show the work** — The user sees what's happening: parallel execution, consensus, dissent, cost. No black boxes.
6. **No gatekeepers** — Works with any model, anywhere. No vendor lock-in. A local Llama has the same voice as Claude Opus in the consensus.
7. **Domain-agnostic** — Code, business, science, agriculture, personal decisions. The consensus loop doesn't care about the domain.
8. **Knowledge democratizes** — Local models access the network's collective intelligence. Expensive thinking is done once and shared. A zero-cost instance benefits from the whole network.

## What This Is

A system where a user provides a concept, question, or decision — and the system:

1. Decomposes it into manageable tasks
2. Assigns tasks to the best available models (cloud or local)
3. Runs structured consensus: propose, challenge, revise, commit
4. Accumulates decisions and outcomes in persistent memory
5. Optionally shares knowledge to a federated network via navigator nodes
6. Returns a result that represents the collective reasoning of multiple AI models, informed by the network's accumulated knowledge

### Emergent Capabilities

The consensus protocol and knowledge accumulation naturally enable:

**Fact-Checking**: Multi-model verification of claims. Decompose a claim into sub-claims, models research and cross-check independently, challenge phase attempts disproof, network provides prior verifications. Result: structured verdict with confidence, evidence, dissent, and sources.

**Research**: Multi-model investigation where different models approach a topic from different angles, cross-reference each other, and produce findings that no single model would generate alone. Network knowledge means research builds on what's already been investigated.

**Living Knowledge Base**: The accumulated, consensus-validated knowledge — browsable by humans through a web interface. Every entry shows its reasoning, its debate, its dissent, and its outcome track record. Not a single-author encyclopedia. A peer-reviewed knowledge graph with full provenance.

Unlike Wikipedia (one article, edit wars, debate buried in Talk pages), every knowledge entry preserves the structured debate as navigable content. A human reader sees the resolved position and can drill into which models agreed, which dissented, what concerns were raised, and how the knowledge performed when applied by other instances across the network.

## What This Is Not

- Not a chatbot wrapper or prompt router
- Not a single-provider tool (must work with all providers + local models)
- Not code-only or developer-only
- Not centralized — no single authority owns the knowledge network
- Not a black box — every decision shows its reasoning and dissent

## Architecture (Three Tiers)

### Tier 1: Model Providers (Thinking Layer)
The workforce. Stateless. Replaceable. Called by instances.

- **Cloud**: Anthropic (Claude), OpenAI (GPT/o-series), Google (Gemini), Mistral, Cohere, etc.
- **Local**: Ollama, LM Studio, llama.cpp, vLLM, text-generation-inference, etc.
- **Common adapter interface**: Send prompt, get response, stream tokens. The consensus engine doesn't know or care where the response came from.
- Most local providers already expose OpenAI-compatible APIs, simplifying the adapter layer.

### Tier 2: Instances (Knowledge Layer)
Where knowledge lives. Your box, your data. The core product.

- **Consensus Engine**: State machine that orchestrates multi-model decision-making
- **Memory Layer**: Persistent storage of threads, decisions, outcomes, patterns
- **Task Decomposer**: Breaks concepts into actionable subtasks
- **Provider Manager**: Routes tasks to appropriate models based on capability, cost, privacy requirements
- **Interface Layer**: CLI (first), Web, API, MCP, A2A (future)

### Tier 3: Knowledge Navigators (Index Layer)
The map. Lightweight index nodes that make knowledge findable across the network.

- Store metadata, summaries, and pointers — not full knowledge
- Respond to queries: "Has anyone solved X?" with matching decisions, debates, and outcomes
- Track outcome-based quality signals (not reputation — empirical results)
- Anyone can run a navigator. General-purpose and specialized navigators can coexist.
- No single point of failure. Multiple navigators, federated.

## Consensus Protocol

```
DECOMPOSE → PROPOSE → CHALLENGE → REVISE → COMMIT → NEXT
```

- **DECOMPOSE**: Break concept into tasks (strong reasoner model)
- **PROPOSE**: One model proposes approach for current task
- **CHALLENGE**: Other models critique in parallel (forced disagreement, not sycophantic agreement)
  - "What's wrong with this proposal?"
  - "What would you do differently?"
  - "What's the biggest risk?"
  - Devil's advocate role-assigned each round
- **REVISE**: Proposer or synthesizer integrates feedback
- **COMMIT**: Summary committed to memory, dissent preserved, move to next task
- **NEXT**: Next task, possibly different proposer

### Network-Informed Consensus
During DECOMPOSE or PROPOSE, the instance can query knowledge navigators:
- "Has anyone solved this before?"
- Navigator returns matching decisions, consensus debates, and outcome data
- Models reason with network knowledge as input, not from scratch
- After resolution, instance publishes its decision back to opted-in navigators

## Memory Architecture

### Storage
- **Default**: SQLite (local, zero-config, works everywhere)
- **Scale path**: PostgreSQL or MySQL via connection string swap (SQLAlchemy abstraction)
- **Managed hosting**: DigitalOcean, AWS RDS, etc. via SSH tunnel or direct connection

### Memory Schema (Three Layers)

**Layer 1 — Operational (thread tracking)**
- Threads: Top-level conversations/projects
- Turns: Each round of the consensus loop
- Contributions: Individual model responses within a turn
- Turn summaries: Generated by fast/local model after each turn
- Thread summaries: Rolling, regenerated after each turn

**Layer 2 — Institutional (accumulated knowledge)**
- Decisions: Structured records with question, proposals, challenges, resolution, dissent, outcomes
- Patterns: Inferred user/domain preferences over time
- Outcomes: Feedback on whether decisions worked — closes the learning loop

**Layer 3 — Retrieval (future)**
- Vector embeddings over memory for semantic search
- "What did we decide about X last month?" without knowing which thread

### Context Management
- Pass thread summary + recent raw turns + current task to models each round
- Raw history always in database for deep retrieval
- Summaries generated by fast/cheap model (Haiku-class or local)
- Thread summary regenerated after each turn to stay coherent

## Technical Decisions

- **Language**: Python (every provider has first-class SDK; asyncio for parallel calls)
- **Distribution**: Docker container (install anywhere, one command)
- **Database abstraction**: SQLAlchemy (swap SQLite for Postgres via config)
- **CLI UI**: Rich / Textual (live parallel execution display)
- **Provider adapters**: Plugin architecture, one adapter per provider
- **Local model protocol**: OpenAI-compatible API (covers most local servers)

## Cost Philosophy

Tokens are the currency. Token cost correlates directly with output quality. The system is **cost-aware, not cost-constrained**:
- Show the user what they're spending in real time
- Let users set their own thresholds
- Never silently degrade quality to save money
- Use fast/cheap/local models for infrastructure tasks (summaries, classification, routing)
- Use expensive models for the actual thinking

## Build Sequence (Suggested)

### Phase 1: Core Loop (CLI POC)
- Provider adapters (2-3 cloud + Ollama)
- Consensus state machine (PROPOSE → CHALLENGE → REVISE → COMMIT)
- SQLite memory layer (threads, turns, contributions)
- Turn/thread summaries via fast model
- Rich CLI with parallel execution display
- Single-user, local only

### Phase 2: Knowledge Depth
- Full memory schema (decisions, patterns, outcomes)
- Outcome tracking and feedback loops
- More provider adapters
- Task decomposition for complex multi-step concepts
- Cost tracking and display

### Phase 3: Interfaces
- Web interface
- API layer
- MCP server implementation
- A2A protocol support

### Phase 4: Network
- Knowledge navigator protocol
- Peer-to-peer decision sharing (opt-in)
- Navigator nodes (index and search)
- Outcome-based quality signals
- Network-informed consensus

### Phase 5: Knowledge Base
- Browsable web interface over accumulated network knowledge
- Fact-checking as a first-class operation
- Research mode for multi-model investigation
- Human-readable knowledge entries with full provenance and debate history
- Search and discovery across the collective knowledge graph

## Origin Context

Born from a conversation about OpenClaw agents, autonomous tool use, and the thesis that AGI — or whatever we end up calling it — will emerge from highly connected systems of models with shared memory, tool access, and physical endpoints. Not a single monolithic model doing superhuman things, but a network of specialized participants building collective intelligence.

The setup.md in memory-bank contains the original conversation that sparked this project.
