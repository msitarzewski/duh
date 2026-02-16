# Quickstart

Get your first consensus answer in minutes.

## 1. Ask a question

```bash
duh ask "What are the trade-offs between PostgreSQL and MySQL for a new SaaS product?"
```

duh will:

1. Select the strongest model as **proposer** (based on output cost as capability proxy)
2. Send your question and display the proposal in a green panel
3. Send the proposal to **challenger** models with forced disagreement instructions
4. Display challenges in a yellow panel (flagging any sycophantic ones)
5. Have the proposer **revise** based on genuine challenges (blue panel)
6. **Commit** the decision with a confidence score

You'll see output like:

```
────────────── Round 1/3 ──────────────
╭─ PROPOSE (anthropic:claude-opus-4-6) ────╮
│ PostgreSQL is the stronger choice for     │
│ most SaaS products...                     │
╰───────────────────────────────────────────╯
╭─ CHALLENGE ───────────────────────────────╮
│ openai:gpt-5.2                            │
│ I disagree with the blanket PostgreSQL    │
│ recommendation. For read-heavy SaaS...    │
╰───────────────────────────────────────────╯
╭─ REVISE (anthropic:claude-opus-4-6) ─────╮
│ The choice depends on your workload       │
│ pattern...                                │
╰───────────────────────────────────────────╯
✓ COMMIT  Confidence: 100%

──────────────────────────────────────────
╭─ Decision ────────────────────────────────╮
│ The choice depends on your workload...    │
╰───────────────────────────────────────────╯
Confidence: 100% | Cost: $0.0342
```

## 2. Recall past decisions

Search your decision history by keyword:

```bash
duh recall "database"
```

```
  Thread a1b2c3d4  What are the trade-offs between PostgreSQL and MySQL...
    Decision: The choice depends on your workload pattern...
    Confidence: 100%
```

## 3. Inspect a thread

View the full debate history for any thread using its ID prefix:

```bash
duh show a1b2c3d4
```

This shows every round's proposal, challenges, revision, and decision.

## 4. Check costs

See how much you've spent across all sessions:

```bash
duh cost
```

```
Total cost: $0.0342
Total tokens: 2,450 input + 1,890 output

By model:
  anthropic:claude-opus-4-6: $0.0280 (2 calls)
  openai:gpt-5.2: $0.0062 (1 calls)
```

## 5. Use the voting protocol

For quick judgment calls, use voting instead of full consensus:

```bash
duh ask --protocol voting "Which Python web framework should I use for a REST API?"
```

All configured models answer independently in parallel. A meta-judge (the strongest model) picks or synthesizes the best answer:

```
╭─ VOTES ─────────────────────────────────────────╮
│ anthropic:claude-opus-4-6                        │
│ FastAPI is the best choice for a modern...       │
│                                                  │
│ openai:gpt-5.2                                   │
│ Django REST Framework provides the most...       │
╰──────────────────────────────────────────────────╯

──────────────────────────────────────────
╭─ Decision ───────────────────────────────────────╮
│ FastAPI is the recommended choice for new...     │
╰──────────────────────────────────────────────────╯
Strategy: majority | Confidence: 80% | Votes: 2 | Cost: $0.0180
```

## 6. Decompose a complex question

Break a multi-part question into subtasks:

```bash
duh ask --decompose "Design a complete CI/CD pipeline for a Python monorepo"
```

duh decomposes the question, solves each subtask with consensus, and synthesizes:

```
╭─ DECOMPOSE (4 subtasks) ────────────────────────╮
│ 1. [research_tools] Research CI/CD tools...      │
│    Dependencies: none                            │
│ 2. [testing_strategy] Define testing stages...   │
│    Dependencies: none                            │
│ 3. [pipeline_design] Design the pipeline...      │
│    Dependencies: research_tools, testing_strategy│
│ 4. [deployment] Define deployment strategy...    │
│    Dependencies: pipeline_design                 │
╰──────────────────────────────────────────────────╯
✓ [research_tools]  Confidence: 95%
✓ [testing_strategy]  Confidence: 90%
✓ [pipeline_design]  Confidence: 85%
✓ [deployment]  Confidence: 90%

╭─ SYNTHESIS (merge) ─────────────────────────────╮
│ Here is a complete CI/CD pipeline design...      │
╰──────────────────────────────────────────────────╯
```

## 7. Record feedback on a decision

After acting on a decision, record whether it worked:

```bash
duh feedback a1b2c3d4 --result success --notes "Deployed to production, no issues"
```

```
Outcome recorded: success for thread a1b2c3d4
```

You can view outcomes later with `duh show`:

```bash
duh show a1b2c3d4
```

## What just happened?

When you ran `duh ask`, the consensus engine:

1. **Loaded configuration** from `~/.config/duh/config.toml` (or defaults)
2. **Registered providers** (Anthropic, OpenAI) and discovered available models
3. **PROPOSE phase** -- Selected the strongest model (by output cost) and asked your question
4. **CHALLENGE phase** -- Sent the proposal to 2 challenger models in parallel with forced disagreement prompts. Sycophantic responses were flagged.
5. **REVISE phase** -- The proposer revised its answer, addressing each valid challenge
6. **COMMIT phase** -- Extracted the final decision, computed confidence from challenge quality, and preserved dissent
7. **Convergence check** -- Compared challenges to the previous round (if any) using Jaccard word-overlap similarity. If similar enough (>= 0.7 threshold), stopped early.
8. **Persisted** the entire thread (question, contributions, decisions) to SQLite

## Next steps

- [Configuration](configuration.md) -- Adjust rounds, cost limits, and providers
- [How Consensus Works](../concepts/how-consensus-works.md) -- Deep dive into the protocol
- [CLI Reference](../cli/index.md) -- All commands and options
