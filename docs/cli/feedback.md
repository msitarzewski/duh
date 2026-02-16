# duh feedback

Record an outcome for a past decision.

## Synopsis

```
duh feedback [OPTIONS] THREAD_ID
```

## Description

The `feedback` command records whether a past consensus decision led to a successful outcome, a failure, or a partial result. This creates an `Outcome` record linked to the thread's latest decision.

Outcome tracking enables you to review which decisions worked and which didn't, building a history of decision quality over time.

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `THREAD_ID` | Yes | Full UUID or prefix (minimum 8 characters). |

## Options

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `--result` | choice | Yes | Outcome result: `success`, `failure`, or `partial`. |
| `--notes` | str | No | Optional notes explaining the outcome. |

## Prefix matching

Like `show`, you don't need the full 36-character UUID. Any unique prefix works:

```bash
duh feedback a1b2c3d4 --result success
```

If the prefix matches multiple threads, duh shows the ambiguous matches.

## Examples

Record a successful outcome:

```bash
duh feedback a1b2c3d4 --result success --notes "Deployed to production, no issues"
```

Record a failure:

```bash
duh feedback a1b2c3d4 --result failure --notes "Approach had scaling issues at 10k users"
```

Record a partial result:

```bash
duh feedback a1b2c3d4 --result partial --notes "Worked for the API layer but not the frontend"
```

## Output

```
Outcome recorded: success for thread a1b2c3d4
```

## Viewing outcomes

Outcomes are displayed when you inspect a thread with `duh show`:

```
  Outcome: success - Deployed to production, no issues
```

## Error cases

- **No thread matching**: `No thread matching '<id>'.`
- **Ambiguous prefix**: Lists all matching threads
- **No decisions**: `No decisions found for thread <id>.`

## Related commands

- [`show`](show.md) -- View a thread including its outcome
- [`ask`](ask.md) -- Create a new consensus decision
- [`recall`](recall.md) -- Search past decisions
