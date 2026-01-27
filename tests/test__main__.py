import pytest

from typer.testing import CliRunner

from linux_mcp_server.__main__ import app


runner = CliRunner()


def test_cli():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_cli_keyboard_interrupt(mocker):
    mocker.patch("linux_mcp_server.__main__.main", side_effect=KeyboardInterrupt)
    mocker.patch("linux_mcp_server.__main__.setup_logging")
    result = runner.invoke(app, [])
    assert result.exit_code == 0
