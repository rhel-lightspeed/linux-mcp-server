"""Settings for linux-mcp-server"""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from linux_mcp_server.utils.enum import StrEnum
from linux_mcp_server.utils.types import UpperCase


class Toolset(StrEnum):
    """Enumeration of available toolsets."""

    FIXED = "fixed"
    RUN_SCRIPT = "run_script"
    BOTH = "both"


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

    # What tools are available
    toolset: Toolset = Toolset.FIXED

    # Gatekeeper model (required for run_script tools)
    gatekeeper_model: str | None = None

    # Command execution timeout (applies to remote SSH commands)
    command_timeout: int = 30  # Timeout in seconds; prevents hung SSH operations

    # Indicate mcp-app compatibility
    use_mcp_apps: bool = False

    @property
    def effective_known_hosts_path(self) -> Path:
        """Return the known_hosts path, using default ~/.ssh/known_hosts if not configured."""
        return self.known_hosts_path or Path.home() / ".ssh" / "known_hosts"

    # Experimentally, having the tool fail with an informative error is a lot easier
    # to debug than a strange Pydantic validation error
    #
    # @model_validator(mode="after")
    # def validate_gatekeeper_model(self):
    #     if self.toolset != Toolset.FIXED and self.gatekeeper_model is None:
    #         raise ValueError('gatekeeper_model must be set unless the toolset is "fixed"')
    #     return self


CONFIG = Config()
