import re

import pytest

from pydantic_core import ValidationError

from linux_mcp_server.__main__ import cli
from linux_mcp_server.config import Config


def test_cli_version(mocker, capsys):
    mocker.patch("linux_mcp_server.__main__.CONFIG.version", True)
    regexp = re.compile(r"(\d+\.?)+")
    with pytest.raises(SystemExit):
        cli()

    out, err = capsys.readouterr()

    assert regexp.match(out)
    assert not err


@pytest.mark.parametrize(
    "args, expected",
    (
        (
            ["--transport", "streamable-http"],
            {"host": "127.0.0.1", "port": 8000, "path": "/mcp", "log_level": "INFO"},
        ),
        (
            ["--transport", "http", "--host", "7.7.7.7", "--port", "8308", "--path", "/culdesac"],
            {"host": "7.7.7.7", "port": 8308, "path": "/culdesac", "log_level": "INFO"},
        ),
    ),
    ids=["streamable", "http-host"],
)
def test_cli_transport(mocker, args, expected):
    mocker.patch("sys.argv", ["linux-mcp-server", *args])

    config = Config()

    assert config.transport_kwargs == expected


def test_cli_transport_invalid(mocker):
    mocker.patch("sys.argv", ["linux-mcp-server", "--transport", "nope"])
    with pytest.raises(ValidationError, match="Input should be"):
        Config()
