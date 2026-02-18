# duh ask

Run a consensus query across multiple LLMs.

## Synopsis

```
duh ask [OPTIONS] QUESTION
```

## Description

The `ask` command is duh's primary command. By default it sends your question through the full consensus protocol:

1. **PROPOSE** -- Strongest model answers the question
2. **CHALLENGE** -- Other models challenge the proposal with forced disagreement
3. **REVISE** -- Proposer revises based on genuine challenges
4. **COMMIT** -- Decision extracted with confidence score and dissent

The process repeats for up to `max_rounds` (default: 3) or until convergence is detected.

You can also select alternative protocols:

- **Voting** (`--protocol voting`) -- Fan out to all models in parallel, then aggregate the best answer
- **Auto** (`--protocol auto`) -- Classify the question first (reasoning vs. judgment), then route to consensus or voting
- **Decomposition** (`--decompose`) -- Break the question into subtasks, solve each with consensus, and synthesize

Output is displayed in real-time with Rich-styled panels:

- Green panel: Proposal
- Yellow panel: Challenges (with sycophancy flags)
- Blue panel: Revision
- Cyan panel: Votes, decomposition plan, subtask results, tool usage
- White panel: Final decision with confidence and cost

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `QUESTION` | Yes | The question to ask. Wrap in quotes if it contains spaces. |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--rounds` | int | From config (3) | Maximum consensus rounds. Overrides `general.max_rounds` in config. |
| `--decompose` | flag | `false` | Decompose the question into subtasks before consensus. |
| `--protocol` | choice | From config (`consensus`) | Protocol: `consensus` (default), `voting`, or `auto` (classify first). |
| `--tools` / `--no-tools` | flag | From config | Enable or disable tool use (web search, code exec, file read). Overrides `tools.enabled` in config. |
| `--proposer` | string | Auto-selected | Override the proposer model (e.g. `anthropic:claude-opus-4-6`). |
| `--challengers` | string | Auto-selected | Override challengers (comma-separated model refs, e.g. `openai:gpt-5.2,google:gemini-3-pro-preview`). |
| `--panel` | string | All models | Restrict consensus to these models only (comma-separated model refs). Overrides `consensus.panel` in config. |

## Examples

Basic question:

```bash
duh ask "What are the security implications of using JWTs for session management?"
```

Single-round consensus (faster, cheaper):

```bash
duh ask --rounds 1 "Quick: should I use Redis or Memcached for caching?"
```

Deeper debate (more rounds):

```bash
duh ask --rounds 5 "Design a microservices architecture for an e-commerce platform"
```

Use the voting protocol:

```bash
duh ask --protocol voting "Which Python web framework should I use?"
```

Auto-detect whether to use consensus or voting:

```bash
duh ask --protocol auto "Is Rust worth learning in 2026?"
```

Decompose a complex question into subtasks:

```bash
duh ask --decompose "Design a complete CI/CD pipeline for a monorepo"
```

Enable tool use (web search, code execution, file read):

```bash
duh ask --tools "What is the current LTS version of Node.js?"
```

Disable tool use even if enabled in config:

```bash
duh ask --no-tools "Explain the CAP theorem"
```

Use a specific proposer:

```bash
duh ask --proposer openai:gpt-5.2 "Compare REST and GraphQL"
```

Override challengers:

```bash
duh ask --challengers google:gemini-3-pro-preview,anthropic:claude-sonnet-4-6 "Best database for IoT?"
```

Restrict to a panel of models:

```bash
duh ask --panel anthropic:claude-opus-4-6,openai:gpt-5.2 "Design a caching strategy"
```

With a specific config:

```bash
duh --config ./local-config.toml ask "question"
```

## Output sections

### Round header

```
────────────── Round 1/3 ──────────────
```

### Proposal (green panel)

Shows the proposer's model reference and initial answer.

### Challenges (yellow panel)

Shows each challenger's model reference and challenge text. Sycophantic challenges are flagged with a yellow "sycophantic" label.

### Revision (blue panel)

Shows the reviser's model reference and improved answer.

### Commit line

```
✓ COMMIT  Confidence: 100%  (no dissent)
```

### Round footer

```
Round 1/3 | 6 models | $0.0342 | 4.2s
```

### Final decision (white panel)

The full, untruncated consensus decision with confidence and cost.

### Dissent panel (yellow, if present)

Preserved genuine challenges that represent minority viewpoints.

### Voting output

When using `--protocol voting`, the output shows:

- **Votes panel** (cyan) -- Each model's independent answer
- **Decision panel** (white) -- The aggregated best answer
- **Stats line** -- Strategy (majority/weighted), confidence, vote count, cost

### Decomposition output

When using `--decompose`, the output shows:

- **DECOMPOSE panel** (magenta) -- The subtask DAG with labels, descriptions, and dependencies
- **Subtask results** -- Each subtask's consensus decision and confidence
- **SYNTHESIS panel** (white) -- The merged final answer from all subtask results
- **Stats line** -- Aggregate confidence and cost

### Tool usage output

When tools are used during consensus (enabled via `--tools` or config), a **TOOLS panel** (cyan) appears after the decision showing each tool call with the phase, tool name, and arguments.

## Related commands

- [`recall`](recall.md) -- Search for this decision later
- [`show`](show.md) -- Inspect the full thread details
- [`feedback`](feedback.md) -- Record whether the decision worked out
- [`cost`](cost.md) -- Check cumulative spending
