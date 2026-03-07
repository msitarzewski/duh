"""Tests for slug generation utility."""

from __future__ import annotations

from duh.core.slugify import generate_slug


class TestGenerateSlug:
    def test_basic_question(self) -> None:
        """Simple question produces a readable slug with hash suffix."""
        slug = generate_slug("What is Python?")
        assert slug.startswith("what-is-python-")
        assert len(slug.split("-")[-1]) == 6  # hash suffix

    def test_special_characters_stripped(self) -> None:
        """Non-alphanumeric characters are removed."""
        slug = generate_slug("What's the best C++ compiler?!@#")
        assert "'" not in slug
        assert "!" not in slug
        assert "@" not in slug
        assert "#" not in slug
        # Should still have meaningful content
        assert slug.startswith("whats-the-best-c-compiler-")

    def test_whitespace_collapsed(self) -> None:
        """Multiple spaces become a single hyphen."""
        slug = generate_slug("too   many    spaces")
        assert "--" not in slug.rsplit("-", 1)[0]  # exclude hash suffix

    def test_truncation(self) -> None:
        """Slugs longer than 80 chars (before hash) are truncated."""
        long_q = "a " * 100  # 200 chars
        slug = generate_slug(long_q)
        # 80 chars max base + dash + 6 char hash = 87 max
        assert len(slug) <= 87

    def test_empty_string(self) -> None:
        """Empty input still produces a hash-only slug."""
        slug = generate_slug("")
        assert len(slug) == 6  # just the hash

    def test_unicode_stripped(self) -> None:
        """Unicode characters are stripped, leaving alphanumeric."""
        slug = generate_slug("Wie heißt du?")
        assert "ß" not in slug
        assert slug.startswith("wie-heit-du-")

    def test_deterministic(self) -> None:
        """Same input always produces same slug."""
        q = "Is Rust better than Go?"
        assert generate_slug(q) == generate_slug(q)

    def test_different_inputs_different_slugs(self) -> None:
        """Different questions produce different slugs."""
        assert generate_slug("question one") != generate_slug("question two")

    def test_leading_trailing_hyphens_stripped(self) -> None:
        """Leading/trailing hyphens are stripped."""
        slug = generate_slug("---hello---")
        base = slug.rsplit("-", 1)[0]
        assert not base.startswith("-")
        assert not base.endswith("-")
