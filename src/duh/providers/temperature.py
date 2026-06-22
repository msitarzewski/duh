"""Self-healing for models that reject the ``temperature`` parameter.

Static sets in ``catalog.py`` cover the known cases (OpenAI gpt-5.x reasoning
models via ``NO_TEMPERATURE_MODELS``; Anthropic Opus 4.7+ via
``ANTHROPIC_NO_TEMPERATURE_MODELS``). But a newly released model can drop
``temperature`` before the catalog is updated — which has bitten us twice
(gpt-5.5, then Opus 4.8).

This module is the cross-provider safety net: when a request 400s with a
temperature-related message, the provider records the model here and retries
the request without ``temperature``. Future calls skip it from the start, so
the system self-corrects without a catalog change or a redeploy.
"""

from __future__ import annotations

# Models learned at runtime to reject temperature. Augments the static catalog
# sets; process-local (resets on restart, repopulates on first use).
_LEARNED_NO_TEMPERATURE: set[str] = set()


def omit_temperature(model_id: str, static_set: frozenset[str] | set[str]) -> bool:
    """Return True if ``temperature`` should NOT be sent for this model."""
    return model_id in static_set or model_id in _LEARNED_NO_TEMPERATURE


def record_no_temperature(model_id: str) -> None:
    """Remember that a model rejects temperature (after a 400)."""
    _LEARNED_NO_TEMPERATURE.add(model_id)


def is_temperature_error(exc: Exception) -> bool:
    """Heuristic: does this error look like 'temperature not supported'?

    Called only after a 400/BadRequest has been caught, so a message mention of
    ``temperature`` is a reliable signal (e.g. "`temperature` is deprecated for
    this model" / "temperature does not support 0.7 with this model").
    """
    return "temperature" in str(exc).lower()
