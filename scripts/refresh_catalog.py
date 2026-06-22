#!/usr/bin/env python3
"""Manual model-catalog refresh tool — propose-only, never auto-applies.

What it does (run on demand, no cron):

1. Reads the models currently in ``duh.providers.catalog.MODEL_CATALOG``.
2. For each, pulls a *projection* (price / context / max-output / status) from
   the community truefoundry/models feed and diffs it against our catalog.
3. Hashes that projection and compares to ``scripts/catalog_snapshot.json`` so
   you can see what changed since the last run.
4. Queries the live provider APIs to surface NEW frontier models (in the API,
   not in our catalog) and models we list that the API no longer returns.
5. Empirically probes OpenAI temperature support against the real endpoint —
   because the feed is unreliable on *behavioral* fields (it had gpt-5.5 wrong)
   — and flags any mismatch with ``NO_TEMPERATURE_MODELS``.

It prints a report and (with --write-snapshot) updates the snapshot. It does
NOT modify ``catalog.py``. Pricing/context/status are DATA: diffed for you to
confirm. Temperature is BEHAVIOR: verified live before trusting.

Usage:
    uv run python scripts/refresh_catalog.py
    uv run python scripts/refresh_catalog.py --no-probe        # offline-ish
    uv run python scripts/refresh_catalog.py --write-snapshot  # save baseline
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from duh.providers.catalog import (
    ANTHROPIC_NO_TEMPERATURE_MODELS,
    MODEL_CATALOG,
    NO_TEMPERATURE_MODELS,
)

# truefoundry provider directory names (differ from our provider_id keys)
_TF_BASE = "https://raw.githubusercontent.com/truefoundry/models/main/providers"
_TF_DIR = {
    "anthropic": "anthropic",
    "openai": "openai",
    "google": "google-gemini",
    "mistral": "mistral",
    "perplexity": "perplexity",
}
_SNAPSHOT = Path(__file__).parent / "catalog_snapshot.json"
_PRICE_TOL = 1e-4  # $/Mtok difference worth reporting


# ── HTTP helpers (stdlib only) ─────────────────────────────────


def _get_text(url: str, headers: dict[str, str] | None = None) -> str | None:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.read().decode()
    except (urllib.error.URLError, TimeoutError):
        return None


def _get_json(url: str, headers: dict[str, str] | None = None) -> Any | None:
    text = _get_text(url, headers)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _post_json(url: str, headers: dict[str, str], body: dict[str, Any]) -> Any | None:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except (json.JSONDecodeError, ValueError):
            return None
    except (urllib.error.URLError, TimeoutError):
        return None


# ── truefoundry feed ───────────────────────────────────────────


def _num(text: str, key: str) -> float | None:
    m = re.search(rf"^\s*{re.escape(key)}:\s*([0-9.eE+-]+)", text, re.M)
    return float(m.group(1)) if m else None


def _str(text: str, key: str) -> str | None:
    m = re.search(rf'^\s*{re.escape(key)}:\s*"?(\w[\w.-]*)"?', text, re.M)
    return m.group(1) if m else None


def tf_projection(provider: str, model_id: str) -> dict[str, Any] | None:
    """Fetch {input_mtok, output_mtok, context, max_output, status} from feed."""
    tf_dir = _TF_DIR.get(provider)
    if tf_dir is None:
        return None
    text = _get_text(f"{_TF_BASE}/{tf_dir}/{model_id}.yaml")
    if text is None:
        return None
    ic = _num(text, "input_cost_per_token")
    oc = _num(text, "output_cost_per_token")
    return {
        "input_cost_per_mtok": round(ic * 1e6, 4) if ic is not None else None,
        "output_cost_per_mtok": round(oc * 1e6, 4) if oc is not None else None,
        "context_window": int(_num(text, "context_window") or 0) or None,
        "max_output_tokens": int(_num(text, "max_output_tokens") or 0) or None,
        "status": _str(text, "status"),
    }


def _hash(projection: dict[str, Any]) -> str:
    payload = json.dumps(projection, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ── live provider model lists ──────────────────────────────────


def live_ids(provider: str) -> set[str] | None:
    """Return the set of model IDs the live API reports, or None if no key."""
    if provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            return None
        data = _get_json(
            "https://api.anthropic.com/v1/models?limit=100",
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
        )
        return {m["id"] for m in data["data"]} if data else None
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            return None
        data = _get_json(
            "https://api.openai.com/v1/models", {"Authorization": f"Bearer {key}"}
        )
        if not data:
            return None
        # Frontier chat/reasoning families only — skip legacy & non-chat variants
        keep = re.compile(r"^(gpt-5(\.\d+)?|o[34])(-mini|-nano|-pro)?$")
        return {m["id"] for m in data["data"] if keep.match(m["id"])}
    if provider == "google":
        key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not key:
            return None
        data = _get_json(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={key}&pageSize=200"
        )
        if not data:
            return None
        skip = re.compile(r"tts|image|embedding|aqa|learnlm|gemma|robotics|computer")
        return {
            m["name"].removeprefix("models/")
            for m in data.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
            and "gemini" in m["name"]
            and not skip.search(m["name"])
        }
    return None


def probe_openai_temperature(model_id: str) -> bool | None:
    """True if the model accepts temperature!=1, False if it rejects, None on error."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    resp = _post_json(
        "https://api.openai.com/v1/chat/completions",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        {
            "model": model_id,
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.7,
            "max_completion_tokens": 16,
        },
    )
    if resp is None:
        return None
    err = resp.get("error") if isinstance(resp, dict) else None
    if err:
        return False if "temperature" in err.get("message", "") else None
    return True


def probe_anthropic_temperature(model_id: str) -> bool | None:
    """True if the model accepts temperature, False if it rejects, None on error."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    resp = _post_json(
        "https://api.anthropic.com/v1/messages",
        {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        {
            "model": model_id,
            "max_tokens": 16,
            "temperature": 0.7,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    if resp is None:
        return None
    err = resp.get("error") if isinstance(resp, dict) else None
    if isinstance(err, dict):
        return False if "temperature" in err.get("message", "") else None
    return True


# ── report ─────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-probe", action="store_true", help="skip live behavioral probes"
    )
    parser.add_argument(
        "--write-snapshot", action="store_true", help="update catalog_snapshot.json"
    )
    args = parser.parse_args()

    load_dotenv()
    snapshot: dict[str, str] = {}
    if _SNAPSHOT.exists():
        snapshot = json.loads(_SNAPSHOT.read_text())
    new_snapshot: dict[str, str] = {}

    print("=" * 70)
    print("CATALOG REFRESH — proposal only, nothing is modified")
    print("=" * 70)

    data_diffs: list[str] = []
    changed_since_last: list[str] = []

    for provider, models in MODEL_CATALOG.items():
        for m in models:
            mid = provider + ":" + m["model_id"]
            proj = tf_projection(provider, m["model_id"])
            if proj is None:
                new_snapshot[mid] = "no-feed"
                continue
            h = _hash(proj)
            new_snapshot[mid] = h
            if snapshot.get(mid) not in (None, h):
                changed_since_last.append(mid)
            for field in ("input_cost_per_mtok", "output_cost_per_mtok"):
                up = proj[field]
                cur = m.get(field)
                if up is not None and abs(up - cur) > _PRICE_TOL:
                    data_diffs.append(f"  {mid}  {field}: {cur} -> {up} (feed)")
            for field in ("context_window", "max_output_tokens"):
                up = proj[field]
                cur = m.get(field)
                if up is not None and up != cur:
                    data_diffs.append(f"  {mid}  {field}: {cur} -> {up} (feed)")
            if proj["status"] == "deprecated":
                data_diffs.append(f"  {mid}  STATUS=deprecated (drop candidate)")

    print("\n## DATA changes vs catalog (price / context / status) — confirm manually")
    print("\n".join(data_diffs) if data_diffs else "  (none — catalog matches feed)")

    print("\n## Changed since last snapshot")
    print(
        "\n".join("  " + m for m in changed_since_last)
        if changed_since_last
        else "  (none)"
    )

    print("\n## DISCOVERY — live API vs catalog")
    for provider in MODEL_CATALOG:
        ids = live_ids(provider)
        if ids is None:
            print(f"  {provider}: (no key / no list endpoint — skipped)")
            continue
        catalog_ids = {m["model_id"] for m in MODEL_CATALOG[provider]}
        new = sorted(ids - catalog_ids)
        gone = sorted(catalog_ids - ids)
        if new:
            print(f"  {provider}: NEW candidates -> {', '.join(new)}")
        if gone:
            print(f"  {provider}: in catalog but not in API -> {', '.join(gone)}")
        if not new and not gone:
            print(f"  {provider}: in sync")

    if not args.no_probe:
        print("\n## BEHAVIOR — OpenAI temperature probe vs NO_TEMPERATURE_MODELS")
        openai_ids = {m["model_id"] for m in MODEL_CATALOG.get("openai", [])}
        for mid in sorted(openai_ids):
            accepts = probe_openai_temperature(mid)
            if accepts is None:
                print(f"  {mid}: probe inconclusive")
                continue
            listed = mid in NO_TEMPERATURE_MODELS
            rejects = not accepts
            if rejects and not listed:
                print(f"  {mid}: REJECTS temp but NOT in NO_TEMPERATURE_MODELS — ADD")
            elif accepts and listed:
                print(
                    f"  {mid}: accepts temp but IS in NO_TEMPERATURE_MODELS"
                    " — review (may be intentional w/ reasoning_effort)"
                )
            else:
                print(f"  {mid}: ok ({'no-temp' if rejects else 'temp'})")

        print("\n## BEHAVIOR — Anthropic temperature probe vs catalog set")
        anthropic_ids = {m["model_id"] for m in MODEL_CATALOG.get("anthropic", [])}
        for mid in sorted(anthropic_ids):
            accepts = probe_anthropic_temperature(mid)
            if accepts is None:
                print(f"  {mid}: probe inconclusive")
                continue
            listed = mid in ANTHROPIC_NO_TEMPERATURE_MODELS
            rejects = not accepts
            if rejects and not listed:
                print(
                    f"  {mid}: REJECTS temp but NOT in "
                    "ANTHROPIC_NO_TEMPERATURE_MODELS — ADD"
                )
            elif accepts and listed:
                print(
                    f"  {mid}: accepts temp but IS in "
                    "ANTHROPIC_NO_TEMPERATURE_MODELS — REMOVE"
                )
            else:
                print(f"  {mid}: ok ({'no-temp' if rejects else 'temp'})")

    if args.write_snapshot:
        _SNAPSHOT.write_text(json.dumps(new_snapshot, indent=2, sort_keys=True) + "\n")
        print(f"\nSnapshot written to {_SNAPSHOT}")
    else:
        print("\n(run with --write-snapshot to save this baseline)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
