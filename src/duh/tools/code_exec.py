"""Code execution tool — runs code in a subprocess.

Provides safe subprocess-based code execution with timeouts
and output truncation for augmenting consensus with
computed results.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from duh.config.schema import CodeExecutionConfig


class CodeExecutionTool:
    """Code execution tool using asyncio subprocesses.

    Implements the :class:`Tool` protocol.
    """

    def __init__(self, config: CodeExecutionConfig | None = None) -> None:
        from duh.config.schema import CodeExecutionConfig as CEConfig

        self._config = config or CEConfig()

    @property
    def name(self) -> str:
        return "code_execution"

    @property
    def description(self) -> str:
        return "Execute Python code and return the output."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout in seconds (optional).",
                },
            },
            "required": ["code"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """Execute Python code in a subprocess.

        Args:
            **kwargs: Must include 'code' (str). Optional 'timeout' (int).

        Returns:
            Combined stdout/stderr output, truncated if needed.

        Raises:
            ValueError: If 'code' is missing or empty.
            RuntimeError: If execution is not enabled.
        """
        if not self._config.enabled:
            msg = (
                "Code execution is disabled. "
                "Set tools.code_execution.enabled=true in config."
            )
            raise RuntimeError(msg)

        code = kwargs.get("code", "")
        if not code or not isinstance(code, str):
            msg = "Parameter 'code' is required and must be a non-empty string."
            raise ValueError(msg)

        timeout = kwargs.get("timeout", self._config.timeout)
        if not isinstance(timeout, int) or timeout <= 0:
            timeout = self._config.timeout

        return await self._run_code(code, timeout)

    async def _run_code(self, code: str, timeout: int) -> str:
        """Run code in a subprocess with timeout."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3",
                "-c",
                code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            return f"Failed to start process: {exc}"

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            return f"Execution timed out after {timeout} seconds."

        output_parts: list[str] = []
        if stdout:
            output_parts.append(stdout.decode(errors="replace"))
        if stderr:
            output_parts.append(f"STDERR:\n{stderr.decode(errors='replace')}")

        result = "\n".join(output_parts) if output_parts else "(no output)"
        return self._truncate(result)

    def _truncate(self, text: str) -> str:
        """Truncate output to max_output characters."""
        if len(text) <= self._config.max_output:
            return text
        half = self._config.max_output // 2
        return (
            text[:half]
            + f"\n\n... [truncated {len(text) - self._config.max_output} chars] ...\n\n"
            + text[-half:]
        )
