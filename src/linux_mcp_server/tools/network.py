"""Network diagnostic tools."""

import socket

import psutil

from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.server import mcp
from linux_mcp_server.utils import format_bytes
from linux_mcp_server.utils import is_ipv6_link_local
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host


def _get_pid_info(pid: int | None) -> str:
    """Get process name for a PID, returning 'N/A' or 'pid/name' format."""
    if not pid:
        return "N/A"
    try:
        proc = psutil.Process(pid)
        return f"{pid}/{proc.name()}"
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return str(pid)


def _format_filtered_total(label: str, displayed: int, total: int) -> str:
    """Format total count with optional filtered count message."""
    filtered = total - displayed
    if filtered > 0:
        return f"\n\nTotal {label}: {displayed} (filtered {filtered} link-local)"
    return f"\n\nTotal {label}: {displayed}"


@mcp.tool(
    title="Get network interfaces",
    description="Get detailed information about network interfaces including address and traffic statistics.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_network_interfaces(  # noqa: C901
    host: Host | None = None,
) -> str:
    """
    Get network interface information.
    """
    try:
        if host:
            # Remote execution - use ip command
            info = []
            info.append("=== Network Interfaces ===\n")

            # Get interface info
            returncode, stdout, _ = await execute_command(
                ["ip", "-brief", "address"],
                host=host,
            )

            if returncode == 0 and stdout:
                info.append(stdout)

            # Get detailed interface info
            returncode, stdout, _ = await execute_command(
                ["ip", "address"],
                host=host,
            )

            if returncode == 0 and stdout:
                info.append("\n=== Detailed Interface Information ===")
                info.append(stdout)

            # Get network statistics using netstat or ss
            returncode, stdout, _ = await execute_command(
                ["cat", "/proc/net/dev"],
                host=host,
            )

            if returncode == 0 and stdout:
                info.append("\n=== Network I/O Statistics ===")
                info.append(stdout)

            return "\n".join(info)
        else:
            # Local execution - use psutil
            info = []
            info.append("=== Network Interfaces ===\n")

            # Get network interface addresses
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()

            for interface, addrs in sorted(net_if_addrs.items()):
                info.append(f"\n{interface}:")

                # Get interface stats
                if interface in net_if_stats:
                    stats = net_if_stats[interface]
                    status = "UP" if stats.isup else "DOWN"
                    info.append(f"  Status: {status}")
                    info.append(f"  Speed: {stats.speed} Mbps")
                    info.append(f"  MTU: {stats.mtu}")

                # Get addresses
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        info.append(f"  IPv4 Address: {addr.address}")
                        if addr.netmask:
                            info.append(f"    Netmask: {addr.netmask}")
                        if addr.broadcast:
                            info.append(f"    Broadcast: {addr.broadcast}")
                    elif addr.family == socket.AF_INET6:
                        # Skip link-local addresses (fe80::/10)
                        if is_ipv6_link_local(addr.address):
                            continue
                        info.append(f"  IPv6 Address: {addr.address}")
                        if addr.netmask:
                            info.append(f"    Netmask: {addr.netmask}")
                    elif addr.family == psutil.AF_LINK:
                        info.append(f"  MAC Address: {addr.address}")

            # Network I/O statistics
            net_io = psutil.net_io_counters()
            info.append("\n\n=== Network I/O Statistics (total) ===")
            info.append(f"Bytes Sent: {format_bytes(net_io.bytes_sent)}")
            info.append(f"Bytes Received: {format_bytes(net_io.bytes_recv)}")
            info.append(f"Packets Sent: {net_io.packets_sent}")
            info.append(f"Packets Received: {net_io.packets_recv}")
            info.append(f"Errors In: {net_io.errin}")
            info.append(f"Errors Out: {net_io.errout}")
            info.append(f"Drops In: {net_io.dropin}")
            info.append(f"Drops Out: {net_io.dropout}")

            return "\n".join(info)
    except ToolError:
        raise
    except Exception as e:
        return f"Error getting network interface information: {str(e)}"


@mcp.tool(
    title="Get network connections",
    description="Get detailed information about active network connections.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_network_connections(
    host: Host | None = None,
) -> str:
    """
    Get active network connections.
    """
    try:
        if host:
            # Remote execution - use ss or netstat command
            # Try ss first (modern tool)
            returncode, stdout, _ = await execute_command(
                ["ss", "-tunap"],
                host=host,
            )

            if returncode == 0 and stdout:
                info = []
                info.append("=== Active Network Connections ===\n")
                info.append(stdout)

                # Count connections
                lines = stdout.strip().split("\n")
                info.append(f"\n\nTotal connections: {len(lines) - 1}")  # -1 for header

                return "\n".join(info)
            else:
                # Fallback to netstat
                returncode, stdout, _ = await execute_command(
                    ["netstat", "-tunap"],
                    host=host,
                )

                if returncode == 0 and stdout:
                    info = []
                    info.append("=== Active Network Connections ===\n")
                    info.append(stdout)
                    return "\n".join(info)
                else:
                    return "Error: Neither ss nor netstat command available on remote host"
        else:
            # Local execution - use psutil
            info = []
            info.append("=== Active Network Connections ===\n")
            info.append(f"{'Proto':<8} {'Local Address':<30} {'Remote Address':<30} {'Status':<15} {'PID/Program'}")
            info.append("-" * 110)

            # Get all network connections
            connections = psutil.net_connections(kind="inet")
            total_count = len(connections)
            displayed_count = 0

            for conn in connections:
                proto = "TCP" if conn.type == socket.SOCK_STREAM else "UDP"

                # Skip connections using link-local addresses
                if conn.laddr and is_ipv6_link_local(conn.laddr.ip):
                    continue
                if conn.raddr and is_ipv6_link_local(conn.raddr.ip):
                    continue

                local_addr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "N/A"
                remote_addr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "N/A"
                status = conn.status if conn.status else "N/A"

                info.append(f"{proto:<8} {local_addr:<30} {remote_addr:<30} {status:<15} {_get_pid_info(conn.pid)}")
                displayed_count += 1

            info.append(_format_filtered_total("connections", displayed_count, total_count))

            return "\n".join(info)
    except ToolError:
        raise
    except psutil.AccessDenied:
        return "Permission denied. This tool requires elevated privileges to view all network connections."
    except Exception as e:
        return f"Error getting network connections: {str(e)}"


@mcp.tool(
    title="Get listening ports",
    description="Get details on listening port, protocols, and services.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_listening_ports(
    host: Host | None = None,
) -> str:
    """
    Get listening ports.
    """
    try:
        if host:
            # Remote execution - use ss or netstat command
            # Try ss first (modern tool)
            returncode, stdout, _ = await execute_command(
                ["ss", "-tulnp"],
                host=host,
            )

            if returncode == 0 and stdout:
                info = []
                info.append("=== Listening Ports ===\n")
                info.append(stdout)

                # Count listening ports
                lines = stdout.strip().split("\n")
                info.append(f"\n\nTotal listening ports: {len(lines) - 1}")  # -1 for header

                return "\n".join(info)
            else:
                # Fallback to netstat
                returncode, stdout, _ = await execute_command(
                    ["netstat", "-tulnp"],
                    host=host,
                )

                if returncode == 0 and stdout:
                    info = []
                    info.append("=== Listening Ports ===\n")
                    info.append(stdout)
                    return "\n".join(info)
                else:
                    return "Error: Neither ss nor netstat command available on remote host"
        else:
            # Local execution - use psutil
            info = []
            info.append("=== Listening Ports ===\n")
            info.append(f"{'Proto':<8} {'Local Address':<30} {'Status':<15} {'PID/Program'}")
            info.append("-" * 80)

            # Get connections in LISTEN state
            connections = psutil.net_connections(kind="inet")
            listening = [c for c in connections if c.status == "LISTEN" or c.type == socket.SOCK_DGRAM]
            total_count = len(listening)
            displayed_count = 0

            for conn in listening:
                # Skip listening on link-local addresses
                if conn.laddr and is_ipv6_link_local(conn.laddr.ip):
                    continue

                proto = "TCP" if conn.type == socket.SOCK_STREAM else "UDP"
                local_addr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "N/A"
                status = conn.status if conn.status else "LISTENING"

                info.append(f"{proto:<8} {local_addr:<30} {status:<15} {_get_pid_info(conn.pid)}")
                displayed_count += 1

            info.append(_format_filtered_total("listening ports", displayed_count, total_count))

            return "\n".join(info)
    except ToolError:
        raise
    except psutil.AccessDenied:
        return "Permission denied. This tool requires elevated privileges to view all listening ports."
    except Exception as e:
        return f"Error getting listening ports: {str(e)}"
