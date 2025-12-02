"""Settings for linux-mcp-server"""

import getpass

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from linux_mcp_server.utils.types import UpperCase


class Config(BaseSettings):
    # The `_`` is required in the env_prefix, otherwise, pydantic would
    # interpret the prefix as `LINUX_MCPLOG_DIR`, instead of `LINUX_MCP_LOG_DIR`
    model_config = SettingsConfigDict(env_prefix="LINUX_MCP_", env_ignore_empty=True)

    user: str = getpass.getuser()

    # Logging configuration
    log_dir: Optional[Path] = None
    log_level: UpperCase = "INFO"
    log_retention_days: int = 10

    # Log file access control
    allowed_log_paths: Optional[str] = None

    # SSH configuration
    ssh_key_path: Optional[Path] = None
    key_passphrase: Optional[str] = None
    search_for_ssh_key: bool = False


CONFIG = Config()
