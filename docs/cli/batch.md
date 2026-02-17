# duh batch

Run consensus on multiple questions from a file.

## Synopsis

```
duh batch [OPTIONS] FILE
```

## Description

Processes multiple questions sequentially from a file. Supports plain text (one question per line) and JSONL (one JSON object per line with a `question` field). The format is auto-detected.

Each question runs through the consensus (or voting) protocol independently. Results are displayed as they complete.

See [Batch Mode](../batch-mode.md) for input format details and examples.

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `FILE` | Yes | Path to a text or JSONL file containing questions |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--protocol` | choice | `consensus` | Default protocol: `consensus`, `voting`, or `auto`. JSONL entries can override per-question. |
| `--rounds` | int | From config (3) | Max consensus rounds |
| `--format` | choice | `text` | Output format: `text` (human-readable) or `json` (structured) |

## Examples

Basic batch run:

```bash
duh batch questions.txt
```

JSON output for scripting:

```bash
duh batch questions.txt --format json > results.json
```

Use voting protocol:

```bash
duh batch questions.txt --protocol voting
```

Fewer rounds for faster processing:

```bash
duh batch questions.txt --rounds 1
```

## Input file formats

**Plain text** -- one question per line, `#` comments and blank lines skipped:

```text
What database should I use for SaaS?
# This line is a comment
REST vs GraphQL for mobile apps?
```

**JSONL** -- each line is a JSON object:

```json
{"question": "What database should I use?"}
{"question": "REST vs GraphQL?", "protocol": "voting"}
```

## Related

- [Batch Mode](../batch-mode.md) -- Full guide with output examples
- [`ask`](ask.md) -- Run a single consensus query
