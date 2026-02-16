# How Consensus Works

## The problem

Every LLM has blind spots. A single model gives you one perspective with no way to know what it missed, oversimplified, or got wrong. Self-critique helps, but models are biased toward agreeing with themselves.

## The solution: forced disagreement

duh uses a 4-phase protocol that forces genuine disagreement between models. The key insight: a challenged and revised answer is consistently stronger than a direct answer from any single model.

## The 4 phases

### 1. PROPOSE

The strongest available model (selected by output cost as a capability proxy) generates an initial answer.

The proposer gets a system prompt that encourages thorough, specific answers with concrete examples and numbers. No hedging.

```
IDLE  -->  PROPOSE
```

### 2. CHALLENGE

Multiple challenger models (default: 2) receive the proposal with explicit instructions to **disagree**:

- They must find at least one substantive disagreement (not a nitpick)
- They must not start with praise ("This is a good answer...")
- They must identify something wrong, oversimplified, or missing
- They must argue for an alternative when the proposal recommends approach X

Challengers are selected to maximize diversity -- models from different providers are preferred over same-model self-critique. Challenges run in parallel for speed.

```
PROPOSE  -->  CHALLENGE
```

!!! note "Sycophancy detection"
    duh scans the opening ~200 characters of each challenge for praise markers like "great answer", "I largely agree", or "no significant flaws". Sycophantic challenges are flagged and excluded from confidence calculations.

### 3. REVISE

The original proposer receives all challenges and produces an improved answer that:

1. Addresses each valid challenge directly
2. Maintains correct points with stronger justification
3. Incorporates new perspectives where they improve the answer
4. Pushes back on wrong challenges with explanations

The revision prompt instructs the model not to mention the debate process -- just give the best possible answer.

```
CHALLENGE  -->  REVISE
```

### 4. COMMIT

A pure extraction step (no model call):

- **Decision** = the revision text
- **Confidence** = computed from challenge quality (0.5 to 1.0). More genuine (non-sycophantic) challenges = higher confidence, because the revision was more rigorously tested.
- **Dissent** = preserved text from genuine challenges, representing minority viewpoints that may be valuable even after revision

```
REVISE  -->  COMMIT
```

## Convergence detection

After COMMIT, duh compares the current round's challenges against the previous round's challenges using **Jaccard word-overlap similarity**:

1. For each current challenge, find the maximum similarity to any previous challenge
2. Average these maximum similarities
3. If the average >= 0.7 (configurable threshold), challenges have **converged**

Convergence means challengers are raising the same issues across rounds. Further iteration is unlikely to improve the answer, so duh stops early.

Round 1 never converges (nothing to compare against).

## Multi-round flow

If challenges haven't converged and rounds remain, the state machine cycles back:

```
COMMIT  -->  PROPOSE  (new round, with previous context)
```

The next round's proposer receives the previous decision and its challenges, so it can build on what was already debated.

When rounds are exhausted or convergence is detected:

```
COMMIT  -->  COMPLETE
```

## Voting protocol

The voting protocol is an alternative to the full consensus debate. Instead of iterative propose-challenge-revise rounds, all models answer independently in parallel and a meta-judge aggregates the results.

### When to use voting

- **Judgment questions** -- subjective evaluations, comparisons, opinions
- **Speed-sensitive queries** -- parallel fan-out is faster than sequential rounds
- **High model count** -- more models means more diverse perspectives to aggregate

Use `--protocol voting` or set `protocol = "voting"` in config. Use `--protocol auto` to let duh classify the question and route automatically.

### How it works

1. **Fan-out**: The question is sent to all configured models in parallel
2. **Collection**: Each model's answer is collected as a `VoteResult`
3. **Meta-judge selection**: The strongest model (highest output cost) is selected as judge
4. **Aggregation**: The judge picks or synthesizes the best answer

### Aggregation strategies

| Strategy | Behavior |
|----------|----------|
| `majority` (default) | Meta-judge reads all answers and picks the best one, improving it if possible |
| `weighted` | Meta-judge synthesizes all answers, weighting by model capability (output cost as proxy) |

Configure the strategy in `[voting]`:

```toml
[voting]
aggregation = "weighted"
```

### Auto-classification

With `--protocol auto`, duh uses the cheapest model to classify the question:

- **Reasoning** (logic, math, code, step-by-step) -- routes to consensus
- **Judgment** (opinions, evaluations, comparisons) -- routes to voting

## Query decomposition

For complex questions that span multiple domains, duh can decompose the question into a directed acyclic graph (DAG) of subtasks.

### When to use decomposition

- **Multi-part questions** -- "Design a complete CI/CD pipeline" has research, tooling, and architecture components
- **Questions with dependencies** -- Some parts must be answered before others
- **Broad-scope queries** -- Better to solve focused subproblems and merge results

Use `--decompose` or set `decompose = true` in config.

### How it works

1. **DECOMPOSE phase**: The cheapest model breaks the question into 2-7 subtasks with dependency relationships, returned as JSON
2. **DAG validation**: Labels are checked for uniqueness, dependencies are resolved, and the graph is verified acyclic (Kahn's algorithm)
3. **Scheduling**: Subtasks are scheduled using `TopologicalSorter` -- independent subtasks run in parallel, dependent subtasks wait for their prerequisites
4. **Per-subtask consensus**: Each subtask runs the full consensus protocol independently
5. **Synthesis**: A meta-model merges all subtask results into a single coherent answer

### Synthesis strategies

| Strategy | Behavior |
|----------|----------|
| `merge` | Combine all subtask answers into one comprehensive response |
| `prioritize` | Weight subtask answers by their confidence scores |

### Single-subtask optimization

If decomposition produces only one subtask (the question is already focused enough), duh skips synthesis and runs normal consensus directly. This avoids unnecessary overhead.

## Tool-augmented consensus

Models can use tools during the PROPOSE and CHALLENGE phases to access external information and capabilities.

### Available tools

| Tool | Description | Config key |
|------|-------------|------------|
| **Web search** | Search the web using DuckDuckGo (or custom backend) | `tools.web_search` |
| **Code execution** | Run Python code in a sandboxed environment | `tools.code_execution` |
| **File read** | Read local files for context | Always available when tools enabled |

### How tools work

1. The model receives tool definitions alongside the consensus prompt
2. If the model requests a tool call, duh executes it and returns the result
3. The model incorporates tool results into its response
4. Tool calls are logged and displayed in the TOOLS panel after the decision

Enable tools globally in config:

```toml
[tools]
enabled = true

[tools.web_search]
backend = "duckduckgo"
max_results = 5

[tools.code_execution]
enabled = true
timeout = 30
```

Or per-query via CLI:

```bash
duh ask --tools "What is the current price of Bitcoin?"
```

!!! note "Tool call loop"
    The tool-augmented send loop runs up to `tools.max_rounds` iterations (default: 5) per phase, allowing models to make multiple sequential tool calls if needed.

## State machine

```
IDLE --> DECOMPOSE --> PROPOSE --> CHALLENGE --> REVISE --> COMMIT --> COMPLETE
             |                                                |
             |                                                +--> PROPOSE (next round)
             |                                                |
             +--> (subtask scheduling + synthesis)            +--> FAILED (on error)
```

The DECOMPOSE state is optional -- it is entered only when `--decompose` is used. The voting protocol bypasses the state machine entirely (parallel fan-out + aggregation).

Any non-terminal state can transition to FAILED on errors. COMPLETE and FAILED are terminal states.

Guard conditions enforce valid transitions:

- Can't PROPOSE without a non-empty question
- Can't CHALLENGE without a proposal
- Can't REVISE without challenges
- Can't COMMIT without a revision
- Can't start a new round if already converged or max rounds reached
- Can't COMPLETE if not converged and rounds remain

## Next steps

- [Providers and Models](providers-and-models.md) -- How models are selected
- [Cost Management](cost-management.md) -- Token tracking and limits
