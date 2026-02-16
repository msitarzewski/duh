# duh models

List configured providers and available models.

## Synopsis

```
duh models
```

## Description

Displays all models available through configured providers. Models are grouped by provider and show pricing and context window information.

This command is useful for verifying that your API keys are working and seeing which models duh will use for consensus.

## Options

No additional options. Uses `--config` from the global options.

## Examples

```bash
duh models
```

## Output format

```
anthropic:
  Claude Opus 4.6 (claude-opus-4-6)  ctx:200,000  in:$5.0/Mtok  out:$25.0/Mtok
  Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)  ctx:200,000  in:$3.0/Mtok  out:$15.0/Mtok
  Claude Haiku 4.5 (claude-haiku-4-5-20251001)  ctx:200,000  in:$1.0/Mtok  out:$5.0/Mtok

openai:
  GPT-5.2 (gpt-5.2)  ctx:400,000  in:$1.75/Mtok  out:$14.0/Mtok
  GPT-5 mini (gpt-5-mini)  ctx:400,000  in:$0.25/Mtok  out:$2.0/Mtok
  o3 (o3)  ctx:200,000  in:$2.0/Mtok  out:$8.0/Mtok
```

Each model shows:

- **Display name** -- Human-readable name
- **Model ID** -- API identifier in parentheses
- **Context window** -- Maximum tokens (input + output)
- **Input cost** -- USD per million input tokens
- **Output cost** -- USD per million output tokens

If no models are available, duh displays a message suggesting you check your API key configuration.

## Related commands

- [`ask`](ask.md) -- Use these models for a consensus query
- [`cost`](cost.md) -- See how much each model has cost
