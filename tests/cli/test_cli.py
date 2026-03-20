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
def test_cli_transport(monkeypatch: pytest.MonkeyPatch, args, expected):
    monkeypatch.setattr("sys.argv", ["linux-mcp-server", *args])
    monkeypatch.setitem(Config.model_config, "cli_parse_args", True)

    config = Config()

    assert config.transport_kwargs == expected


def test_cli_transport_invalid(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("sys.argv", ["linux-mcp-server", "--transport", "nope"])
    monkeypatch.setitem(Config.model_config, "cli_parse_args", True)
    with pytest.raises(ValidationError, match="Input should be"):
        Config()
