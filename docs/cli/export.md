# duh export

Export a thread with its full debate history.

## Synopsis

```
duh export [OPTIONS] THREAD_ID
```

## Description

Exports a complete thread including all rounds, contributions, decisions, votes, and metadata. Output can be JSON (for programmatic use), Markdown (for documentation), or PDF (for sharing).

Thread IDs support prefix matching (minimum 8 characters).

By default, the full report is exported with the decision section first, followed by the complete consensus process. Use `--content decision` to export just the decision.

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `THREAD_ID` | Yes | Full UUID or prefix (minimum 8 chars) |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--format` | choice | `json` | Export format: `json`, `markdown`, or `pdf` |
| `--content` | choice | `full` | Content level: `full` report or `decision` only |
| `--no-dissent` | flag | off | Suppress the dissent section |
| `-o`, `--output` | path | stdout | Output file path (required for PDF) |

## Examples

Export as JSON (default):

```bash
duh export a1b2c3d4
```

Export as Markdown (full report, decision first):

```bash
duh export a1b2c3d4 --format markdown
```

Export decision only:

```bash
duh export a1b2c3d4 --format markdown --content decision
```

Export decision without dissent:

```bash
duh export a1b2c3d4 --format markdown --content decision --no-dissent
```

Export as PDF:

```bash
duh export a1b2c3d4 --format pdf -o consensus.pdf
```

Save markdown to a file:

```bash
duh export a1b2c3d4 --format markdown -o report.md
```

Extract just the decision with jq:

```bash
duh export a1b2c3d4 | jq '.turns[-1].decision.content'
```

## Output Formats

### Markdown (full)

```markdown
# Consensus: [question]

## Decision
[decision text]

Confidence: 85%

## Dissent
[dissent text]

---

## Consensus Process

### Round 1

#### Proposal (provider:model)
[proposal text]

#### Challenges
**provider:model**: [challenge text]

#### Revision (provider:model)
[revision text]

---
*duh v0.5.0 | 2026-02-17 | Cost: $0.0030*
```

### Markdown (decision only)

```markdown
# Consensus: [question]

## Decision
[decision text]

Confidence: 85%

## Dissent
[dissent text]

---
*duh v0.5.0 | 2026-02-17 | Cost: $0.0030*
```

## Related

- [`show`](show.md) -- View a thread in the terminal
- [`threads`](threads.md) -- List threads to find IDs
