"""Web search tool — searches the web via DuckDuckGo or Tavily.

Provides formatted search results for augmenting consensus
with real-time information from the web.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from duh.config.schema import WebSearchConfig


class WebSearchTool:
    """Web search tool using DuckDuckGo (default) or Tavily backend.

    Implements the :class:`Tool` protocol.
    """

    def __init__(self, config: WebSearchConfig | None = None) -> None:
        from duh.config.schema import WebSearchConfig as WSConfig

        self._config = config or WSConfig()

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web for current information on a topic."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """Execute a web search.

        Args:
            **kwargs: Must include 'query' (str).

        Returns:
            Formatted search results as a string.

        Raises:
            ValueError: If 'query' is missing or empty.
            RuntimeError: If the search backend fails.
        """
        query = kwargs.get("query", "")
        if not query or not isinstance(query, str):
            msg = "Parameter 'query' is required and must be a non-empty string."
            raise ValueError(msg)

        if self._config.backend == "tavily":
            return await self._search_tavily(query)
        return await self._search_duckduckgo(query)

    async def _search_duckduckgo(self, query: str) -> str:
        """Search using DuckDuckGo."""
        import asyncio

        try:
            import duckduckgo_search  # noqa: F401
        except ImportError:
            msg = (
                "duckduckgo-search package is required for web search. "
                "Install with: pip install duckduckgo-search"
            )
            raise RuntimeError(msg) from None

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None,
            self._ddg_sync_search,
            query,
        )

        if not results:
            return f"No results found for: {query}"

        return self._format_results(results)

    def _ddg_sync_search(self, query: str) -> list[dict[str, str]]:
        """Synchronous DuckDuckGo search (run in executor)."""
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=self._config.max_results))

    async def _search_tavily(self, query: str) -> str:
        """Search using Tavily API."""
        if not self._config.api_key:
            msg = "Tavily API key is required. Set tools.web_search.api_key in config."
            raise RuntimeError(msg)

        import asyncio
        import json
        from urllib.request import Request, urlopen

        def _fetch() -> list[dict[str, str]]:
            url = "https://api.tavily.com/search"
            payload = json.dumps(
                {
                    "api_key": self._config.api_key,
                    "query": query,
                    "max_results": self._config.max_results,
                }
            ).encode()
            req = Request(url, data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            return [
                {
                    "title": r.get("title", ""),
                    "href": r.get("url", ""),
                    "body": r.get("content", ""),
                }
                for r in data.get("results", [])
            ]

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, _fetch)

        if not results:
            return f"No results found for: {query}"

        return self._format_results(results)

    def _format_results(self, results: list[dict[str, str]]) -> str:
        """Format search results into a readable string."""
        lines: list[str] = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            url = r.get("href", "")
            snippet = r.get("body", "No description")
            lines.append(f"{i}. {title}")
            if url:
                lines.append(f"   URL: {url}")
            lines.append(f"   {snippet}")
            lines.append("")
        return "\n".join(lines).strip()
