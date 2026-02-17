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
| [`ask`](ask.md) | Run a consensus query (supports consensus, voting, and decomposition protocols) |
| [`recall`](recall.md) | Search past decisions by keyword |
| [`threads`](threads.md) | List past consensus threads |
| [`show`](show.md) | Show a thread with its full debate history, votes, taxonomy, and outcomes |
| [`feedback`](feedback.md) | Record an outcome (success/failure/partial) for a past decision |
| [`models`](models.md) | List configured providers and available models |
| [`cost`](cost.md) | Show cumulative cost from stored contributions |
| [`serve`](serve.md) | Start the REST API server |
| [`mcp`](mcp.md) | Start the MCP server for AI agent integration |
| [`batch`](batch.md) | Run consensus on multiple questions from a file |
| [`export`](export.md) | Export a thread as JSON or Markdown |

## Common patterns

Run a consensus query:

```bash
duh ask "What testing framework should I use for a Python REST API?"
```

Use voting for quick judgment calls:

```bash
duh ask --protocol voting "Should I use Tailwind CSS or vanilla CSS?"
```

Decompose a complex question into subtasks:

```bash
duh ask --decompose "Plan a migration from monolith to microservices"
```

Enable tool use for up-to-date information:

```bash
duh ask --tools "What is the latest stable release of Python?"
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

Record whether a decision worked out:

```bash
duh feedback a1b2c3d4 --result success --notes "Worked great in production"
```

Check costs:

```bash
duh cost
```

Start the REST API server:

```bash
duh serve
duh serve --host 0.0.0.0 --port 9000
```

Start the MCP server:

```bash
duh mcp
```

Process a batch of questions:

```bash
duh batch questions.txt --format json
```

Export a thread:

```bash
duh export a1b2c3d4 --format markdown
```

Use a specific config file:

```bash
duh --config ./project-config.toml ask "question"
```
