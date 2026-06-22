# 260622_cloudflare-glm-provider

## Objective
Add Zhipu **GLM-5.2** as a usable model via Cloudflare Workers AI, and in doing
so generalize the OpenAI adapter to serve any OpenAI-compatible host. (PR #18.)

## Outcome
- **`cloudflare` provider** backed by Cloudflare Workers AI's OpenAI-compatible
  endpoint, with `@cf/zai-org/glm-5.2` in the catalog (262,144 context,
  $1.40 / $4.40 per Mtok, per the Workers AI model page).
- **Generalized `OpenAIProvider`**: gained an optional `provider_id` (default
  `"openai"`) and resolves its model catalog + capabilities from that id (was
  hardcoded). So it can run as `cloudflare` *alongside* real OpenAI without a
  provider_id collision. This now enables ANY OpenAI-compatible host (Groq,
  Together, OpenRouter, AI Gateway) by config alone.
- **`_setup_providers`** (app.py): generic branch — any enabled provider with a
  `base_url` + key registers as an OpenAI-compatible adapter under its config name.
- **`.env`-driven**: `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_WORKERS_AI_TOKEN`.
  The loader builds the account's Workers AI base URL
  (`https://api.cloudflare.com/client/v4/accounts/<id>/ai/v1`) and configures the
  provider. Missing either → no provider (graceful).

## Files
- `src/duh/providers/openai.py` — instance-based provider_id / catalog / caps
- `src/duh/providers/catalog.py` — `cloudflare` capabilities + GLM-5.2 entry
- `src/duh/cli/app.py` — generic base_url+key registration branch
- `src/duh/config/loader.py` — `_resolve_cloudflare()` from env vars
- `.env.example` — documents `CLOUDFLARE_*`
- Tests: `test_providers_openai.py` (custom provider_id), `test_config.py`
  (cloudflare env wiring), `test_cli.py` (registration)

## Validation (live, against the user's Cloudflare account)
- Provider wires up from `.env`; `@cf/zai-org/glm-5.2` appears in `duh models`
- Plain text generation works (`finish_reason=stop`, token accounting correct)
- **JSON mode works** — important because COMMIT and follow-up generation use
  `response_format`
- Note: GLM-5.2 is a reasoning model that spends tokens thinking, so it needs
  real `max_tokens` headroom (duh uses 32k budgets — fine).

## Usage
```
duh ask "..." --proposer cloudflare:@cf/zai-org/glm-5.2
duh ask "..." --challengers cloudflare:@cf/zai-org/glm-5.2,openai:gpt-5.5
```

## Patterns
- One adapter, many hosts: `OpenAIProvider(provider_id=name, base_url=...)`.
- Test-isolation gotcha: `load_config()` runs `load_dotenv()`, which finds the
  repo `.env` via the caller frame (not cwd). Tests asserting a provider is
  *absent* must set the env vars to `""` (load_dotenv won't override existing,
  even empty, vars), not `delenv` them.
