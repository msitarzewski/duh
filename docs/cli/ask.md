# duh ask

Run a consensus query across multiple LLMs.

## Synopsis

```
duh ask [OPTIONS] QUESTION
```

## Description

The `ask` command is duh's primary command. It sends your question through the full consensus protocol:

1. **PROPOSE** -- Strongest model answers the question
2. **CHALLENGE** -- Other models challenge the proposal with forced disagreement
3. **REVISE** -- Proposer revises based on genuine challenges
4. **COMMIT** -- Decision extracted with confidence score and dissent

The process repeats for up to `max_rounds` (default: 3) or until convergence is detected.

Output is displayed in real-time with Rich-styled panels:

- Green panel: Proposal
- Yellow panel: Challenges (with sycophancy flags)
- Blue panel: Revision
- White panel: Final decision with confidence and cost

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `QUESTION` | Yes | The question to ask. Wrap in quotes if it contains spaces. |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--rounds` | int | From config (3) | Maximum consensus rounds. Overrides `general.max_rounds` in config. |

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

## Related commands

- [`recall`](recall.md) -- Search for this decision later
- [`show`](show.md) -- Inspect the full thread details
- [`cost`](cost.md) -- Check cumulative spending
