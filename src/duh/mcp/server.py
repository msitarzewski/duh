"""MCP server for duh consensus engine."""

from __future__ import annotations

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("duh")


def _get_tools() -> list[Tool]:
    """Define the MCP tools."""
    return [
        Tool(
            name="duh_ask",
            description=(
                "Run multi-model consensus on a question. "
                "Returns a decision that multiple LLMs agree on."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to get consensus on",
                    },
                    "protocol": {
                        "type": "string",
                        "enum": ["consensus", "voting", "auto"],
                        "default": "consensus",
                        "description": "Protocol to use",
                    },
                    "rounds": {
                        "type": "integer",
                        "default": 3,
                        "description": "Max consensus rounds",
                    },
                },
                "required": ["question"],
            },
        ),
        Tool(
            name="duh_recall",
            description="Search past consensus decisions by keyword.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "description": "Max results",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="duh_threads",
            description="List past consensus threads.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["active", "complete", "failed"],
                        "description": "Filter by status",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 20,
                        "description": "Max results",
                    },
                },
            },
        ),
    ]


@server.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return _get_tools()


@server.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict) -> list[TextContent]:  # type: ignore[type-arg]
    """Handle tool calls."""
    if name == "duh_ask":
        return await _handle_ask(arguments)
    elif name == "duh_recall":
        return await _handle_recall(arguments)
    elif name == "duh_threads":
        return await _handle_threads(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _handle_ask(args: dict) -> list[TextContent]:  # type: ignore[type-arg]
    """Run consensus and return decision."""
    import json

    from duh.cli.app import _run_consensus, _setup_providers
    from duh.config.loader import load_config

    question = args["question"]
    protocol = args.get("protocol", "consensus")
    rounds = args.get("rounds", 3)

    config = load_config()
    config.general.max_rounds = rounds
    pm = await _setup_providers(config)

    if protocol == "voting":
        from duh.consensus.voting import run_voting

        aggregation = config.voting.aggregation
        result = await run_voting(question, pm, aggregation=aggregation)
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "decision": result.decision,
                        "confidence": result.confidence,
                        "votes": len(result.votes),
                        "cost": pm.total_cost,
                    }
                ),
            )
        ]
    else:
        decision, confidence, dissent, cost = await _run_consensus(question, config, pm)
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "decision": decision,
                        "confidence": confidence,
                        "dissent": dissent,
                        "cost": cost,
                    }
                ),
            )
        ]


async def _handle_recall(args: dict) -> list[TextContent]:  # type: ignore[type-arg]
    """Search past decisions."""
    import json

    from duh.cli.app import _create_db
    from duh.config.loader import load_config
    from duh.memory.repository import MemoryRepository

    query = args["query"]
    limit = args.get("limit", 10)

    config = load_config()
    factory, engine = await _create_db(config)

    async with factory() as session:
        repo = MemoryRepository(session)
        threads = await repo.search(query, limit=limit)
        results = []
        for thread in threads:
            await session.refresh(thread, ["decisions"])
            entry: dict[str, object] = {
                "thread_id": thread.id,
                "question": thread.question,
                "status": thread.status,
            }
            if thread.decisions:
                latest = thread.decisions[-1]
                entry["decision"] = latest.content[:200]
                entry["confidence"] = latest.confidence
            results.append(entry)

    await engine.dispose()
    return [TextContent(type="text", text=json.dumps(results))]


async def _handle_threads(args: dict) -> list[TextContent]:  # type: ignore[type-arg]
    """List threads."""
    import json

    from duh.cli.app import _create_db
    from duh.config.loader import load_config
    from duh.memory.repository import MemoryRepository

    status = args.get("status")
    limit = args.get("limit", 20)

    config = load_config()
    factory, engine = await _create_db(config)

    async with factory() as session:
        repo = MemoryRepository(session)
        thread_list = await repo.list_threads(status=status, limit=limit)
        results = [
            {
                "thread_id": t.id,
                "question": t.question[:100],
                "status": t.status,
                "created_at": t.created_at.isoformat(),
            }
            for t in thread_list
        ]

    await engine.dispose()
    return [TextContent(type="text", text=json.dumps(results))]


async def run_server() -> None:
    """Start the MCP server on stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
