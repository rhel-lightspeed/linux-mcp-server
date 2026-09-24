"""TLS configuration and forwarding to the server."""

from pathlib import Path
from typing import Any

import pytest

from pytest_mock import MockerFixture

from linux_mcp_server import server
from linux_mcp_server.config import Config
from linux_mcp_server.config import Transport


@pytest.mark.parametrize(
    "transport, enabled, expected",
    [
        (Transport.stdio, False, {"log_level": "INFO"}),
        (Transport.http, False, {"log_level": "INFO", "host": "127.0.0.1", "port": 8000, "path": "/mcp"}),
        (Transport.streamable_http, False, {"log_level": "INFO", "host": "127.0.0.1", "port": 8000, "path": "/mcp"}),
        (
            Transport.http,
            True,
            {
                "log_level": "INFO",
                "host": "127.0.0.1",
                "port": 8000,
                "path": "/mcp",
                "uvicorn_config": {"ssl_certfile": "cert.pem", "ssl_keyfile": "key.pem"},
            },
        ),
        (
            Transport.streamable_http,
            True,
            {
                "log_level": "INFO",
                "host": "127.0.0.1",
                "port": 8000,
                "path": "/mcp",
                "uvicorn_config": {"ssl_certfile": "cert.pem", "ssl_keyfile": "key.pem"},
            },
        ),
    ],
)
def test_tls_transport(transport: Transport, enabled: bool, expected: dict[str, Any], mocker: MockerFixture) -> None:
    config = Config(
        transport=transport,
        tls_cert=Path("cert.pem") if enabled else None,
        tls_key=Path("key.pem") if enabled else None,
    )
    assert config.transport_kwargs == expected

    mocker.patch.object(server, "CONFIG", config)
    run = mocker.patch.object(server.mcp, "run", autospec=True)
    server.main()
    run.assert_called_once_with(show_banner=False, transport=transport.value, **expected)


def test_tls_rejects_stdio() -> None:
    with pytest.raises(ValueError, match="TLS requires"):
        Config(transport=Transport.stdio, tls_cert=Path("cert.pem"), tls_key=Path("key.pem"))


@pytest.mark.parametrize("field", ["tls_cert", "tls_key"])
def test_tls_requires_pair(field: str) -> None:
    with pytest.raises(ValueError, match="must be set together"):
        Config(
            transport=Transport.http,
            tls_cert=Path("tls.pem") if field == "tls_cert" else None,
            tls_key=Path("tls.pem") if field == "tls_key" else None,
        )


@pytest.mark.parametrize("cli", [False, True])
def test_tls_settings(monkeypatch: pytest.MonkeyPatch, cli: bool) -> None:
    monkeypatch.setenv("LINUX_MCP_TRANSPORT", "http")
    monkeypatch.setenv("LINUX_MCP_TLS_CERT", "env-cert.pem")
    monkeypatch.setenv("LINUX_MCP_TLS_KEY", "env-key.pem")
    args = ["--tls-cert", "cli-cert.pem", "--tls-key", "cli-key.pem"] if cli else []
    monkeypatch.setattr("sys.argv", ["linux-mcp-server", *args])
    monkeypatch.setitem(Config.model_config, "cli_parse_args", True)
    config = Config()
    prefix = "cli" if cli else "env"
    assert config.tls_cert == Path(f"{prefix}-cert.pem")
    assert config.tls_key == Path(f"{prefix}-key.pem")
