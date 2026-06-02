"""Settings for linux-mcp-server"""

import logging
import os
import sys

from pathlib import Path
from typing import Annotated
from typing import Any

from pydantic import BeforeValidator
from pydantic import Field
from pydantic import model_validator
from pydantic import SecretStr
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from linux_mcp_server.utils.enum import StrEnum
from linux_mcp_server.utils.types import UpperCase


logger = logging.getLogger(__name__)


class Transport(StrEnum):
    stdio = "stdio"
    http = "http"
    streamable_http = "streamable-http"


class Toolset(StrEnum):
    """Enumeration of available toolsets."""

    FIXED = "fixed"
    RUN_SCRIPT = "run_script"
    BOTH = "both"


class ReasoningEffort(StrEnum):
    """Reasoning effort levels for the gatekeeper model."""

    NONE = "none"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    DEFAULT = "default"


class GatekeeperProvider(StrEnum):
    """LLM provider for the gatekeeper model."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"


class GatekeeperBackend(StrEnum):
    """API backend for the gatekeeper provider."""

    DIRECT = "direct"
    VERTEX = "vertex"


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


def parse_cost(v: Any) -> Any:
    if isinstance(v, str):
        try:
            parts = v.split(":")
            return (float(parts[0]), float(parts[1]))
        except ValueError:
            raise ValueError("Cost must be formatted as '<float>:<float>'")
    elif not (v is None or (isinstance(v, tuple) and len(v) == 2 and all(isinstance(vv, (int, float)) for vv in v))):
        # This produces clearer errors if the input is just a single float, compared
        # to using the default Pydantic validation
        raise ValueError("Cost must be formatted as '<float>:<float>'")
    return v


class GatekeeperConfig(BaseSettings):
    """Gatekeeper Model configuration"""

    provider: GatekeeperProvider | None = None
    backend: GatekeeperBackend = GatekeeperBackend.DIRECT
    model: str | None = None

    # Model quantization for OpenRouter provider routing (e.g. fp8, bf16)
    quantization: str | None = None

    # OpenAI-compatible API base URL (OpenAI provider only)
    base_url: str | None = None

    # GCP project and region for Vertex backends
    project: str | None = None
    location: str | None = None

    # reasoning effort
    reasoning_effort: ReasoningEffort | None = None

    # Whether we should use structured output
    structured_output: bool = True

    # Extra chat-template arguments for OpenAI-compatible servers (e.g. llama.cpp enable_thinking).
    # Passed as chat_template_kwargs on Chat Completions requests.
    template_kwargs: dict[str, Any] = Field(default_factory=dict)

    # Temperature for gatekeeper model
    temperature: float = 0.0

    # Gatekeeper cost for accounting (input $/token, output $/token)
    cost: Annotated[tuple[float, float] | None, BeforeValidator(parse_cost)] = None


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

    gatekeeper: GatekeeperConfig = Field(default_factory=GatekeeperConfig)

    # Command execution timeout (applies to both local and remote commands)
    command_timeout: int = 30  # Timeout in seconds; prevents hung commands

    # Indicate mcp-app compatibility
    use_mcp_apps: bool | None = None

    # Force all scripts to require confirmation (even readonly ones)
    always_confirm_scripts: bool = False

    # Authentication configuration
    auth: AuthConfig | None = None

    # Authorization policy path
    policy_path: Path | None = None

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
    #     if self.toolset != Toolset.FIXED and self.gatekeeper.model is None:
    #         raise ValueError('gatekeeper.model must be set unless the toolset is "fixed"')
    #     return self

    @model_validator(mode="before")
    @staticmethod
    def handle_deprecated_aliases(data: Any) -> Any:
        if isinstance(data, dict):
            old_value = os.environ.get("LINUX_MCP_GATEKEEPER_MODEL")
            if old_value is not None:
                logger.warning(
                    "LINUX_MCP_GATEKEEPER_MODEL is deprecated. Please use LINUX_MCP_GATEKEEPER__MODEL instead.",
                )

                gatekeeper_data = data.setdefault("gatekeeper", {})
                if isinstance(gatekeeper_data, dict) and "model" not in gatekeeper_data:
                    gatekeeper_data["model"] = old_value

        return data


CONFIG = Config()
