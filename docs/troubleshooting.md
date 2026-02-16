# Troubleshooting

Common issues and their solutions.

## "No API key" errors

**Symptom**: `Error: [anthropic] Invalid or missing API key` or similar.

**Fix**:

1. Check that the environment variable is set:

    ```bash
    echo $ANTHROPIC_API_KEY
    echo $OPENAI_API_KEY
    ```

2. If empty, set it:

    ```bash
    export ANTHROPIC_API_KEY=sk-ant-...
    export OPENAI_API_KEY=sk-...
    ```

3. Make sure it persists by adding to your shell profile (`~/.bashrc`, `~/.zshrc`).

4. Verify with `duh models` -- you should see models listed under each provider.

## "No models available"

**Symptom**: `No models available. Configure providers in ~/.config/duh/config.toml or set API key environment variables.`

**Fix**:

- Set at least one API key (see above)
- Check that providers are enabled in config (they are by default)
- Run `duh models` to see what's available

If using local models, verify the server is running:

```bash
curl http://localhost:11434/v1/models  # Ollama
curl http://localhost:1234/v1/models   # LM Studio
```

## Rate limiting (429 errors)

**Symptom**: `[openai] Rate limited` or `[anthropic] Rate limited`

**Fix**:

- Wait a few seconds and retry. duh handles transient rate limits automatically.
- If persistent, you may be hitting account-level limits. Check your API provider's usage dashboard.
- Consider using fewer consensus rounds (`--rounds 1`).

## Cost limit exceeded

**Symptom**: `Cost limit $10.00 exceeded (current: $10.23)`

**Fix**:

Increase the hard limit in your config:

```toml
[cost]
hard_limit = 50.00
```

Or disable it (use with caution):

```toml
[cost]
hard_limit = 0
```

Check your spending with `duh cost`.

## Database locked

**Symptom**: `StorageError` or SQLite lock errors.

**Fix**:

- Make sure only one instance of duh is running at a time
- If a previous process crashed, the lock file should clear automatically
- As a last resort, delete the database and start fresh:

    ```bash
    rm ~/.local/share/duh/duh.db
    ```

    !!! warning
        This deletes all stored threads and decisions.

## Import errors

**Symptom**: `ModuleNotFoundError: No module named 'duh'` or similar.

**Fix**:

- Make sure duh is installed in the active environment:

    ```bash
    uv pip list | grep duh
    ```

- If using `uv`, run via:

    ```bash
    uv run duh ask "question"
    ```

- If installed globally, check your PATH.

## Docker volume issues

**Symptom**: Data lost between container restarts, or "permission denied" on `/data`.

**Fix**:

- Verify the volume exists:

    ```bash
    docker volume ls | grep duh
    ```

- The container runs as user `duh` (UID 1000). The `/data` directory must be writable by this user.

- If rebuilding from scratch:

    ```bash
    docker compose down -v  # Removes volumes!
    docker compose build
    docker compose run duh ask "test"
    ```

## Config file not found

**Symptom**: `Config file not found: /path/to/config.toml`

**Fix**:

- Check that the file exists at the specified path
- If using `DUH_CONFIG`, verify the environment variable:

    ```bash
    echo $DUH_CONFIG
    ```

- duh works without any config file (uses sensible defaults). You only need a config file to customize behavior.

## Sycophantic challenges

**Symptom**: All challenges flagged as "sycophantic", low-quality consensus.

**Cause**: Challenger models are agreeing with the proposal instead of genuinely challenging it. This can happen with:

- Weaker or smaller local models
- Same-model self-critique (only one provider configured)

**Fix**:

- Use multiple providers (Anthropic + OpenAI) for cross-model challenges
- Use stronger challenger models
- duh already uses aggressive anti-sycophancy prompts, but model compliance varies

## FAQ

### How many models do I need?

At minimum, 1 (duh will use the same model for proposing, challenging, and revising). For best results, use 2+ models from different providers.

### Can I use only local models?

Yes. Configure the OpenAI provider with a `base_url` pointing to Ollama or LM Studio. All model costs will be $0.00.

### How much does a typical query cost?

With default models (Claude Opus + GPT-5.2), a single-round consensus costs roughly $0.03-$0.10 depending on response length. See [Cost Management](concepts/cost-management.md) for details.

### Can I use duh without an internet connection?

Yes, if you use only local models (Ollama, LM Studio). See the [Local Models guide](guides/local-models.md).

### Where is the database stored?

Default: `~/.local/share/duh/duh.db`. Change it in config under `[database]`.

### How do I reset everything?

Delete the database file:

```bash
rm ~/.local/share/duh/duh.db
```

This removes all threads, decisions, and cost history. Configuration is not affected.
