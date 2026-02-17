# Export

Export a thread's full debate history as JSON or Markdown.

## Usage

```bash
duh export <thread-id>                    # JSON (default)
duh export <thread-id> --format markdown  # Markdown
duh export <thread-id> --format json      # Explicit JSON
```

Thread IDs support prefix matching (minimum 8 characters):

```bash
duh export a1b2c3d4
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--format` | choice | `json` | Export format: `json` or `markdown` |

## JSON export

```bash
duh export a1b2c3d4 --format json > thread.json
```

```json
{
  "thread_id": "a1b2c3d4-5678-...",
  "question": "What database should I use for a new SaaS product?",
  "status": "complete",
  "created_at": "2026-02-15T10:30:00",
  "turns": [
    {
      "round_number": 1,
      "state": "propose",
      "contributions": [
        {
          "model_ref": "anthropic:claude-opus-4-6",
          "role": "proposer",
          "content": "PostgreSQL is the best choice...",
          "input_tokens": 150,
          "output_tokens": 500,
          "cost_usd": 0.013
        },
        {
          "model_ref": "openai:gpt-5.2",
          "role": "challenger",
          "content": "I disagree with the blanket recommendation...",
          "input_tokens": 200,
          "output_tokens": 400,
          "cost_usd": 0.006
        }
      ],
      "decision": {
        "content": "The choice depends on your workload...",
        "confidence": 0.85,
        "dissent": null
      }
    }
  ],
  "votes": [],
  "exported_at": "2026-02-16T14:00:00+00:00"
}
```

The JSON export includes:

- Thread metadata (ID, question, status, creation time)
- Every round with all contributions (model, role, content, tokens, cost)
- Decisions with confidence and dissent
- Votes (for voting protocol threads)
- Export timestamp

## Markdown export

```bash
duh export a1b2c3d4 --format markdown > thread.md
```

```markdown
# Thread: What database should I use for a new SaaS product?
**Status**: complete | **Created**: 2026-02-15

## Round 1
### Proposer (anthropic:claude-opus-4-6)
PostgreSQL is the best choice...

### Challenger (openai:gpt-5.2)
I disagree with the blanket recommendation...

### Decision
**Confidence**: 85%
The choice depends on your workload...

---
*Exported from duh v0.3.0*
```

## Piping and scripting

Export pairs well with other tools:

```bash
# Save to file
duh export a1b2c3d4 > decision.json

# Pretty-print with jq
duh export a1b2c3d4 | jq .

# Extract just the decision
duh export a1b2c3d4 | jq '.turns[-1].decision.content'

# Export multiple threads
for id in $(duh threads --limit 5 | awk '{print $1}'); do
  duh export "$id" > "export_${id}.json"
done

# Convert to Markdown for documentation
duh export a1b2c3d4 --format markdown >> decisions.md
```
