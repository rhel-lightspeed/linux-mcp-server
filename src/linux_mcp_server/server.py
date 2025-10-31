"""Core MCP server for Linux diagnostics using FastMCP."""

import logging

from mcp.server.fastmcp import FastMCP

from .tools import logs
from .tools import network
from .tools import processes
from .tools import services
from .tools import storage
from .tools import system_info


logger = logging.getLogger(__name__)


# Initialize FastMCP server
mcp = FastMCP("linux-diagnostics")


# System Information Tools
@mcp.tool()
async def get_system_info(host: str | None = None, username: str | None = None) -> str:
    """Get basic system information including OS version, kernel, hostname, and uptime.

    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await system_info.get_system_info(host=host, username=username)


@mcp.tool()
async def get_cpu_info(host: str | None = None, username: str | None = None) -> str:
    """Get CPU information and load averages.

    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await system_info.get_cpu_info(host=host, username=username)


@mcp.tool()
async def get_memory_info(host: str | None = None, username: str | None = None) -> str:
    """Get memory usage including RAM and swap details.

    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await system_info.get_memory_info(host=host, username=username)


@mcp.tool()
async def get_disk_usage(host: str | None = None, username: str | None = None) -> str:
    """Get filesystem usage and mount points.

    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await system_info.get_disk_usage(host=host, username=username)


@mcp.tool()
async def get_hardware_info(host: str | None = None, username: str | None = None) -> str:
    """Get hardware information including CPU architecture, PCI devices, USB devices, and memory hardware.

    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await system_info.get_hardware_info(host=host, username=username)


# Service Management Tools
@mcp.tool()
async def list_services(host: str | None = None, username: str | None = None) -> str:
    """List all systemd services with their current status.

    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await services.list_services(host=host, username=username)


@mcp.tool()
async def get_service_status(service_name: str, host: str | None = None, username: str | None = None) -> str:
    """Get detailed status of a specific systemd service.

    Args:
        service_name: Name of the service
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await services.get_service_status(service_name=service_name, host=host, username=username)


@mcp.tool()
async def get_service_logs(
    service_name: str, lines: int = 50, host: str | None = None, username: str | None = None
) -> str:
    """Get recent logs for a specific systemd service.

    Args:
        service_name: Name of the service
        lines: Number of log lines to retrieve (default: 50)
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await services.get_service_logs(service_name=service_name, lines=lines, host=host, username=username)


# Process Management Tools
@mcp.tool()
async def list_processes(host: str | None = None, username: str | None = None) -> str:
    """List running processes with CPU and memory usage.

    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await processes.list_processes(host=host, username=username)


@mcp.tool()
async def get_process_info(
    pid: int,
    host: str | None = None,
    username: str | None = None,
) -> str:
    """Get detailed information about a specific process.

    Args:
        pid: Process ID
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await processes.get_process_info(pid=pid, host=host, username=username)


# Log and Audit Tools
@mcp.tool()
async def get_journal_logs(
    unit: str | None = None,
    priority: str | None = None,
    since: str | None = None,
    lines: int = 100,
    host: str | None = None,
    username: str | None = None,
) -> str:
    """Query systemd journal logs with optional filters.

    Args:
        unit: Filter by systemd unit
        priority: Filter by priority (emerg, alert, crit, err, warning, notice, info, debug)
        since: Show entries since specified time (e.g., '1 hour ago', '2024-01-01')
        lines: Number of log lines to retrieve (default: 100)
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await logs.get_journal_logs(
        unit=unit, priority=priority, since=since, lines=lines, host=host, username=username
    )


@mcp.tool()
async def get_audit_logs(lines: int = 100, host: str | None = None, username: str | None = None) -> str:
    """Get audit logs if available.

    Args:
        lines: Number of log lines to retrieve (default: 100)
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await logs.get_audit_logs(lines=lines, host=host, username=username)


@mcp.tool()
async def read_log_file(log_path: str, lines: int = 100, host: str | None = None, username: str | None = None) -> str:
    """Read a specific log file (whitelist-controlled via LINUX_MCP_ALLOWED_LOG_PATHS).

    Args:
        log_path: Path to the log file
        lines: Number of lines to retrieve from the end (default: 100)
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await logs.read_log_file(log_path=log_path, lines=lines, host=host, username=username)


# Network Tools
@mcp.tool()
async def get_network_interfaces(host: str | None = None, username: str | None = None) -> str:
    """Get network interface information including IP addresses.

    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await network.get_network_interfaces(host=host, username=username)


@mcp.tool()
async def get_network_connections(host: str | None = None, username: str | None = None) -> str:
    """Get active network connections.

    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await network.get_network_connections(host=host, username=username)


@mcp.tool()
async def get_listening_ports(host: str | None = None, username: str | None = None) -> str:
    """Get ports that are listening on the system.

    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await network.get_listening_ports(host=host, username=username)


# Storage Tools
@mcp.tool()
async def list_block_devices(host: str | None = None, username: str | None = None) -> str:
    """List block devices and partitions.

    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await storage.list_block_devices(host=host, username=username)


@mcp.tool()
async def list_directories_by_size(
    path: str,
    top_n: int,
    host: str | None = None,
    username: str | None = None,
) -> str:
    """List directories sorted by size (largest first). Uses efficient Linux du command.

    Args:
        path: Directory path to analyze
        top_n: Number of top largest directories to return (1-1000)
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await storage.list_directories_by_size(path=path, top_n=top_n, host=host, username=username)


@mcp.tool()
async def list_directories_by_name(
    path: str,
    reverse: bool = False,
    host: str | None = None,
    username: str | None = None,
) -> str:
    """List directories sorted alphabetically by name. Uses efficient Linux find command.

    Args:
        path: Directory path to analyze
        reverse: Sort in reverse order (Z-A) (default: False)
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await storage.list_directories_by_name(path=path, reverse=reverse, host=host, username=username)


@mcp.tool()
async def list_directories_by_modified_date(
    path: str,
    newest_first: bool = True,
    host: str | None = None,
    username: str | None = None,
) -> str:
    """List directories sorted by modification date. Uses efficient Linux find command.

    Args:
        path: Directory path to analyze
        newest_first: Show newest first (default: True)
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await storage.list_directories_by_modified_date(
        path=path, newest_first=newest_first, host=host, username=username
    )


def main():
    """Run the MCP server using FastMCP."""
    logger.info("Initialized linux-diagnostics v0.1.0")
    logger.info("Starting FastMCP server")

    # Run the FastMCP server (it creates its own event loop)
    mcp.run()
