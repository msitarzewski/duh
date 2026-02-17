"""Smoke tests — verify scaffolding is wired correctly."""

from click.testing import CliRunner

from duh import __version__
from duh.cli.app import cli


def test_version_string():
    assert __version__ == "0.4.0"


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.4.0" in result.output


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "consensus" in result.output


def test_subpackage_imports():
    import duh.cli
    import duh.config
    import duh.consensus
    import duh.core
    import duh.memory
    import duh.providers

    assert duh.cli is not None
    assert duh.config is not None
    assert duh.consensus is not None
    assert duh.core is not None
    assert duh.memory is not None
    assert duh.providers is not None
