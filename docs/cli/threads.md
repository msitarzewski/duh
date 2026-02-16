# duh threads

List past consensus threads.

## Synopsis

```
duh threads [OPTIONS]
```

## Description

Lists consensus threads ordered by most recent first. Shows the thread ID prefix, status, creation time, and question snippet for each thread.

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--status` | choice | All | Filter by status: `active`, `complete`, or `failed`. |
| `--limit` | int | 20 | Maximum number of threads to show. |

## Examples

List recent threads:

```bash
duh threads
```

List only completed threads:

```bash
duh threads --status complete
```

List the last 5 threads:

```bash
duh threads --limit 5
```

Combine filters:

```bash
duh threads --status failed --limit 10
```

## Output format

```
  a1b2c3d4  [complete]  2026-02-16 14:30  What are the trade-offs between Postgr
  e5f6g7h8  [complete]  2026-02-16 13:15  Should I use an ORM or raw SQL for my
  i9j0k1l2  [active]    2026-02-16 12:00  Design a microservices architecture fo
```

Each line shows:

- **Thread ID prefix** (first 8 characters)
- **Status** in brackets
- **Creation timestamp**
- **Question snippet** (first 60 characters)

If no threads match, displays: `No threads found.`

## Related commands

- [`show`](show.md) -- View full thread details
- [`recall`](recall.md) -- Search by keyword instead of browsing
