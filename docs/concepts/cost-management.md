# Cost Management

duh tracks every token spent across all providers and gives you full visibility into costs. The philosophy: show, don't hide.

## Per-model costs

Every model has known input and output costs per million tokens. When a model responds, duh calculates:

```
cost = (input_tokens / 1,000,000) * input_cost_per_mtok
     + (output_tokens / 1,000,000) * output_cost_per_mtok
```

Costs are accumulated per-provider and globally across the session.

## Running cost display

During consensus, duh shows the running cost after each round:

```
Round 1/3 | 6 models | $0.0342 | 4.2s
```

Disable this with:

```toml
[cost]
show_running_cost = false
```

## Warn threshold

When cumulative cost exceeds the warn threshold, duh displays a warning. Default: $1.00.

```toml
[cost]
warn_threshold = 1.00
```

## Hard limit

When cumulative cost exceeds the hard limit, duh stops immediately and raises `CostLimitExceededError`. Default: $10.00.

```toml
[cost]
hard_limit = 10.00
```

Set to `0` to disable the hard limit (not recommended for production use).

## Checking cumulative costs

View total spending across all stored sessions:

```bash
duh cost
```

```
Total cost: $1.2345
Total tokens: 45,230 input + 32,100 output

By model:
  anthropic:claude-opus-4-6: $0.8200 (15 calls)
  openai:gpt-5.2: $0.3145 (12 calls)
  openai:gpt-5-mini: $0.1000 (8 calls)
```

This reads from the database, so it reflects all historical usage.

## Tips for cost-effective usage

- **Fewer rounds**: Set `max_rounds = 1` for simple questions. Multi-round is most valuable for complex, nuanced topics.
- **Cheaper challengers**: Challenger output cost doesn't need to match the proposer. GPT-5 mini at $2/Mtok output is an effective challenger.
- **Local challengers**: Use Ollama models for challenges (free). See the [Local Models guide](../guides/local-models.md).
- **Hard limits**: Set a hard limit appropriate for your budget to prevent runaway costs.

## Typical costs per query

Costs vary based on question complexity and response length. Rough estimates for a single-round consensus with default models:

| Component | Typical cost |
|-----------|-------------|
| Proposer (Claude Opus 4.6) | $0.02 - $0.05 |
| 2 Challengers (GPT-5.2) | $0.01 - $0.03 |
| Reviser (Claude Opus 4.6) | $0.02 - $0.05 |
| **Total per round** | **$0.03 - $0.10** |

Multi-round consensus multiplies this by the number of rounds (typically 1-3).

## Next steps

- [CLI Reference: cost](../cli/cost.md) -- Cost command details
- [Config Reference](../reference/config-reference.md) -- All cost configuration options
