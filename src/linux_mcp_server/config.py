"""Settings for linux-mcp-server"""

import sys

from pathlib import Path

from pydantic import Field
from pydantic import SecretStr
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from linux_mcp_server.utils.enum import StrEnum
from linux_mcp_server.utils.types import UpperCase


class Transport(StrEnum):
    stdio = "stdio"
    http = "http"
    streamable_http = "streamable-http"


class Toolset(StrEnum):
    """Enumeration of available toolsets."""

    FIXED = "fixed"
    RUN_SCRIPT = "run_script"
    BOTH = "both"


class AuthProvider(StrEnum):
    """Authentication provider types."""

    GOOGLE = "google"
    GITHUB = "github"
    JWT = "jwt"
    INTROSPECTION = "introspection"


class GoogleAuthConfig(BaseSettings):
    """Google OAuth authentication configuration."""

    client_id: str
    client_secret: SecretStr


class GitHubAuthConfig(BaseSettings):
    """GitHub OAuth authentication configuration."""

    client_id: str
    client_secret: SecretStr


class JWTAuthConfig(BaseSettings):
    """JWT authentication configuration."""

    jwks_uri: str
    issuer: str
    audience: str | None = None


class IntrospectionAuthConfig(BaseSettings):
    """Token introspection authentication configuration."""

    introspection_url: str
    issuer: str
    client_id: str
    client_secret: SecretStr
    timeout_seconds: int = 10


class AuthConfig(BaseSettings):
    """Authentication configuration."""

    provider: AuthProvider | None = None
    google: GoogleAuthConfig | None = None
    github: GitHubAuthConfig | None = None
    jwt: JWTAuthConfig | None = None
    introspection: IntrospectionAuthConfig | None = None


class Config(BaseSettings):
    # The '_' is required in the env_prefix, otherwise, pydantic would
    # interpret the prefix as LINUX_MCPLOG_DIR, instead of LINUX_MCP_LOG_DIR
    model_config = SettingsConfigDict(
        env_prefix="LINUX_MCP_",
        env_nested_delimiter="__",
        env_ignore_empty=True,
        cli_hide_none_type=True,
        cli_implicit_flags=True,
        cli_kebab_case=True,
        # Only parse CLI args when running linux-mcp-server itself, not when
        # importing the module for other scripts (like eval scripts)
        cli_parse_args=sys.argv[0].endswith("linux-mcp-server"),
    )

    # FIXME: When the next version of pydantic-settings is released, change this
    # to CliToggleFlag in order to remove the '--no-' option.
    # https://github.com/pydantic/pydantic-settings/pull/717/changes
    version: bool = False

    user: str = ""
    transport: Transport = Transport.stdio
    host: str = "127.0.0.1"
    port: int = 8000
    path: str = "/mcp"

    # Logging configuration
    log_dir: Path = Path.home() / ".local" / "share" / "linux-mcp-server" / "logs"
    log_level: UpperCase = "INFO"
    log_retention_days: int = 10

    # Log file access control
    allowed_log_paths: str | None = None

    # Storage tool safety limits
    max_file_read_bytes: int = Field(default=1024 * 1024, ge=1)

    # SSH configuration
    ssh_key_path: Path | None = None
    key_passphrase: SecretStr = SecretStr("")
    search_for_ssh_key: bool = False

    # SSH host key verification (security)
    verify_host_keys: bool = True
    known_hosts_path: Path | None = None  # Custom path to known_hosts file

    # What tools are available
    toolset: Toolset = Toolset.FIXED

    # Gatekeeper model (required for run_script tools)
    gatekeeper_model: str | None = None

    # Command execution timeout (applies to both local and remote commands)
    command_timeout: int = 30  # Timeout in seconds; prevents hung commands

    # Indicate mcp-app compatibility
    use_mcp_apps: bool | None = None

    # Force all scripts to require confirmation (even readonly ones)
    always_confirm_scripts: bool = False

    # Authentication configuration
    auth: AuthConfig | None = None

    @property
    def effective_known_hosts_path(self) -> Path:
        """Return the known_hosts path, using default ~/.ssh/known_hosts if not configured."""
        return self.known_hosts_path or Path.home() / ".ssh" / "known_hosts"

    @property
    def transport_kwargs(self):
        result: dict[str, str | int] = {"log_level": self.log_level}
        if self.transport in {Transport.http, Transport.streamable_http}:
            result["host"] = self.host
            result["port"] = self.port
            result["path"] = self.path

        return result

    # Experimentally, having the tool fail with an informative error is a lot easier
    # to debug than a strange Pydantic validation error
    #
    # @model_validator(mode="after")
    # def validate_gatekeeper_model(self):
    #     if self.toolset != Toolset.FIXED and self.gatekeeper_model is None:
    #         raise ValueError('gatekeeper_model must be set unless the toolset is "fixed"')
    #     return self


CONFIG = Config()
