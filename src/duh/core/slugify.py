"""Slug generation for public thread URLs."""

from __future__ import annotations

import hashlib
import re


def generate_slug(question: str) -> str:
    """Generate a URL-friendly slug from a question string.

    Lowercase, strip non-alphanumeric (keep spaces turned to hyphens),
    truncate to 80 chars, append 6-char hash suffix for uniqueness.
    """
    # Lowercase and replace whitespace with hyphens
    slug = question.lower().strip()
    slug = re.sub(r"\s+", "-", slug)
    # Strip non-alphanumeric except hyphens
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    # Truncate to 80 chars
    slug = slug[:80]
    # Strip trailing hyphen after truncation
    slug = slug.rstrip("-")
    # Append 6-char hash suffix
    hash_suffix = hashlib.sha256(question.encode()).hexdigest()[:6]
    return f"{slug}-{hash_suffix}" if slug else hash_suffix
