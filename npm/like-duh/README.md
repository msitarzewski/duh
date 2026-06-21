# like-duh

npm wrapper for the **duh** multi-model consensus engine CLI.

This package is a thin shim — it finds your Python `duh` installation and forwards all arguments. No bundled Python, no runtime dependencies.

## Quick start

```bash
# Zero-install (requires duh already installed via pip/uv)
npx like-duh ask "what database should I use for my project?"

# Or install globally
npm install -g like-duh
like-duh ask "what database should I use?"
like-duh serve   # web UI on localhost:8080
```

## Prerequisites

- **Node.js** >= 18
- **Python** >= 3.11
- **duh** CLI installed via pip, uv, or pipx
- At least one LLM API key configured (see [duh docs](https://github.com/msitarzewski/duh))

## Installing duh

```bash
# Recommended
uv tool install duh

# Alternatives
pipx install duh
pip install duh
```

If `duh` is on your PATH, `like-duh` finds it automatically. You can also set `DUH_PATH` to an explicit path.

## How it works

`like-duh` resolves the `duh` executable in this order:

1. `DUH_PATH` environment variable (explicit override)
2. `duh` on PATH (pip/uv installed)
3. `uvx duh` (auto-download via uv)
4. `pipx run duh` (auto-download via pipx)

All stdio is inherited — Rich console output (colors, tables, spinners) passes through untouched. Signals (Ctrl+C) are forwarded for graceful shutdown.

## Auto-install

Set `DUH_AUTO_INSTALL=1` before installing to have the postinstall script attempt to install duh automatically:

```bash
DUH_AUTO_INSTALL=1 npm install -g like-duh
```

## Links

- [duh repository](https://github.com/msitarzewski/duh)
- [PyPI package](https://pypi.org/project/duh/)
