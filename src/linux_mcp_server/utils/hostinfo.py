"""Helpers for discovering properties of a target host."""

from linux_mcp_server.commands import get_command
from linux_mcp_server.utils.types import Host


class TimezoneDiscoveryError(RuntimeError):
    """Raised when the timezone command fails or returns no timezone."""


async def discover_timezone_name(host: Host) -> str:
    """Read the target host's timezone name, raising on lookup failure."""
    returncode, stdout, stderr = await get_command("host_info", "timezone").run(host=host)

    if returncode != 0:
        raise TimezoneDiscoveryError(
            f"Unable to determine the target system's timezone on {host}: "
            f"command exited with status {returncode}: {stderr.strip()}"
        )

    name = stdout.strip()
    if not name:
        raise TimezoneDiscoveryError(
            f"Unable to determine the target system's timezone on {host}: command returned empty output."
        )

    return name
