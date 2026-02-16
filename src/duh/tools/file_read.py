"""File read tool — reads file contents safely.

Provides safe file reading with path traversal protection,
binary rejection, and size limits for augmenting consensus
with file contents.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

MAX_FILE_SIZE = 100 * 1024  # 100KB


class FileReadTool:
    """File read tool with safety checks.

    Implements the :class:`Tool` protocol.
    """

    def __init__(self, *, allowed_dir: str | None = None) -> None:
        self._allowed_dir: Path | None = (
            Path(allowed_dir).resolve() if allowed_dir else None
        )

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return "Read the contents of a file."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read.",
                },
            },
            "required": ["path"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """Read a file's contents.

        Args:
            **kwargs: Must include 'path' (str).

        Returns:
            File contents as a string.

        Raises:
            ValueError: If 'path' is missing, empty, or unsafe.
            RuntimeError: If the file cannot be read.
        """
        path_str = kwargs.get("path", "")
        if not path_str or not isinstance(path_str, str):
            msg = "Parameter 'path' is required and must be a non-empty string."
            raise ValueError(msg)

        return self._read_file(path_str)

    def _read_file(self, path_str: str) -> str:
        """Read and validate a file."""
        self._validate_path(path_str)

        resolved = Path(path_str).resolve()

        if self._allowed_dir and not self._is_within(resolved, self._allowed_dir):
            msg = f"Path is outside allowed directory: {path_str}"
            raise ValueError(msg)

        if not resolved.exists():
            msg = f"File not found: {path_str}"
            raise FileNotFoundError(msg)

        if not resolved.is_file():
            msg = f"Not a regular file: {path_str}"
            raise ValueError(msg)

        if resolved.is_symlink():
            real = resolved.resolve()
            if self._allowed_dir and not self._is_within(real, self._allowed_dir):
                msg = f"Symlink escapes allowed directory: {path_str}"
                raise ValueError(msg)

        size = resolved.stat().st_size
        if size > MAX_FILE_SIZE:
            msg = (
                f"File too large: {size} bytes "
                f"(max {MAX_FILE_SIZE} bytes / {MAX_FILE_SIZE // 1024}KB)"
            )
            raise ValueError(msg)

        if self._is_binary(resolved):
            msg = f"Binary file cannot be read as text: {path_str}"
            raise ValueError(msg)

        return resolved.read_text(encoding="utf-8")

    def _validate_path(self, path_str: str) -> None:
        """Reject paths with traversal patterns."""
        normalized = os.path.normpath(path_str)
        if ".." in normalized.split(os.sep):
            msg = f"Path traversal not allowed: {path_str}"
            raise ValueError(msg)

    def _is_within(self, path: Path, directory: Path) -> bool:
        """Check if path is within directory."""
        try:
            path.relative_to(directory)
        except ValueError:
            return False
        return True

    def _is_binary(self, path: Path) -> bool:
        """Check if a file appears to be binary."""
        try:
            chunk = path.read_bytes()[:8192]
        except OSError:
            return True
        return b"\x00" in chunk
