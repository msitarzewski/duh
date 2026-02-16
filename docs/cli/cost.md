# duh cost

Show cumulative cost from stored contributions.

## Synopsis

```
duh cost
```

## Description

Displays total spending across all stored consensus sessions. Reads from the database, so it reflects all historical usage -- not just the current session.

Shows total cost, total tokens (input + output), and a per-model breakdown sorted by cost (highest first).

## Options

No additional options. Uses `--config` from the global options.

## Examples

```bash
duh cost
```

## Output format

```
Total cost: $1.2345
Total tokens: 45,230 input + 32,100 output

By model:
  anthropic:claude-opus-4-6: $0.8200 (15 calls)
  openai:gpt-5.2: $0.3145 (12 calls)
  openai:gpt-5-mini: $0.1000 (8 calls)
```

- **Total cost** -- Sum of all contribution costs in USD
- **Total tokens** -- Aggregate input and output token counts
- **By model** -- Per-model breakdown showing cost and number of API calls, sorted by cost descending

If no contributions exist (fresh database), shows `$0.0000` totals.

## Related commands

- [`models`](models.md) -- See per-model pricing
- [`ask`](ask.md) -- Run queries (which incur costs)
