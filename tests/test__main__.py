import pytest

from linux_mcp_server.__main__ import cli


pytestmark = pytest.mark.usefixtures("isolated_logging")


def test_cli(mocker):
    main = mocker.patch("linux_mcp_server.__main__.main", autospec=True)
    cli()
    main.assert_called_once_with()


def test_cli_keyboard_interrupt(mocker):
    mocker.patch("linux_mcp_server.__main__.main", side_effect=KeyboardInterrupt)
    with pytest.raises(SystemExit):
        cli()


def test_cli_fatal_error(mocker):
    mocker.patch("linux_mcp_server.__main__.main", side_effect=RuntimeError("boom"))
    with pytest.raises(SystemExit) as exc_info:
        cli()

    assert exc_info.value.code == 1
