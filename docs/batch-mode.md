# Batch Mode

Process multiple questions from a file in a single run.

## Usage

```bash
duh batch questions.txt
duh batch questions.jsonl --protocol voting
duh batch questions.txt --format json --rounds 2
```

## Input formats

### Plain text

One question per line. Lines starting with `#` and blank lines are skipped.

```text title="questions.txt"
# Architecture decisions
What database should I use for a new SaaS product?
What are the trade-offs between microservices and monolith?

# Framework choices
Which Python web framework is best for a REST API?
```

### JSONL

Each line is a JSON object with a `question` field and optional `protocol` override.

```json title="questions.jsonl"
{"question": "What database should I use for a new SaaS product?"}
{"question": "REST vs GraphQL for mobile apps?", "protocol": "voting"}
{"question": "Design a CI/CD pipeline for a monorepo"}
```

The format is auto-detected from the first non-empty line.

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--protocol` | choice | `consensus` | Default protocol: `consensus`, `voting`, or `auto`. JSONL entries can override per-question. |
| `--rounds` | int | From config | Max consensus rounds |
| `--format` | choice | `text` | Output format: `text` (human-readable) or `json` (structured) |

## Output formats

### Text (default)

```
── Question 1/3 ──────────────────────────────────────────
Q: What database should I use for a new SaaS product?
Decision: PostgreSQL is the stronger choice...
Confidence: 85%
Cost: $0.0342

── Question 2/3 ──────────────────────────────────────────
Q: REST vs GraphQL for mobile apps?
Decision: GraphQL provides better flexibility...
Confidence: 80%
Cost: $0.0180

── Question 3/3 ──────────────────────────────────────────
Q: Design a CI/CD pipeline for a monorepo
Decision: Use a monorepo-aware CI system...
Confidence: 90%
Cost: $0.0450

── Summary ──────────────────────────────────────────────
3 questions | Total cost: $0.0972 | Elapsed: 45.2s
```

### JSON

```bash
duh batch questions.txt --format json
```

```json
{
  "results": [
    {
      "question": "What database should I use for a new SaaS product?",
      "decision": "PostgreSQL is the stronger choice...",
      "confidence": 0.85,
      "cost": 0.0342
    },
    {
      "question": "REST vs GraphQL for mobile apps?",
      "decision": "GraphQL provides better flexibility...",
      "confidence": 0.80,
      "cost": 0.018
    }
  ],
  "summary": {
    "total_questions": 2,
    "total_cost": 0.0522,
    "elapsed_seconds": 30.1
  }
}
```

JSON output is useful for piping into other tools or scripts:

```bash
duh batch questions.txt --format json | jq '.results[].decision'
```

## Mixed protocols

Use JSONL format to mix protocols in a single batch:

```json title="mixed.jsonl"
{"question": "Design a microservices architecture", "protocol": "consensus"}
{"question": "Should I use Tailwind or vanilla CSS?", "protocol": "voting"}
{"question": "Is Rust worth learning?", "protocol": "auto"}
```

```bash
duh batch mixed.jsonl
```

## Error handling

If a question fails (provider error, timeout, etc.), the batch continues with the remaining questions. Failed questions appear with an `error` field in JSON output:

```json
{
  "question": "...",
  "error": "Provider error: API rate limit exceeded",
  "confidence": 0.0,
  "cost": 0.001
}
```
