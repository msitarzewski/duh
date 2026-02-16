# 150215_project-scaffolding

## Objective
v0.1 Task 1: Create the full project scaffolding — package layout, tooling config, tests, CI, Docker, Alembic.

## Outcome
- 4/4 smoke tests passing
- Linter: 0 errors, 0 warnings
- mypy strict: 0 issues (9 source files)
- Format: 16 files clean
- Docker: builds successfully
- CLI: `duh --version`, `duh --help`, `python -m duh --version` all work

## Files Created/Modified
- `pyproject.toml` — Rewritten from Phase 0 to v0.1 (all runtime + dev deps, pytest/ruff/mypy/coverage config)
- `.gitignore` — Added coverage, mypy, ruff, pytest, database sections
- `src/duh/__init__.py` — `__version__ = "0.1.0dev0"`
- `src/duh/__main__.py` — `python -m duh` entry point
- `src/duh/py.typed` — PEP 561 marker
- `src/duh/cli/app.py` — Click group: `--version`, `--help`, `consensus` stub
- `src/duh/{cli,consensus,providers,memory,config,core}/__init__.py` — Docstring only
- `tests/conftest.py` — Shared fixtures (empty for now)
- `tests/unit/test_smoke.py` — 4 smoke tests (version, CLI --version, CLI --help, subpackage imports)
- `tests/{unit,integration,sycophancy,fixtures}/__init__.py` — Empty
- `Dockerfile` — Multi-stage (builder + runtime), uv-based, non-root user, /data volume
- `.github/workflows/ci.yml` — 3 parallel jobs (lint, typecheck, test) using astral-sh/setup-uv@v4
- `alembic.ini` — sqlite+aiosqlite config
- `alembic/env.py` — Offline/online migration support (target_metadata=None until task 10)
- `alembic/script.py.mako` — Migration template

## Patterns Applied
- `techContext.md` — uv, Click, Rich, SQLAlchemy, pytest, ruff, mypy
- `decisions.md#ADR-001` — src layout
- `roadmap.md:592-606` — Package structure

## Key Decisions
- All v0.1 runtime deps declared upfront (avoids lockfile churn)
- `asyncio_mode = "auto"` (no per-test boilerplate)
- `mypy strict = true` from day 1, tests exempt from `disallow_untyped_defs`
- `fail_under = 0` coverage (raised incrementally per task)
- Phase 0 code untouched in `phase0/`
