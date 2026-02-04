import pytest

from linux_mcp_server.__main__ import cli


def test_cli():
    with pytest.raises(SystemExit):
        cli()


def test_cli_keyboard_interrupt(mocker):
    mocker.patch("linux_mcp_server.__main__.main", side_effect=KeyboardInterrupt)
    with pytest.raises(SystemExit):
        cli()
