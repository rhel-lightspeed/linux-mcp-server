"""Settings for linux-mcp-server"""

import sys

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from linux_mcp_server.utils.types import UpperCase


class Config(BaseSettings):
    # The `_`` is required in the env_prefix, otherwise, pydantic would
    # interpret the prefix as `LINUX_MCPLOG_DIR`, instead of `LINUX_MCP_LOG_DIR`
    model_config = SettingsConfigDict(env_prefix="LINUX_MCP_", env_ignore_empty=True)

    user: str = ""

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

    # SSH connection timeout (separate from command execution timeout)
    ssh_connect_timeout: int = 10  # Timeout for establishing SSH connection

    # SSH backend selection (auto-detected by default)
    ssh_backend: Literal["subprocess", "asyncssh"] | None = None
    ssh_control_persist: int = 300  # ControlMaster persist time in seconds (subprocess backend)

    @property
    def effective_ssh_backend(self) -> Literal["subprocess", "asyncssh"]:
        """Determine SSH backend based on explicit config or platform."""
        if self.ssh_backend:
            return self.ssh_backend
        # Windows requires asyncssh (no ControlMaster support)
        if sys.platform == "win32":
            return "asyncssh"
        # Unix-likes use subprocess for full SSH config inheritance
        return "subprocess"

    @property
    def effective_known_hosts_path(self) -> Path:
        """Return the known_hosts path, using default ~/.ssh/known_hosts if not configured."""
        return self.known_hosts_path or Path.home() / ".ssh" / "known_hosts"


CONFIG = Config()
