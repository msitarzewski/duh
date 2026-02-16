"""Tests for concrete tool implementations (web_search, code_exec, file_read)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from duh.config.schema import CodeExecutionConfig, WebSearchConfig
from duh.tools.base import Tool
from duh.tools.code_exec import CodeExecutionTool
from duh.tools.file_read import MAX_FILE_SIZE, FileReadTool
from duh.tools.web_search import WebSearchTool

# ── WebSearchTool ──────────────────────────────────────────────────


class TestWebSearchToolProtocol:
    def test_implements_tool_protocol(self) -> None:
        tool = WebSearchTool()
        assert isinstance(tool, Tool)

    def test_name(self) -> None:
        tool = WebSearchTool()
        assert tool.name == "web_search"

    def test_description_nonempty(self) -> None:
        tool = WebSearchTool()
        assert len(tool.description) > 0

    def test_parameters_schema(self) -> None:
        tool = WebSearchTool()
        schema = tool.parameters_schema
        assert schema["type"] == "object"
        assert "query" in schema["properties"]
        assert "query" in schema["required"]


class TestWebSearchToolExecute:
    async def test_missing_query_raises(self) -> None:
        tool = WebSearchTool()
        with pytest.raises(ValueError, match=r"query.*required"):
            await tool.execute()

    async def test_empty_query_raises(self) -> None:
        tool = WebSearchTool()
        with pytest.raises(ValueError, match=r"query.*required"):
            await tool.execute(query="")

    async def test_non_string_query_raises(self) -> None:
        tool = WebSearchTool()
        with pytest.raises(ValueError, match=r"query.*required"):
            await tool.execute(query=123)

    async def test_duckduckgo_search_success(self) -> None:
        tool = WebSearchTool()
        fake_results = [
            {"title": "Result 1", "href": "https://example.com", "body": "Snippet 1"},
            {"title": "Result 2", "href": "https://example.org", "body": "Snippet 2"},
        ]
        with patch.object(tool, "_ddg_sync_search", return_value=fake_results):
            result = await tool.execute(query="test query")
        assert "Result 1" in result
        assert "https://example.com" in result
        assert "Snippet 1" in result
        assert "Result 2" in result

    async def test_duckduckgo_no_results(self) -> None:
        tool = WebSearchTool()
        with patch.object(tool, "_ddg_sync_search", return_value=[]):
            result = await tool.execute(query="obscure query")
        assert "No results found" in result

    async def test_duckduckgo_import_error(self) -> None:
        tool = WebSearchTool()
        with (
            patch.object(
                tool,
                "_ddg_sync_search",
                side_effect=RuntimeError("duckduckgo-search package is required"),
            ),
            pytest.raises(RuntimeError, match=r"duckduckgo-search"),
        ):
            await tool.execute(query="test")

    async def test_tavily_missing_api_key(self) -> None:
        config = WebSearchConfig(backend="tavily", api_key=None)
        tool = WebSearchTool(config=config)
        with pytest.raises(RuntimeError, match=r"Tavily API key"):
            await tool.execute(query="test")

    def test_format_results(self) -> None:
        tool = WebSearchTool()
        results = [
            {"title": "Title A", "href": "https://a.com", "body": "Body A"},
            {"title": "Title B", "href": "", "body": "Body B"},
        ]
        formatted = tool._format_results(results)
        assert "1. Title A" in formatted
        assert "URL: https://a.com" in formatted
        assert "2. Title B" in formatted
        # No URL line for empty href
        lines = formatted.split("\n")
        title_b_idx = next(i for i, line in enumerate(lines) if "2. Title B" in line)
        assert "URL:" not in lines[title_b_idx + 1]

    def test_uses_config_max_results(self) -> None:
        config = WebSearchConfig(max_results=3)
        tool = WebSearchTool(config=config)
        assert tool._config.max_results == 3

    def test_default_config(self) -> None:
        tool = WebSearchTool()
        assert tool._config.backend == "duckduckgo"
        assert tool._config.max_results == 5


# ── CodeExecutionTool ──────────────────────────────────────────────


class TestCodeExecutionToolProtocol:
    def test_implements_tool_protocol(self) -> None:
        tool = CodeExecutionTool()
        assert isinstance(tool, Tool)

    def test_name(self) -> None:
        tool = CodeExecutionTool()
        assert tool.name == "code_execution"

    def test_description_nonempty(self) -> None:
        tool = CodeExecutionTool()
        assert len(tool.description) > 0

    def test_parameters_schema(self) -> None:
        tool = CodeExecutionTool()
        schema = tool.parameters_schema
        assert schema["type"] == "object"
        assert "code" in schema["properties"]
        assert "code" in schema["required"]


class TestCodeExecutionToolExecute:
    async def test_disabled_raises(self) -> None:
        config = CodeExecutionConfig(enabled=False)
        tool = CodeExecutionTool(config=config)
        with pytest.raises(RuntimeError, match=r"disabled"):
            await tool.execute(code="print(1)")

    async def test_missing_code_raises(self) -> None:
        config = CodeExecutionConfig(enabled=True)
        tool = CodeExecutionTool(config=config)
        with pytest.raises(ValueError, match=r"code.*required"):
            await tool.execute()

    async def test_empty_code_raises(self) -> None:
        config = CodeExecutionConfig(enabled=True)
        tool = CodeExecutionTool(config=config)
        with pytest.raises(ValueError, match=r"code.*required"):
            await tool.execute(code="")

    async def test_non_string_code_raises(self) -> None:
        config = CodeExecutionConfig(enabled=True)
        tool = CodeExecutionTool(config=config)
        with pytest.raises(ValueError, match=r"code.*required"):
            await tool.execute(code=42)

    async def test_execute_simple_code(self) -> None:
        config = CodeExecutionConfig(enabled=True, timeout=10)
        tool = CodeExecutionTool(config=config)
        result = await tool.execute(code="print('hello world')")
        assert "hello world" in result

    async def test_execute_stderr_captured(self) -> None:
        config = CodeExecutionConfig(enabled=True, timeout=10)
        tool = CodeExecutionTool(config=config)
        result = await tool.execute(code="import sys; sys.stderr.write('err msg')")
        assert "STDERR" in result
        assert "err msg" in result

    async def test_execute_timeout(self) -> None:
        config = CodeExecutionConfig(enabled=True, timeout=1)
        tool = CodeExecutionTool(config=config)
        result = await tool.execute(code="import time; time.sleep(10)")
        assert "timed out" in result

    async def test_execute_custom_timeout(self) -> None:
        config = CodeExecutionConfig(enabled=True, timeout=30)
        tool = CodeExecutionTool(config=config)
        result = await tool.execute(code="print('fast')", timeout=5)
        assert "fast" in result

    async def test_execute_invalid_timeout_uses_default(self) -> None:
        config = CodeExecutionConfig(enabled=True, timeout=10)
        tool = CodeExecutionTool(config=config)
        result = await tool.execute(code="print('ok')", timeout=-1)
        assert "ok" in result

    async def test_execute_no_output(self) -> None:
        config = CodeExecutionConfig(enabled=True, timeout=10)
        tool = CodeExecutionTool(config=config)
        result = await tool.execute(code="x = 1")
        assert "no output" in result

    async def test_execute_syntax_error(self) -> None:
        config = CodeExecutionConfig(enabled=True, timeout=10)
        tool = CodeExecutionTool(config=config)
        result = await tool.execute(code="def")
        assert "STDERR" in result
        assert "SyntaxError" in result

    def test_truncate_short(self) -> None:
        config = CodeExecutionConfig(enabled=True, max_output=100)
        tool = CodeExecutionTool(config=config)
        text = "short text"
        assert tool._truncate(text) == text

    def test_truncate_long(self) -> None:
        config = CodeExecutionConfig(enabled=True, max_output=100)
        tool = CodeExecutionTool(config=config)
        text = "x" * 200
        truncated = tool._truncate(text)
        assert "truncated" in truncated
        assert len(truncated) < 200

    def test_default_config(self) -> None:
        tool = CodeExecutionTool()
        assert tool._config.enabled is False
        assert tool._config.timeout == 30


# ── FileReadTool ───────────────────────────────────────────────────


class TestFileReadToolProtocol:
    def test_implements_tool_protocol(self) -> None:
        tool = FileReadTool()
        assert isinstance(tool, Tool)

    def test_name(self) -> None:
        tool = FileReadTool()
        assert tool.name == "file_read"

    def test_description_nonempty(self) -> None:
        tool = FileReadTool()
        assert len(tool.description) > 0

    def test_parameters_schema(self) -> None:
        tool = FileReadTool()
        schema = tool.parameters_schema
        assert schema["type"] == "object"
        assert "path" in schema["properties"]
        assert "path" in schema["required"]


class TestFileReadToolExecute:
    async def test_missing_path_raises(self) -> None:
        tool = FileReadTool()
        with pytest.raises(ValueError, match=r"path.*required"):
            await tool.execute()

    async def test_empty_path_raises(self) -> None:
        tool = FileReadTool()
        with pytest.raises(ValueError, match=r"path.*required"):
            await tool.execute(path="")

    async def test_non_string_path_raises(self) -> None:
        tool = FileReadTool()
        with pytest.raises(ValueError, match=r"path.*required"):
            await tool.execute(path=123)

    async def test_read_text_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello content", encoding="utf-8")
        tool = FileReadTool(allowed_dir=str(tmp_path))
        result = await tool.execute(path=str(f))
        assert result == "hello content"

    async def test_path_traversal_rejected(self) -> None:
        tool = FileReadTool()
        with pytest.raises(ValueError, match=r"traversal"):
            await tool.execute(path="../../../etc/passwd")

    async def test_path_traversal_normalized(self) -> None:
        tool = FileReadTool()
        # Absolute path with .. normalizes cleanly — caught by allowed_dir
        # instead. Test a relative path with .. that survives normpath.
        with pytest.raises(ValueError, match=r"traversal"):
            await tool.execute(path="foo/../../etc/passwd")

    async def test_outside_allowed_dir(self, tmp_path: Path) -> None:
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        tool = FileReadTool(allowed_dir=str(allowed))
        with pytest.raises(ValueError, match=r"outside allowed"):
            await tool.execute(path=str(outside))

    async def test_file_not_found(self, tmp_path: Path) -> None:
        tool = FileReadTool(allowed_dir=str(tmp_path))
        with pytest.raises(FileNotFoundError, match=r"not found"):
            await tool.execute(path=str(tmp_path / "nonexistent.txt"))

    async def test_not_a_file(self, tmp_path: Path) -> None:
        d = tmp_path / "adir"
        d.mkdir()
        tool = FileReadTool(allowed_dir=str(tmp_path))
        with pytest.raises(ValueError, match=r"Not a regular file"):
            await tool.execute(path=str(d))

    async def test_file_too_large(self, tmp_path: Path) -> None:
        f = tmp_path / "large.txt"
        f.write_bytes(b"x" * (MAX_FILE_SIZE + 1))
        tool = FileReadTool(allowed_dir=str(tmp_path))
        with pytest.raises(ValueError, match=r"too large"):
            await tool.execute(path=str(f))

    async def test_binary_file_rejected(self, tmp_path: Path) -> None:
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x00\x01\x02\x03binary data")
        tool = FileReadTool(allowed_dir=str(tmp_path))
        with pytest.raises(ValueError, match=r"Binary file"):
            await tool.execute(path=str(f))

    async def test_symlink_within_allowed(self, tmp_path: Path) -> None:
        real = tmp_path / "real.txt"
        real.write_text("real content", encoding="utf-8")
        link = tmp_path / "link.txt"
        link.symlink_to(real)
        tool = FileReadTool(allowed_dir=str(tmp_path))
        result = await tool.execute(path=str(link))
        assert result == "real content"

    async def test_no_allowed_dir_reads_anywhere(self, tmp_path: Path) -> None:
        f = tmp_path / "anywhere.txt"
        f.write_text("anywhere", encoding="utf-8")
        tool = FileReadTool()
        result = await tool.execute(path=str(f))
        assert result == "anywhere"

    async def test_max_file_size_constant(self) -> None:
        assert MAX_FILE_SIZE == 100 * 1024


class TestFileReadToolPathValidation:
    def test_validate_path_simple(self) -> None:
        tool = FileReadTool()
        tool._validate_path("/some/valid/path.txt")

    def test_validate_path_traversal(self) -> None:
        tool = FileReadTool()
        with pytest.raises(ValueError, match=r"traversal"):
            tool._validate_path("../secret")

    def test_validate_path_embedded_traversal(self) -> None:
        tool = FileReadTool()
        with pytest.raises(ValueError, match=r"traversal"):
            tool._validate_path("foo/../../bar")

    def test_is_within_true(self) -> None:
        tool = FileReadTool()
        assert tool._is_within(Path("/a/b/c"), Path("/a/b"))

    def test_is_within_false(self) -> None:
        tool = FileReadTool()
        assert not tool._is_within(Path("/a/b"), Path("/a/b/c"))

    def test_is_binary_text(self, tmp_path: Path) -> None:
        f = tmp_path / "text.txt"
        f.write_text("hello", encoding="utf-8")
        tool = FileReadTool()
        assert not tool._is_binary(f)

    def test_is_binary_binary(self, tmp_path: Path) -> None:
        f = tmp_path / "bin.dat"
        f.write_bytes(b"\x00\x01\x02")
        tool = FileReadTool()
        assert tool._is_binary(f)


# ── Registry integration ──────────────────────────────────────────


class TestToolRegistryIntegration:
    async def test_all_tools_register(self) -> None:
        from duh.tools.registry import ToolRegistry

        reg = ToolRegistry()
        reg.register(WebSearchTool())
        reg.register(CodeExecutionTool())
        reg.register(FileReadTool())
        assert len(reg) == 3
        assert "web_search" in reg
        assert "code_execution" in reg
        assert "file_read" in reg

    async def test_definitions_generated(self) -> None:
        from duh.tools.registry import ToolRegistry

        reg = ToolRegistry()
        reg.register(WebSearchTool())
        reg.register(CodeExecutionTool())
        reg.register(FileReadTool())
        defs = reg.list_definitions()
        assert len(defs) == 3
        names = {d.name for d in defs}
        assert names == {"web_search", "code_execution", "file_read"}
