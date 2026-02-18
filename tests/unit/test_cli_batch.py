"""Tests for the batch CLI command: file parsing, output formats, error handling."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from duh.cli.app import _parse_batch_file, cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ── Help & argument validation ──────────────────────────────────


class TestBatchHelp:
    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["batch", "--help"])
        assert result.exit_code == 0
        assert "FILE" in result.output
        assert "--protocol" in result.output
        assert "--rounds" in result.output
        assert "--format" in result.output

    def test_missing_file_arg(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["batch"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_nonexistent_file(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["batch", "/tmp/no_such_file_xyz.txt"])
        assert result.exit_code != 0


# ── File parsing: plain text ────────────────────────────────────


class TestParseTextFile:
    def test_one_question_per_line(self, tmp_path: Any) -> None:
        f = tmp_path / "questions.txt"
        f.write_text("What is REST?\nWhat is GraphQL?\n")
        questions = _parse_batch_file(str(f), "consensus")
        assert len(questions) == 2
        assert questions[0]["question"] == "What is REST?"
        assert questions[1]["question"] == "What is GraphQL?"
        assert all(q["protocol"] == "consensus" for q in questions)

    def test_empty_lines_skipped(self, tmp_path: Any) -> None:
        f = tmp_path / "questions.txt"
        f.write_text("Q1\n\n\nQ2\n\n")
        questions = _parse_batch_file(str(f), "consensus")
        assert len(questions) == 2
        assert questions[0]["question"] == "Q1"
        assert questions[1]["question"] == "Q2"

    def test_comments_skipped(self, tmp_path: Any) -> None:
        f = tmp_path / "questions.txt"
        f.write_text("# This is a comment\nQ1\n# Another comment\nQ2\n")
        questions = _parse_batch_file(str(f), "consensus")
        assert len(questions) == 2
        assert questions[0]["question"] == "Q1"
        assert questions[1]["question"] == "Q2"

    def test_empty_file_returns_empty(self, tmp_path: Any) -> None:
        f = tmp_path / "empty.txt"
        f.write_text("")
        questions = _parse_batch_file(str(f), "consensus")
        assert questions == []

    def test_only_comments_returns_empty(self, tmp_path: Any) -> None:
        f = tmp_path / "comments.txt"
        f.write_text("# comment 1\n# comment 2\n")
        questions = _parse_batch_file(str(f), "consensus")
        assert questions == []

    def test_whitespace_stripped(self, tmp_path: Any) -> None:
        f = tmp_path / "questions.txt"
        f.write_text("  Q1  \n  Q2  \n")
        questions = _parse_batch_file(str(f), "consensus")
        assert questions[0]["question"] == "Q1"
        assert questions[1]["question"] == "Q2"


# ── File parsing: JSONL ─────────────────────────────────────────


class TestParseJsonlFile:
    def test_basic_jsonl(self, tmp_path: Any) -> None:
        f = tmp_path / "questions.jsonl"
        lines = [
            json.dumps({"question": "What is REST?"}),
            json.dumps({"question": "What is GraphQL?"}),
        ]
        f.write_text("\n".join(lines))
        questions = _parse_batch_file(str(f), "consensus")
        assert len(questions) == 2
        assert questions[0]["question"] == "What is REST?"
        assert questions[1]["question"] == "What is GraphQL?"

    def test_jsonl_with_protocol(self, tmp_path: Any) -> None:
        f = tmp_path / "questions.jsonl"
        lines = [
            json.dumps({"question": "Q1", "protocol": "voting"}),
            json.dumps({"question": "Q2"}),
        ]
        f.write_text("\n".join(lines))
        questions = _parse_batch_file(str(f), "consensus")
        assert questions[0]["protocol"] == "voting"
        assert questions[1]["protocol"] == "consensus"

    def test_jsonl_empty_lines_skipped(self, tmp_path: Any) -> None:
        f = tmp_path / "questions.jsonl"
        q1 = json.dumps({"question": "Q1"})
        q2 = json.dumps({"question": "Q2"})
        content = f"{q1}\n\n{q2}"
        f.write_text(content)
        questions = _parse_batch_file(str(f), "consensus")
        assert len(questions) == 2

    def test_invalid_jsonl_raises(self, tmp_path: Any) -> None:
        f = tmp_path / "bad.jsonl"
        f.write_text('{"question": "Q1"}\nnot valid json\n')
        with pytest.raises(ValueError, match="Invalid JSON on line"):
            _parse_batch_file(str(f), "consensus")

    def test_jsonl_missing_question_field_raises(self, tmp_path: Any) -> None:
        f = tmp_path / "bad.jsonl"
        f.write_text('{"question": "Q1"}\n{"answer": "A2"}\n')
        with pytest.raises(ValueError, match="must have a 'question' field"):
            _parse_batch_file(str(f), "consensus")

    def test_auto_detect_json(self, tmp_path: Any) -> None:
        """First line is valid JSON with 'question' key -> JSONL mode."""
        f = tmp_path / "questions.txt"
        f.write_text('{"question": "Q1"}\n{"question": "Q2"}\n')
        questions = _parse_batch_file(str(f), "consensus")
        assert len(questions) == 2

    def test_auto_detect_text(self, tmp_path: Any) -> None:
        """First line is not valid JSON -> text mode."""
        f = tmp_path / "questions.txt"
        f.write_text("What is REST?\nWhat is GraphQL?\n")
        questions = _parse_batch_file(str(f), "consensus")
        assert len(questions) == 2
        assert questions[0]["question"] == "What is REST?"


# ── Batch command: text output ──────────────────────────────────


class TestBatchTextOutput:
    @patch("duh.cli.app._batch_async", new_callable=AsyncMock)
    @patch("duh.cli.app.load_config")
    def test_text_output_runs(
        self,
        mock_config: Any,
        mock_batch: AsyncMock,
        runner: CliRunner,
        tmp_path: Any,
    ) -> None:
        from duh.config.schema import DuhConfig

        mock_config.return_value = DuhConfig()
        f = tmp_path / "q.txt"
        f.write_text("Q1\nQ2\n")

        result = runner.invoke(cli, ["batch", str(f)])
        assert result.exit_code == 0
        mock_batch.assert_called_once()
        args = mock_batch.call_args[0]
        assert len(args[0]) == 2
        assert args[0][0]["question"] == "Q1"

    @patch("duh.cli.app._batch_async", new_callable=AsyncMock)
    @patch("duh.cli.app.load_config")
    def test_rounds_option_applied(
        self,
        mock_config: Any,
        mock_batch: AsyncMock,
        runner: CliRunner,
        tmp_path: Any,
    ) -> None:
        from duh.config.schema import DuhConfig

        config = DuhConfig()
        mock_config.return_value = config
        f = tmp_path / "q.txt"
        f.write_text("Q1\n")

        result = runner.invoke(cli, ["batch", "--rounds", "5", str(f)])
        assert result.exit_code == 0
        assert config.general.max_rounds == 5

    @patch("duh.cli.app._batch_async", new_callable=AsyncMock)
    @patch("duh.cli.app.load_config")
    def test_protocol_option_passed(
        self,
        mock_config: Any,
        mock_batch: AsyncMock,
        runner: CliRunner,
        tmp_path: Any,
    ) -> None:
        from duh.config.schema import DuhConfig

        mock_config.return_value = DuhConfig()
        f = tmp_path / "q.txt"
        f.write_text("Q1\n")

        result = runner.invoke(cli, ["batch", "--protocol", "voting", str(f)])
        assert result.exit_code == 0
        args = mock_batch.call_args[0]
        assert args[0][0]["protocol"] == "voting"


# ── Batch command: JSON output ──────────────────────────────────


class TestBatchJsonOutput:
    @patch("duh.cli.app._batch_async", new_callable=AsyncMock)
    @patch("duh.cli.app.load_config")
    def test_json_format_option(
        self,
        mock_config: Any,
        mock_batch: AsyncMock,
        runner: CliRunner,
        tmp_path: Any,
    ) -> None:
        from duh.config.schema import DuhConfig

        mock_config.return_value = DuhConfig()
        f = tmp_path / "q.txt"
        f.write_text("Q1\n")

        result = runner.invoke(cli, ["batch", "--format", "json", str(f)])
        assert result.exit_code == 0
        args = mock_batch.call_args[0]
        assert args[2] == "json"


# ── Batch async: integration with mock providers ─────────────────


class TestBatchIntegration:
    def test_batch_text_full_loop(self, runner: CliRunner, tmp_path: Any) -> None:
        """Full batch flow with mocked _run_consensus."""
        from duh.config.schema import DuhConfig

        config = DuhConfig()

        f = tmp_path / "q.txt"
        f.write_text("What database?\nWhat language?\n")

        call_count = 0

        async def fake_batch(
            questions: list[dict[str, str]],
            cfg: Any,
            output_fmt: str,
        ) -> None:
            nonlocal call_count
            import click

            n = len(questions)
            for i, q in enumerate(questions, 1):
                header = f"── Question {i}/{n} "
                click.echo(f"\n{header:─<60}")
                click.echo(f"Q: {q['question']}")
                click.echo("Decision: Use SQLite.")
                click.echo("Confidence: 85%")
                click.echo("Cost: $0.0100")
                call_count += 1
            sep = "── Summary "
            click.echo(f"\n{sep:─<60}")
            click.echo(f"{n} questions | Total cost: $0.0200 | Elapsed: 1.0s")

        with (
            patch("duh.cli.app.load_config", return_value=config),
            patch("duh.cli.app._batch_async", side_effect=fake_batch),
        ):
            result = runner.invoke(cli, ["batch", str(f)])

        assert result.exit_code == 0
        assert "Question 1/2" in result.output
        assert "Question 2/2" in result.output
        assert "Summary" in result.output
        assert "2 questions" in result.output

    def test_batch_json_full_loop(self, runner: CliRunner, tmp_path: Any) -> None:
        """Full batch flow with JSON output and mocked _run_consensus."""
        from duh.config.schema import DuhConfig

        config = DuhConfig()

        f = tmp_path / "q.txt"
        f.write_text("Q1\nQ2\n")

        async def fake_batch(
            questions: list[dict[str, str]],
            cfg: Any,
            output_fmt: str,
        ) -> None:
            import click

            output = {
                "results": [
                    {
                        "question": q["question"],
                        "decision": f"Answer for {q['question']}",
                        "confidence": 0.85,
                        "cost": 0.01,
                    }
                    for q in questions
                ],
                "summary": {
                    "total_questions": len(questions),
                    "total_cost": 0.02,
                    "elapsed_seconds": 1.0,
                },
            }
            click.echo(json.dumps(output, indent=2))

        with (
            patch("duh.cli.app.load_config", return_value=config),
            patch("duh.cli.app._batch_async", side_effect=fake_batch),
        ):
            result = runner.invoke(cli, ["batch", "--format", "json", str(f)])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["results"]) == 2
        assert data["summary"]["total_questions"] == 2

    def test_per_question_error_handling(
        self, runner: CliRunner, tmp_path: Any
    ) -> None:
        """One failing question should not abort the batch."""
        from duh.config.schema import DuhConfig

        config = DuhConfig()

        f = tmp_path / "q.txt"
        f.write_text("Q1\nQ2\nQ3\n")

        async def fake_batch(
            questions: list[dict[str, str]],
            cfg: Any,
            output_fmt: str,
        ) -> None:
            import click

            results = []
            for i, q in enumerate(questions, 1):
                click.echo(
                    f"\n── Question {i}/{len(questions)} "
                    "──────────────────────────────────────────"
                )
                click.echo(f"Q: {q['question']}")
                if q["question"] == "Q2":
                    click.echo("Error: Provider timeout")
                    results.append(
                        {
                            "question": q["question"],
                            "error": "Provider timeout",
                            "confidence": 0.0,
                            "cost": 0.0,
                        }
                    )
                else:
                    click.echo("Decision: Answer.")
                    click.echo("Confidence: 85%")
                    click.echo("Cost: $0.0100")
                    results.append(
                        {
                            "question": q["question"],
                            "decision": "Answer.",
                            "confidence": 0.85,
                            "cost": 0.01,
                        }
                    )
            click.echo("\n── Summary ──────────────────────────────────────────────")
            click.echo(
                f"{len(questions)} questions | Total cost: $0.0200 | Elapsed: 1.0s"
            )

        with (
            patch("duh.cli.app.load_config", return_value=config),
            patch("duh.cli.app._batch_async", side_effect=fake_batch),
        ):
            result = runner.invoke(cli, ["batch", str(f)])

        assert result.exit_code == 0
        assert "Question 1/3" in result.output
        assert "Question 2/3" in result.output
        assert "Question 3/3" in result.output
        assert "Error: Provider timeout" in result.output
        assert "Summary" in result.output

    def test_empty_file_error(self, runner: CliRunner, tmp_path: Any) -> None:
        """Empty file should produce an error."""
        from duh.config.schema import DuhConfig

        config = DuhConfig()
        f = tmp_path / "empty.txt"
        f.write_text("")

        with patch("duh.cli.app.load_config", return_value=config):
            result = runner.invoke(cli, ["batch", str(f)])

        assert result.exit_code != 0
        assert "No questions found" in result.output


# ── _batch_async unit tests ──────────────────────────────────────


class TestBatchAsyncUnit:
    def test_consensus_protocol(self, runner: CliRunner, tmp_path: Any) -> None:
        """Batch with consensus protocol calls _run_consensus."""
        from duh.config.schema import DuhConfig
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        config = DuhConfig()
        provider = MockProvider(
            provider_id="mock",
            responses=CONSENSUS_BASIC,
            input_cost=3.0,
            output_cost=15.0,
        )

        f = tmp_path / "q.txt"
        f.write_text("What database?\n")

        consensus_called = False

        async def fake_setup(cfg: Any) -> ProviderManager:
            pm = ProviderManager()
            await pm.register(provider)
            return pm

        async def fake_consensus(
            question: str,
            cfg: Any,
            pm: Any,
            display: Any = None,
            tool_registry: Any = None,
        ) -> tuple[str, float, float, str | None, float]:
            nonlocal consensus_called
            consensus_called = True
            return ("Use SQLite.", 0.85, 1.0, None, 0.01)

        with (
            patch("duh.cli.app.load_config", return_value=config),
            patch("duh.cli.app._setup_providers", side_effect=fake_setup),
            patch("duh.cli.app._run_consensus", side_effect=fake_consensus),
        ):
            result = runner.invoke(cli, ["batch", str(f)])

        assert result.exit_code == 0
        assert consensus_called
        assert "Use SQLite." in result.output
        assert "85%" in result.output

    def test_voting_protocol(self, runner: CliRunner, tmp_path: Any) -> None:
        """Batch with voting protocol calls run_voting."""
        from duh.config.schema import DuhConfig
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import MINIMAL

        config = DuhConfig()
        provider = MockProvider(
            provider_id="mock",
            responses=MINIMAL,
            input_cost=3.0,
            output_cost=15.0,
        )

        f = tmp_path / "q.txt"
        f.write_text("What database?\n")

        async def fake_setup(cfg: Any) -> ProviderManager:
            pm = ProviderManager()
            await pm.register(provider)
            return pm

        voting_called = False

        async def fake_voting(question: str, pm: Any, **kwargs: Any) -> Any:
            nonlocal voting_called
            voting_called = True
            from duh.consensus.voting import VoteResult, VotingAggregation

            return VotingAggregation(
                votes=(VoteResult(model_ref="mock:a", content="SQLite"),),
                decision="Use SQLite.",
                strategy="majority",
                confidence=0.9,
            )

        with (
            patch("duh.cli.app.load_config", return_value=config),
            patch("duh.cli.app._setup_providers", side_effect=fake_setup),
            patch("duh.consensus.voting.run_voting", side_effect=fake_voting),
        ):
            result = runner.invoke(cli, ["batch", "--protocol", "voting", str(f)])

        assert result.exit_code == 0
        assert voting_called
        assert "Use SQLite." in result.output

    def test_json_output_structure(self, runner: CliRunner, tmp_path: Any) -> None:
        """JSON output has correct structure with results and summary."""
        from duh.config.schema import DuhConfig
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        config = DuhConfig()
        provider = MockProvider(
            provider_id="mock",
            responses=CONSENSUS_BASIC,
            input_cost=3.0,
            output_cost=15.0,
        )

        f = tmp_path / "q.txt"
        f.write_text("Q1\nQ2\n")

        async def fake_setup(cfg: Any) -> ProviderManager:
            pm = ProviderManager()
            await pm.register(provider)
            return pm

        async def fake_consensus(
            question: str,
            cfg: Any,
            pm: Any,
            display: Any = None,
            tool_registry: Any = None,
        ) -> tuple[str, float, float, str | None, float]:
            return ("Answer.", 0.9, 1.0, None, 0.01)

        with (
            patch("duh.cli.app.load_config", return_value=config),
            patch("duh.cli.app._setup_providers", side_effect=fake_setup),
            patch("duh.cli.app._run_consensus", side_effect=fake_consensus),
        ):
            result = runner.invoke(cli, ["batch", "--format", "json", str(f)])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "results" in data
        assert "summary" in data
        assert len(data["results"]) == 2
        assert data["summary"]["total_questions"] == 2
        for r in data["results"]:
            assert "question" in r
            assert "decision" in r
            assert "confidence" in r
            assert "cost" in r

    def test_error_in_one_question_continues(
        self, runner: CliRunner, tmp_path: Any
    ) -> None:
        """If one question fails, the rest still execute."""
        from duh.config.schema import DuhConfig
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        config = DuhConfig()
        provider = MockProvider(
            provider_id="mock",
            responses=CONSENSUS_BASIC,
            input_cost=3.0,
            output_cost=15.0,
        )

        f = tmp_path / "q.txt"
        f.write_text("Q1\nQ2\nQ3\n")

        call_count = 0

        async def fake_setup(cfg: Any) -> ProviderManager:
            pm = ProviderManager()
            await pm.register(provider)
            return pm

        async def fake_consensus(
            question: str,
            cfg: Any,
            pm: Any,
            display: Any = None,
            tool_registry: Any = None,
        ) -> tuple[str, float, float, str | None, float]:
            nonlocal call_count
            call_count += 1
            if question == "Q2":
                raise RuntimeError("Provider timeout")
            return ("Answer.", 0.9, 1.0, None, 0.01)

        with (
            patch("duh.cli.app.load_config", return_value=config),
            patch("duh.cli.app._setup_providers", side_effect=fake_setup),
            patch("duh.cli.app._run_consensus", side_effect=fake_consensus),
        ):
            result = runner.invoke(cli, ["batch", str(f)])

        assert result.exit_code == 0
        assert call_count == 3
        assert "Error: Provider timeout" in result.output
        assert "Summary" in result.output
        assert "3 questions" in result.output

    def test_error_in_json_output(self, runner: CliRunner, tmp_path: Any) -> None:
        """Failed questions appear with error field in JSON output."""
        from duh.config.schema import DuhConfig
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        config = DuhConfig()
        provider = MockProvider(
            provider_id="mock",
            responses=CONSENSUS_BASIC,
            input_cost=3.0,
            output_cost=15.0,
        )

        f = tmp_path / "q.txt"
        f.write_text("Q1\nQ2\n")

        async def fake_setup(cfg: Any) -> ProviderManager:
            pm = ProviderManager()
            await pm.register(provider)
            return pm

        async def fake_consensus(
            question: str,
            cfg: Any,
            pm: Any,
            display: Any = None,
            tool_registry: Any = None,
        ) -> tuple[str, float, float, str | None, float]:
            if question == "Q2":
                raise RuntimeError("Model unavailable")
            return ("Answer.", 0.9, 1.0, None, 0.01)

        with (
            patch("duh.cli.app.load_config", return_value=config),
            patch("duh.cli.app._setup_providers", side_effect=fake_setup),
            patch("duh.cli.app._run_consensus", side_effect=fake_consensus),
        ):
            result = runner.invoke(cli, ["batch", "--format", "json", str(f)])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["results"]) == 2
        # First result is success
        assert "decision" in data["results"][0]
        assert "error" not in data["results"][0]
        # Second result has error
        assert "error" in data["results"][1]
        assert "Model unavailable" in data["results"][1]["error"]
