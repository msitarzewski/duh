# duh export

Export a thread with its full debate history.

## Synopsis

```
duh export [OPTIONS] THREAD_ID
```

## Description

Exports a complete thread including all rounds, contributions, decisions, votes, and metadata. Output can be JSON (for programmatic use) or Markdown (for documentation).

Thread IDs support prefix matching (minimum 8 characters).

See [Export](../export.md) for output format details and scripting examples.

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `THREAD_ID` | Yes | Full UUID or prefix (minimum 8 chars) |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--format` | choice | `json` | Export format: `json` or `markdown` |

## Examples

Export as JSON:

```bash
duh export a1b2c3d4
```

Export as Markdown:

```bash
duh export a1b2c3d4 --format markdown
```

Save to a file:

```bash
duh export a1b2c3d4 > thread.json
duh export a1b2c3d4 --format markdown > thread.md
```

Extract just the decision with jq:

```bash
duh export a1b2c3d4 | jq '.turns[-1].decision.content'
```

## Related

- [Export](../export.md) -- Full export guide with format details
- [`show`](show.md) -- View a thread in the terminal
- [`threads`](threads.md) -- List threads to find IDs
