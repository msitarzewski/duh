# duh show

Show a thread with its full debate history.

## Synopsis

```
duh show THREAD_ID
```

## Description

Displays the complete debate history for a consensus thread: every round's proposals, challenges, revisions, and decisions. Useful for understanding how the consensus was reached.

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `THREAD_ID` | Yes | Full UUID or prefix (minimum 8 characters). |

## Prefix matching

You don't need the full 36-character UUID. Any unique prefix works:

```bash
duh show a1b2c3d4        # 8-char prefix
duh show a1b2c3d4-e5f6   # Longer prefix
```

If the prefix matches multiple threads, duh shows the ambiguous matches so you can be more specific.

## Examples

Show a thread by prefix:

```bash
duh show a1b2c3d4
```

## Output format

```
Question: What are the trade-offs between PostgreSQL and MySQL for a new SaaS product?
Status: complete
Created: 2026-02-16 14:30

--- Round 1 ---
  [PROPOSER] anthropic:claude-opus-4-6
  PostgreSQL is the stronger choice for most SaaS products...

  [CHALLENGER] openai:gpt-5.2
  I disagree with the blanket PostgreSQL recommendation...

  [REVISER] anthropic:claude-opus-4-6
  The choice depends on your workload pattern...

  Decision (confidence 100%):
  The choice depends on your workload pattern...
  Dissent: [openai:gpt-5.2]: I disagree with...
```

Each round shows:

- **Contributions** by role (PROPOSER, CHALLENGER, REVISER) with model reference
- **Decision** with confidence percentage
- **Dissent** if any genuine challenges were preserved

## Error cases

- **Thread not found**: `Thread not found: <id>`
- **Ambiguous prefix**: Lists all matching threads with their IDs and question snippets

## Related commands

- [`threads`](threads.md) -- Find thread IDs to inspect
- [`recall`](recall.md) -- Search for threads by keyword
