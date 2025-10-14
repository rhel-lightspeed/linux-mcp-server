"""Core MCP server for Linux diagnostics using FastMCP."""

import logging
import time
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .audit import log_tool_call, log_tool_complete
from .tools import system_info, services, processes, logs, network, storage


logger = logging.getLogger(__name__)


# Initialize FastMCP server
mcp = FastMCP("linux-diagnostics")


# System Information Tools
@mcp.tool()
async def get_system_info(host: Optional[str] = None, username: Optional[str] = None) -> str:
    """Get basic system information including OS version, kernel, hostname, and uptime.
    
    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("get_system_info", system_info.get_system_info, 
                               host=host, username=username)


@mcp.tool()
async def get_cpu_info(host: Optional[str] = None, username: Optional[str] = None) -> str:
    """Get CPU information and load averages.
    
    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("get_cpu_info", system_info.get_cpu_info,
                               host=host, username=username)


@mcp.tool()
async def get_memory_info(host: Optional[str] = None, username: Optional[str] = None) -> str:
    """Get memory usage including RAM and swap details.
    
    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("get_memory_info", system_info.get_memory_info,
                               host=host, username=username)


@mcp.tool()
async def get_disk_usage(host: Optional[str] = None, username: Optional[str] = None) -> str:
    """Get filesystem usage and mount points.
    
    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("get_disk_usage", system_info.get_disk_usage,
                               host=host, username=username)


@mcp.tool()
async def get_hardware_info(host: Optional[str] = None, username: Optional[str] = None) -> str:
    """Get hardware information including CPU architecture, PCI devices, USB devices, and memory hardware.
    
    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("get_hardware_info", system_info.get_hardware_info,
                               host=host, username=username)


# Service Management Tools
@mcp.tool()
async def list_services(host: Optional[str] = None, username: Optional[str] = None) -> str:
    """List all systemd services with their current status.
    
    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("list_services", services.list_services,
                               host=host, username=username)


@mcp.tool()
async def get_service_status(service_name: str, host: Optional[str] = None, 
                             username: Optional[str] = None) -> str:
    """Get detailed status of a specific systemd service.
    
    Args:
        service_name: Name of the service
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("get_service_status", services.get_service_status,
                               service_name=service_name, host=host, username=username)


@mcp.tool()
async def get_service_logs(service_name: str, lines: int = 50, 
                          host: Optional[str] = None, username: Optional[str] = None) -> str:
    """Get recent logs for a specific systemd service.
    
    Args:
        service_name: Name of the service
        lines: Number of log lines to retrieve (default: 50)
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("get_service_logs", services.get_service_logs,
                               service_name=service_name, lines=lines, 
                               host=host, username=username)


# Process Management Tools
@mcp.tool()
async def list_processes(host: Optional[str] = None, username: Optional[str] = None) -> str:
    """List running processes with CPU and memory usage.
    
    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("list_processes", processes.list_processes,
                               host=host, username=username)


@mcp.tool()
async def get_process_info(pid: int, host: Optional[str] = None, 
                          username: Optional[str] = None) -> str:
    """Get detailed information about a specific process.
    
    Args:
        pid: Process ID
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("get_process_info", processes.get_process_info,
                               pid=pid, host=host, username=username)


# Log and Audit Tools
@mcp.tool()
async def get_journal_logs(unit: Optional[str] = None, priority: Optional[str] = None,
                          since: Optional[str] = None, lines: int = 100,
                          host: Optional[str] = None, username: Optional[str] = None) -> str:
    """Query systemd journal logs with optional filters.
    
    Args:
        unit: Filter by systemd unit
        priority: Filter by priority (emerg, alert, crit, err, warning, notice, info, debug)
        since: Show entries since specified time (e.g., '1 hour ago', '2024-01-01')
        lines: Number of log lines to retrieve (default: 100)
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("get_journal_logs", logs.get_journal_logs,
                               unit=unit, priority=priority, since=since, lines=lines,
                               host=host, username=username)


@mcp.tool()
async def get_audit_logs(lines: int = 100, host: Optional[str] = None, 
                        username: Optional[str] = None) -> str:
    """Get audit logs if available.
    
    Args:
        lines: Number of log lines to retrieve (default: 100)
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("get_audit_logs", logs.get_audit_logs,
                               lines=lines, host=host, username=username)


@mcp.tool()
async def read_log_file(log_path: str, lines: int = 100,
                       host: Optional[str] = None, username: Optional[str] = None) -> str:
    """Read a specific log file (whitelist-controlled via LINUX_MCP_ALLOWED_LOG_PATHS).
    
    Args:
        log_path: Path to the log file
        lines: Number of lines to retrieve from the end (default: 100)
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("read_log_file", logs.read_log_file,
                               log_path=log_path, lines=lines, host=host, username=username)


# Network Tools
@mcp.tool()
async def get_network_interfaces(host: Optional[str] = None, username: Optional[str] = None) -> str:
    """Get network interface information including IP addresses.
    
    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("get_network_interfaces", network.get_network_interfaces,
                               host=host, username=username)


@mcp.tool()
async def get_network_connections(host: Optional[str] = None, username: Optional[str] = None) -> str:
    """Get active network connections.
    
    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("get_network_connections", network.get_network_connections,
                               host=host, username=username)


@mcp.tool()
async def get_listening_ports(host: Optional[str] = None, username: Optional[str] = None) -> str:
    """Get ports that are listening on the system.
    
    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("get_listening_ports", network.get_listening_ports,
                               host=host, username=username)


# Storage Tools
@mcp.tool()
async def list_block_devices(host: Optional[str] = None, username: Optional[str] = None) -> str:
    """List block devices and partitions.
    
    Args:
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("list_block_devices", storage.list_block_devices,
                               host=host, username=username)


@mcp.tool()
async def list_directories_by_size(path: str, top_n: int,
                                  host: Optional[str] = None, username: Optional[str] = None) -> str:
    """List directories sorted by size (largest first). Uses efficient Linux du command.
    
    Args:
        path: Directory path to analyze
        top_n: Number of top largest directories to return (1-1000)
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("list_directories_by_size", storage.list_directories_by_size,
                               path=path, top_n=top_n, host=host, username=username)


@mcp.tool()
async def list_directories_by_name(path: str, reverse: bool = False,
                                  host: Optional[str] = None, username: Optional[str] = None) -> str:
    """List directories sorted alphabetically by name. Uses efficient Linux find command.
    
    Args:
        path: Directory path to analyze
        reverse: Sort in reverse order (Z-A) (default: False)
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("list_directories_by_name", storage.list_directories_by_name,
                               path=path, reverse=reverse, host=host, username=username)


@mcp.tool()
async def list_directories_by_modified_date(path: str, newest_first: bool = True,
                                           host: Optional[str] = None, username: Optional[str] = None) -> str:
    """List directories sorted by modification date. Uses efficient Linux find command.
    
    Args:
        path: Directory path to analyze
        newest_first: Show newest first (default: True)
        host: Remote host to connect to via SSH (optional, executes locally if not provided)
        username: SSH username for remote host (required if host is provided)
    """
    return await _execute_tool("list_directories_by_modified_date", 
                               storage.list_directories_by_modified_date,
                               path=path, newest_first=newest_first, host=host, username=username)


async def _execute_tool(tool_name: str, handler, **kwargs):
    """Execute a tool with logging and error handling.
    
    Args:
        tool_name: Name of the tool being executed
        handler: The tool function to call
        **kwargs: Arguments to pass to the tool function
    """
    # Log tool invocation
    log_tool_call(tool_name, kwargs)
    
    start_time = time.time()
    
    try:
        result = await handler(**kwargs)
        duration = time.time() - start_time
        log_tool_complete(tool_name, status="success", duration=duration)
        return result
        
    except Exception as e:
        duration = time.time() - start_time
        log_tool_complete(tool_name, status="error", duration=duration, error=str(e))
        raise


def main():
    """Run the MCP server using FastMCP."""
    logger.info(f"Initialized linux-diagnostics v0.1.0")
    logger.info("Starting FastMCP server")
    
    # Run the FastMCP server (it creates its own event loop)
    mcp.run()

