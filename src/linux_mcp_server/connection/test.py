import logging

from pathlib import Path

from linux_mcp_server.config import CONFIG


logger = logging.getLogger("linux-mcp-server")


def discover_ssh_key() -> str | None:
    """
    Discover SSH private key for authentication.

    Checks in order:
    1. LINUX_MCP_SSH_KEY_PATH environment variable
    2. Default locations: ~/.ssh/id_ed25519, ~/.ssh/id_rsa, ~/.ssh/id_ecdsa

    Returns:
        Path to SSH private key if found, None otherwise.
    """
    logger.debug("Discovering SSH key for authentication")

    env_key = CONFIG.ssh_key_path
    if env_key:
        logger.debug(f"Checking SSH key from environment: {env_key}")
        key_path = Path(env_key)
        if key_path.exists() and key_path.is_file():
            logger.info(f"Using SSH key from environment: {env_key}")
            return str(key_path)
        else:
            logger.warning(f"SSH key specified in LINUX_MCP_SSH_KEY_PATH not found: {env_key}")
            return None

    # Check default locations (prefer modern algorithms)
    if CONFIG.search_for_ssh_key:
        home = Path.home()
        default_keys = [
            home / ".ssh" / "id_ed25519",
            home / ".ssh" / "id_ecdsa",
            home / ".ssh" / "id_rsa",
        ]

        logger.debug(f"Checking default SSH key locations: {[str(k) for k in default_keys]}")

        for key_path in default_keys:
            if key_path.exists() and key_path.is_file():
                logger.info(f"Using SSH key: {key_path}")
                return str(key_path)

        logger.warning("No SSH private key found in default locations")

    logger.debug("Not providing an SSH key")
