# duh recall

Search past decisions by keyword.

## Synopsis

```
duh recall [OPTIONS] QUERY
```

## Description

Searches across thread questions and decision content for matching keywords. Results show the thread ID prefix, question text, decision snippet, and confidence score.

The search is case-insensitive and uses SQL `ILIKE` pattern matching (substring match).

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `QUERY` | Yes | Keyword(s) to search for in questions and decisions. |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--limit` | int | 10 | Maximum number of results to return. |

## Examples

Search for database-related decisions:

```bash
duh recall "database"
```

Search with a higher result limit:

```bash
duh recall --limit 25 "authentication"
```

## Output format

```
  Thread a1b2c3d4  What are the trade-offs between PostgreSQL and MySQL...
    Decision: The choice depends on your workload pattern. For read-heavy SaaS with simp...
    Confidence: 100%

  Thread e5f6g7h8  Should I use an ORM or raw SQL for my Python API?
    Decision: Use an ORM (SQLAlchemy recommended) for most cases. The productivity gains...
    Confidence: 75%
```

Each result shows:

- **Thread ID prefix** (first 8 characters)
- **Question** text
- **Decision** snippet (first 120 characters)
- **Confidence** score

If no results match, displays: `No results for 'query'.`

## Related commands

- [`show`](show.md) -- View full thread history for a result
- [`threads`](threads.md) -- Browse threads by status
- [`ask`](ask.md) -- Run a new consensus query
