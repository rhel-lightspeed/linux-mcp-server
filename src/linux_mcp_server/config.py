"""Settings for linux-mcp-server"""

import sys

from pathlib import Path
from typing import Any

from pydantic import SecretStr
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from linux_mcp_server.utils.enum import StrEnum
from linux_mcp_server.utils.types import UpperCase


class Transport(StrEnum):
    stdio = "stdio"
    http = "http"
    streamable_http = "streamable-http"


# Only enable CLI parsing when not running under pytest
_enable_cli_parsing = "pytest" not in sys.modules


class Config(
    BaseSettings,
    cli_parse_args=_enable_cli_parsing,
    cli_implicit_flags=_enable_cli_parsing,
    cli_kebab_case=_enable_cli_parsing,
):
    # The `_`` is required in the env_prefix, otherwise, pydantic would
    # interpret the prefix as `LINUX_MCPLOG_DIR`, instead of `LINUX_MCP_LOG_DIR`
    model_config = SettingsConfigDict(env_prefix="LINUX_MCP_", env_ignore_empty=True)

    user: str = ""
    transport: Transport = Transport.stdio
    host: str | None = None
    port: int | None = None
    path: str | None = None

    # Logging configuration
    log_dir: Path = Path.home() / ".local" / "share" / "linux-mcp-server" / "logs"
    log_level: UpperCase = "INFO"
    log_retention_days: int = 10

    # Log file access control
    allowed_log_paths: str | None = None

    # SSH configuration
    ssh_key_path: Path | None = None
    key_passphrase: SecretStr = SecretStr("")
    search_for_ssh_key: bool = False

    # SSH host key verification (security)
    verify_host_keys: bool = False  # NOTE(major): Switch to true later for production!
    known_hosts_path: Path | None = None  # Custom path to known_hosts file

    # Command execution timeout (applies to remote SSH commands)
    command_timeout: int = 30  # Timeout in seconds; prevents hung SSH operations

    @property
    def effective_known_hosts_path(self) -> Path:
        """Return the known_hosts path, using default ~/.ssh/known_hosts if not configured."""
        return self.known_hosts_path or Path.home() / ".ssh" / "known_hosts"

    @property
    def transport_kwargs(self) -> dict[str, Any]:
        """Return transport-specific keyword arguments for mcp.run()."""
        result: dict[str, Any] = {}
        if self.transport in {Transport.http, Transport.streamable_http}:
            result["host"] = self.host
            result["port"] = self.port
            result["path"] = self.path
            result["log_level"] = self.log_level

        return result


CONFIG = Config()
