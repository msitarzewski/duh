# Memory and Persistence

duh stores every consensus session in a local database so you can recall past decisions, inspect full debate histories, and build on previous context.

## What duh remembers

Every consensus run persists:

| Entity | What it stores |
|--------|---------------|
| **Thread** | The question, status (active/complete/failed), timestamps |
| **Turn** | One round of PROPOSE/CHALLENGE/REVISE/COMMIT |
| **Contribution** | A single model's output (role, content, token counts, cost, latency) |
| **Decision** | The committed decision text, confidence score, and dissent |
| **TurnSummary** | LLM-generated summary of a single turn |
| **ThreadSummary** | LLM-generated summary of an entire thread |

## Database

duh uses SQLite by default, stored at:

```
~/.local/share/duh/duh.db
```

The database is created automatically on first use. Tables are managed via SQLAlchemy ORM with async support (aiosqlite).

!!! tip "Custom database location"
    Change the database URL in your config:

    ```toml
    [database]
    url = "sqlite+aiosqlite:///path/to/your/duh.db"
    ```

    Any SQLAlchemy async-compatible URL works, though SQLite is the only tested backend.

## Database schema

```
threads
├── turns
│   ├── contributions    (model outputs with token/cost tracking)
│   ├── decision         (committed decision per turn)
│   └── turn_summary     (LLM summary of the turn)
└── thread_summary       (LLM summary of the thread)
```

Key relationships:

- A **thread** has many **turns** (one per consensus round)
- Each **turn** has multiple **contributions** (proposer + challengers + reviser)
- Each **turn** has at most one **decision** (from COMMIT phase)
- Each **thread** and **turn** can have an LLM-generated **summary**

## Searching past decisions

Use `duh recall` to search across thread questions and decision content:

```bash
duh recall "database"
```

The search uses SQL `ILIKE` for case-insensitive keyword matching across both `threads.question` and `decisions.content`.

## Inspecting threads

List recent threads:

```bash
duh threads
duh threads --status complete --limit 5
```

View a thread's full debate history:

```bash
duh show a1b2c3d4
```

Thread IDs support prefix matching -- you only need the first 8 characters (or enough to be unambiguous).

## Context building

duh uses past thread context to inform future queries. The context builder assembles relevant history (previous decisions, summaries) to provide continuity across sessions. This means follow-up questions can reference prior debates.

## Next steps

- [CLI Reference: recall](../cli/recall.md) -- Search syntax and options
- [CLI Reference: show](../cli/show.md) -- Thread inspection details
- [CLI Reference: threads](../cli/threads.md) -- Thread listing and filtering
