# duh mcp

Start the MCP server for AI agent integration.

## Synopsis

```
duh mcp
```

## Description

Starts a [Model Context Protocol](https://modelcontextprotocol.io/) server on stdio. This allows AI agents (Claude Desktop, Claude Code, and other MCP-compatible clients) to use duh's consensus engine as a tool.

The server exposes three tools: `duh_ask`, `duh_recall`, and `duh_threads`.

See [MCP Server](../mcp-server.md) for full configuration and usage details.

## Examples

Run directly:

```bash
duh mcp
```

## Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

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

### Claude Code

Add to `.mcp.json` in your project:

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

## Related

- [MCP Server](../mcp-server.md) -- Full MCP server guide with tool details
