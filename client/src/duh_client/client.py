"""DuhClient -- async and sync client for the duh REST API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import httpx


@dataclass
class AskResult:
    decision: str
    confidence: float
    dissent: str | None
    cost: float
    thread_id: str | None
    protocol_used: str


@dataclass
class ThreadSummary:
    thread_id: str
    question: str
    status: str
    created_at: str


@dataclass
class RecallResult:
    thread_id: str
    question: str
    decision: str | None
    confidence: float | None


class DuhAPIError(Exception):
    """Error from the duh API."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class DuhClient:
    """Client for the duh consensus engine REST API.

    Provides both async and sync interfaces.

    Usage (async)::

        async with DuhClient("http://localhost:8080") as client:
            result = await client.ask("What is the best auth strategy?")
            print(result.decision)

    Usage (sync)::

        client = DuhClient("http://localhost:8080")
        result = client.ask_sync("What is the best auth strategy?")
        print(result.decision)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_key: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        headers: dict[str, str] = {}
        if api_key:
            headers["X-API-Key"] = api_key
        self._base_url = base_url.rstrip("/")
        self._async_client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=timeout,
        )
        self._sync_client = httpx.Client(
            base_url=self._base_url,
            headers=headers,
            timeout=timeout,
        )

    async def __aenter__(self) -> DuhClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._async_client.aclose()

    def close(self) -> None:
        self._sync_client.close()

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise DuhAPIError(response.status_code, detail)

    # -- Async methods ---------------------------------------------------------

    async def ask(
        self,
        question: str,
        *,
        protocol: str = "consensus",
        rounds: int = 3,
        decompose: bool = False,
        tools: bool = False,
    ) -> AskResult:
        resp = await self._async_client.post(
            "/api/ask",
            json={
                "question": question,
                "protocol": protocol,
                "rounds": rounds,
                "decompose": decompose,
                "tools": tools,
            },
        )
        self._raise_for_status(resp)
        return AskResult(**resp.json())

    async def threads(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ThreadSummary]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        resp = await self._async_client.get("/api/threads", params=params)
        self._raise_for_status(resp)
        return [ThreadSummary(**t) for t in resp.json()["threads"]]

    async def show(self, thread_id: str) -> dict[str, Any]:
        resp = await self._async_client.get(f"/api/threads/{thread_id}")
        self._raise_for_status(resp)
        return cast("dict[str, Any]", resp.json())

    async def recall(
        self, query: str, *, limit: int = 10
    ) -> list[RecallResult]:
        resp = await self._async_client.get(
            "/api/recall", params={"query": query, "limit": limit}
        )
        self._raise_for_status(resp)
        return [RecallResult(**r) for r in resp.json()["results"]]

    async def feedback(
        self,
        thread_id: str,
        result: str,
        *,
        notes: str | None = None,
    ) -> dict[str, str]:
        body: dict[str, Any] = {"thread_id": thread_id, "result": result}
        if notes:
            body["notes"] = notes
        resp = await self._async_client.post("/api/feedback", json=body)
        self._raise_for_status(resp)
        return cast("dict[str, str]", resp.json())

    async def models(self) -> list[dict[str, Any]]:
        resp = await self._async_client.get("/api/models")
        self._raise_for_status(resp)
        return cast("list[dict[str, Any]]", resp.json()["models"])

    async def cost(self) -> dict[str, Any]:
        resp = await self._async_client.get("/api/cost")
        self._raise_for_status(resp)
        return cast("dict[str, Any]", resp.json())

    async def health(self) -> bool:
        try:
            resp = await self._async_client.get("/api/health")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    # -- Sync wrappers ---------------------------------------------------------

    def ask_sync(self, question: str, **kwargs: Any) -> AskResult:
        resp = self._sync_client.post(
            "/api/ask", json={"question": question, **kwargs}
        )
        self._raise_for_status(resp)
        return AskResult(**resp.json())

    def threads_sync(self, **kwargs: Any) -> list[ThreadSummary]:
        resp = self._sync_client.get("/api/threads", params=kwargs)
        self._raise_for_status(resp)
        return [ThreadSummary(**t) for t in resp.json()["threads"]]

    def recall_sync(self, query: str, **kwargs: Any) -> list[RecallResult]:
        resp = self._sync_client.get(
            "/api/recall", params={"query": query, **kwargs}
        )
        self._raise_for_status(resp)
        return [RecallResult(**r) for r in resp.json()["results"]]

    def models_sync(self) -> list[dict[str, Any]]:
        resp = self._sync_client.get("/api/models")
        self._raise_for_status(resp)
        return cast("list[dict[str, Any]]", resp.json()["models"])

    def health_sync(self) -> bool:
        try:
            resp = self._sync_client.get("/api/health")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
