import pytest

from linux_mcp_server.__main__ import cli
from linux_mcp_server.config import CONFIG


pytestmark = pytest.mark.usefixtures("isolated_logging")


def test_cli(mocker):
    main = mocker.patch("linux_mcp_server.server.main", autospec=True)
    cli()
    main.assert_called_once_with()


def test_cli_keyboard_interrupt(mocker):
    mocker.patch("linux_mcp_server.server.main", side_effect=KeyboardInterrupt)
    with pytest.raises(SystemExit):
        cli()


def test_cli_fatal_error(mocker):
    mocker.patch("linux_mcp_server.server.main", side_effect=RuntimeError("boom"))
    with pytest.raises(SystemExit) as exc_info:
        cli()

    assert exc_info.value.code == 1


@pytest.mark.parametrize("flag", ["redact_list", "redact_test"])
def test_cli_redaction_command(mocker, flag):
    mocker.patch.object(CONFIG, flag, True)
    run = mocker.patch("linux_mcp_server.__main__.redaction_cli.run", autospec=True, return_value=3)
    main = mocker.patch("linux_mcp_server.server.main", autospec=True)

    with pytest.raises(SystemExit) as exc_info:
        cli()

    assert exc_info.value.code == 3
    run.assert_called_once_with(CONFIG)
    main.assert_not_called()
