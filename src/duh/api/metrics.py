"""Lightweight Prometheus metrics — no external dependencies."""

from __future__ import annotations

import math
import threading
from typing import ClassVar

from fastapi import APIRouter, Response

router = APIRouter()


class Counter:
    """Thread-safe monotonic counter."""

    def __init__(
        self,
        name: str,
        help_text: str,
        labels: list[str] | None = None,
    ) -> None:
        self.name = name
        self.help_text = help_text
        self.labels = labels or []
        self._lock = threading.Lock()
        # When labels are used, store per-label-combo values
        self._values: dict[tuple[str, ...], float] = {}
        if not self.labels:
            self._values[()] = 0.0
        MetricsRegistry.get().register(self)

    def inc(self, value: float = 1.0, **label_values: str) -> None:
        """Increment the counter."""
        key = tuple(label_values.get(lbl, "") for lbl in self.labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + value

    def collect(self) -> str:
        """Return Prometheus text format."""
        lines: list[str] = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} counter",
        ]
        with self._lock:
            for key, val in sorted(self._values.items()):
                if self.labels:
                    label_str = ",".join(
                        f'{lbl}="{v}"' for lbl, v in zip(self.labels, key, strict=True)
                    )
                    lines.append(f"{self.name}{{{label_str}}} {_fmt(val)}")
                else:
                    lines.append(f"{self.name} {_fmt(val)}")
        return "\n".join(lines) + "\n"


class Histogram:
    """Thread-safe histogram with predefined buckets."""

    DEFAULT_BUCKETS: ClassVar[list[float]] = [
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    ]

    def __init__(
        self,
        name: str,
        help_text: str,
        buckets: list[float] | None = None,
    ) -> None:
        self.name = name
        self.help_text = help_text
        self.buckets = sorted(buckets or self.DEFAULT_BUCKETS)
        self._lock = threading.Lock()
        self._bucket_counts: dict[float, int] = {b: 0 for b in self.buckets}
        self._sum: float = 0.0
        self._count: int = 0
        MetricsRegistry.get().register(self)

    def observe(self, value: float) -> None:
        """Record an observation."""
        with self._lock:
            self._sum += value
            self._count += 1
            for b in self.buckets:
                if value <= b:
                    self._bucket_counts[b] += 1
                    break

    def collect(self) -> str:
        """Return Prometheus text format."""
        lines: list[str] = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} histogram",
        ]
        with self._lock:
            cumulative = 0
            for b in self.buckets:
                cumulative += self._bucket_counts[b]
                lines.append(f'{self.name}_bucket{{le="{_fmt(b)}"}} {cumulative}')
            lines.append(f'{self.name}_bucket{{le="+Inf"}} {self._count}')
            lines.append(f"{self.name}_sum {_fmt(self._sum)}")
            lines.append(f"{self.name}_count {self._count}")
        return "\n".join(lines) + "\n"


class Gauge:
    """Thread-safe gauge (can go up and down)."""

    def __init__(self, name: str, help_text: str) -> None:
        self.name = name
        self.help_text = help_text
        self._lock = threading.Lock()
        self._value: float = 0.0
        MetricsRegistry.get().register(self)

    def set(self, value: float) -> None:
        """Set to an absolute value."""
        with self._lock:
            self._value = value

    def inc(self, value: float = 1.0) -> None:
        """Increment."""
        with self._lock:
            self._value += value

    def dec(self, value: float = 1.0) -> None:
        """Decrement."""
        with self._lock:
            self._value -= value

    def collect(self) -> str:
        """Return Prometheus text format."""
        with self._lock:
            val = self._value
        return (
            f"# HELP {self.name} {self.help_text}\n"
            f"# TYPE {self.name} gauge\n"
            f"{self.name} {_fmt(val)}\n"
        )


class MetricsRegistry:
    """Global registry of all metrics."""

    _instance: ClassVar[MetricsRegistry | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        self._metrics: list[Counter | Histogram | Gauge] = []

    @classmethod
    def get(cls) -> MetricsRegistry:
        """Return the singleton registry."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = MetricsRegistry()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for tests)."""
        with cls._lock:
            cls._instance = None

    def register(self, metric: Counter | Histogram | Gauge) -> None:
        """Register a metric for collection."""
        self._metrics.append(metric)

    def collect_all(self) -> str:
        """Return concatenated Prometheus text format for all metrics."""
        return "\n".join(m.collect() for m in self._metrics)


def _fmt(v: float) -> str:
    """Format a float: use integer form when possible."""
    if math.isinf(v):
        return "+Inf"
    if v == int(v):
        return str(int(v))
    return str(v)


# ── Pre-defined metrics ──────────────────────────────────────────

REQUESTS_TOTAL = Counter(
    "duh_requests_total",
    "Total HTTP requests",
    labels=["method", "path", "status"],
)
CONSENSUS_RUNS_TOTAL = Counter(
    "duh_consensus_runs_total",
    "Total consensus runs",
)
TOKENS_TOTAL = Counter(
    "duh_tokens_total",
    "Total tokens consumed",
    labels=["provider", "direction"],
)
ERRORS_TOTAL = Counter(
    "duh_errors_total",
    "Total errors",
    labels=["type"],
)
REQUEST_DURATION = Histogram(
    "duh_request_duration_seconds",
    "Request duration",
)
CONSENSUS_DURATION = Histogram(
    "duh_consensus_duration_seconds",
    "Consensus run duration",
)
ACTIVE_CONNECTIONS = Gauge(
    "duh_active_connections",
    "Active connections",
)
PROVIDER_HEALTH = Gauge(
    "duh_provider_health",
    "Provider health status",
)


@router.get("/api/metrics")
async def metrics_endpoint() -> Response:
    """Serve all registered metrics in Prometheus text format."""
    registry = MetricsRegistry.get()
    return Response(
        content=registry.collect_all(),
        media_type="text/plain; version=0.0.4",
    )
