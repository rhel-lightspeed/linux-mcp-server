"""Configuration management for Linux MCP Server.

This module handles loading and managing configuration from YAML files,
including remote host definitions, SSH settings, and logging configuration.
"""

import logging
import os

from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import yaml


logger = logging.getLogger(__name__)


class HostConfig:
    """Configuration for a remote host."""

    def __init__(
        self,
        name: str,
        host: str,
        username: str,
        description: str = "",
        ssh_key_path: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ):
        self.name = name
        self.host = host
        self.username = username
        self.description = description
        self.ssh_key_path = ssh_key_path
        self.tags = tags or []

    def __repr__(self) -> str:
        return f"HostConfig(name={self.name}, host={self.host}, username={self.username})"


class SSHConfig:
    """SSH connection configuration."""

    def __init__(
        self,
        default_key_path: Optional[str] = None,
        connection_timeout: int = 30,
        keep_alive: bool = True,
        keep_alive_interval: int = 30,
    ):
        self.default_key_path = default_key_path
        self.connection_timeout = connection_timeout
        self.keep_alive = keep_alive
        self.keep_alive_interval = keep_alive_interval


class LoggingConfig:
    """Logging configuration."""

    def __init__(
        self,
        level: str = "INFO",
        retention_days: int = 10,
        directory: str = "/app/logs",
    ):
        self.level = level
        self.retention_days = retention_days
        self.directory = directory


class ServerConfig:
    """Main server configuration."""

    def __init__(
        self,
        hosts: Optional[List[HostConfig]] = None,
        ssh_config: Optional[SSHConfig] = None,
        allowed_log_paths: Optional[List[str]] = None,
        logging_config: Optional[LoggingConfig] = None,
    ):
        self.hosts = hosts or []
        self.ssh_config = ssh_config or SSHConfig()
        self.allowed_log_paths = allowed_log_paths or []
        self.logging_config = logging_config or LoggingConfig()

    def get_host_by_name(self, name: str) -> Optional[HostConfig]:
        """Get host configuration by name."""
        for host in self.hosts:
            if host.name == name:
                return host
        return None

    def get_hosts_by_tag(self, tag: str) -> List[HostConfig]:
        """Get all hosts with a specific tag."""
        return [host for host in self.hosts if tag in host.tags]

    def list_host_names(self) -> List[str]:
        """Get list of all host names."""
        return [host.name for host in self.hosts]


def load_config_from_file(config_path: str) -> ServerConfig:
    """Load configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file

    Returns:
        ServerConfig object with loaded configuration

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid YAML
        ValueError: If config file has invalid structure
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    logger.info(f"Loading configuration from: {config_path}")

    with open(path, "r") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML configuration: {e}")
            raise

    if not data:
        logger.warning("Configuration file is empty, using defaults")
        return ServerConfig()

    # Parse hosts
    hosts = []
    if "hosts" in data and isinstance(data["hosts"], list):
        for host_data in data["hosts"]:
            try:
                host = HostConfig(
                    name=host_data.get("name", ""),
                    host=host_data.get("host", ""),
                    username=host_data.get("username", ""),
                    description=host_data.get("description", ""),
                    ssh_key_path=host_data.get("ssh_key_path"),
                    tags=host_data.get("tags", []),
                )
                hosts.append(host)
                logger.debug(f"Loaded host configuration: {host}")
            except Exception as e:
                logger.warning(f"Skipping invalid host configuration: {e}")

    # Parse SSH config
    ssh_config = SSHConfig()
    if "ssh_config" in data:
        ssh_data = data["ssh_config"]
        ssh_config = SSHConfig(
            default_key_path=ssh_data.get("default_key_path"),
            connection_timeout=ssh_data.get("connection_timeout", 30),
            keep_alive=ssh_data.get("keep_alive", True),
            keep_alive_interval=ssh_data.get("keep_alive_interval", 30),
        )

    # Parse allowed log paths
    allowed_log_paths = data.get("allowed_log_paths", [])

    # Parse logging config
    logging_config = LoggingConfig()
    if "logging" in data:
        log_data = data["logging"]
        logging_config = LoggingConfig(
            level=log_data.get("level", "INFO"),
            retention_days=log_data.get("retention_days", 10),
            directory=log_data.get("directory", "/app/logs"),
        )

    config = ServerConfig(
        hosts=hosts,
        ssh_config=ssh_config,
        allowed_log_paths=allowed_log_paths,
        logging_config=logging_config,
    )

    logger.info(
        f"Configuration loaded: {len(hosts)} hosts, "
        f"{len(allowed_log_paths)} allowed log paths"
    )

    return config


def load_config_from_env() -> ServerConfig:
    """Load configuration from environment variables (legacy support).

    Returns:
        ServerConfig object with configuration from environment variables
    """
    logger.info("Loading configuration from environment variables")

    # Parse allowed log paths
    allowed_log_paths = []
    env_paths = os.getenv("LINUX_MCP_ALLOWED_LOG_PATHS", "")
    if env_paths:
        allowed_log_paths = [p.strip() for p in env_paths.split(",") if p.strip()]

    # Parse logging config
    logging_config = LoggingConfig(
        level=os.getenv("LINUX_MCP_LOG_LEVEL", "INFO"),
        retention_days=int(os.getenv("LINUX_MCP_LOG_RETENTION_DAYS", "10")),
        directory=os.getenv("LINUX_MCP_LOG_DIR", str(Path.home() / ".local" / "share" / "linux-mcp-server" / "logs")),
    )

    # Parse SSH config
    ssh_config = SSHConfig(
        default_key_path=os.getenv("LINUX_MCP_SSH_KEY_PATH"),
    )

    return ServerConfig(
        hosts=[],  # No hosts defined in env vars
        ssh_config=ssh_config,
        allowed_log_paths=allowed_log_paths,
        logging_config=logging_config,
    )


def load_config() -> ServerConfig:
    """Load configuration from file or environment variables.

    Priority:
    1. LINUX_MCP_CONFIG_FILE environment variable
    2. /app/config/hosts.yaml (container default)
    3. ./hosts.yaml (local development)
    4. Environment variables (legacy)

    Returns:
        ServerConfig object with loaded configuration
    """
    # Check for explicit config file path
    config_file = os.getenv("LINUX_MCP_CONFIG_FILE")
    if config_file:
        logger.info(f"Using config file from LINUX_MCP_CONFIG_FILE: {config_file}")
        try:
            return load_config_from_file(config_file)
        except Exception as e:
            logger.error(f"Failed to load config from {config_file}: {e}")
            logger.info("Falling back to environment variables")
            return load_config_from_env()

    # Check default container location
    container_config = Path("/app/config/hosts.yaml")
    if container_config.exists():
        logger.info(f"Using container config file: {container_config}")
        try:
            return load_config_from_file(str(container_config))
        except Exception as e:
            logger.warning(f"Failed to load container config: {e}")

    # Check local development location
    local_config = Path("hosts.yaml")
    if local_config.exists():
        logger.info(f"Using local config file: {local_config}")
        try:
            return load_config_from_file(str(local_config))
        except Exception as e:
            logger.warning(f"Failed to load local config: {e}")

    # Fall back to environment variables
    logger.info("No config file found, using environment variables")
    return load_config_from_env()


# Global configuration instance
_config: Optional[ServerConfig] = None


def get_config() -> ServerConfig:
    """Get the global configuration instance.

    Returns:
        ServerConfig object
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> ServerConfig:
    """Reload configuration from source.

    Returns:
        ServerConfig object
    """
    global _config
    _config = load_config()
    return _config

