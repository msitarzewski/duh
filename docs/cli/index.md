# CLI Reference

## Usage

```
duh [OPTIONS] COMMAND [ARGS]...
```

## Global options

| Option | Description |
|--------|-------------|
| `--config PATH` | Path to config file |
| `--version` | Show version and exit |
| `--help` | Show help and exit |

## Commands

| Command | Description |
|---------|-------------|
| [`ask`](ask.md) | Run a consensus query |
| [`recall`](recall.md) | Search past decisions by keyword |
| [`threads`](threads.md) | List past consensus threads |
| [`show`](show.md) | Show a thread with its full debate history |
| [`models`](models.md) | List configured providers and available models |
| [`cost`](cost.md) | Show cumulative cost from stored contributions |

## Common patterns

Run a consensus query:

```bash
duh ask "What testing framework should I use for a Python REST API?"
```

Search past decisions:

```bash
duh recall "testing"
```

List recent threads, then inspect one:

```bash
duh threads --limit 5
duh show a1b2c3d4
```

Check costs:

```bash
duh cost
```

Use a specific config file:

```bash
duh --config ./project-config.toml ask "question"
```
