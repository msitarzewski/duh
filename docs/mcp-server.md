# MCP Server

duh can run as an [MCP](https://modelcontextprotocol.io/) (Model Context Protocol) server, allowing AI agents to use consensus-driven decision making as a tool.

## Starting the server

```bash
duh mcp
```

This starts the MCP server on stdio, ready for integration with any MCP-compatible client.

## Available tools

### duh_ask

Run multi-model consensus on a question.

**Input:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `question` | string | *required* | The question to get consensus on |
| `protocol` | string | `"consensus"` | Protocol: `consensus`, `voting`, or `auto` |
| `rounds` | integer | `3` | Max consensus rounds |

**Output:** JSON with `decision`, `confidence`, `dissent`, and `cost`.

**Example call:**

```json
{
  "name": "duh_ask",
  "arguments": {
    "question": "What is the best authentication strategy for a REST API?",
    "protocol": "consensus",
    "rounds": 2
  }
}
```

**Example response:**

```json
{
  "decision": "Use short-lived JWTs with refresh token rotation...",
  "confidence": 0.85,
  "dissent": "API keys may be simpler for server-to-server communication",
  "cost": 0.0342
}
```

### duh_recall

Search past consensus decisions by keyword.

**Input:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | *required* | Search query |
| `limit` | integer | `10` | Max results |

**Output:** JSON array of matching threads with `thread_id`, `question`, `status`, and optionally `decision` and `confidence`.

### duh_threads

List past consensus threads.

**Input:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | *all* | Filter: `active`, `complete`, or `failed` |
| `limit` | integer | `20` | Max results |

**Output:** JSON array of threads with `thread_id`, `question`, `status`, and `created_at`.

## Configuration for Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "duh": {
      "command": "duh",
      "args": ["mcp"]
    }
  }
}
```

If duh is installed in a virtual environment, use the full path:

```json
{
  "mcpServers": {
    "duh": {
      "command": "/path/to/venv/bin/duh",
      "args": ["mcp"]
    }
  }
}
```

## Configuration for Claude Code

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "duh": {
      "command": "duh",
      "args": ["mcp"]
    }
  }
}
```

## Use cases

- **Architecture decisions** -- Have your AI agent consult multiple models before recommending a database, framework, or design pattern.
- **Code review consensus** -- Get multi-model agreement on whether a code change is safe to merge.
- **Research synthesis** -- Ask complex questions and get a debated, revised answer rather than a single-model response.
- **Decision recall** -- Let your agent search past consensus decisions for relevant context.

## How it works

When an AI agent calls `duh_ask`, duh:

1. Loads your `~/.config/duh/config.toml` configuration
2. Registers all configured providers (Anthropic, OpenAI, Google, Mistral, local models)
3. Runs the consensus protocol (PROPOSE, CHALLENGE, REVISE, COMMIT)
4. Returns the consensus decision as structured JSON

The agent receives a well-debated answer rather than a single model's opinion.
