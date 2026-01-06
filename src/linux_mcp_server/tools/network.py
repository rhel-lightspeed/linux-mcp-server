"""Network diagnostic tools."""

from mcp.types import ToolAnnotations

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.commands import get_command
from linux_mcp_server.formatters import format_listening_ports
from linux_mcp_server.formatters import format_network_connections
from linux_mcp_server.formatters import format_network_interfaces
from linux_mcp_server.parsers import parse_ip_brief
from linux_mcp_server.parsers import parse_proc_net_dev
from linux_mcp_server.parsers import parse_ss_connections
from linux_mcp_server.parsers import parse_ss_listening
from linux_mcp_server.server import mcp
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host


@mcp.tool(
    title="Get network interfaces",
    description="Get detailed information about network interfaces including address and traffic statistics.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_network_interfaces(
    host: Host | None = None,
) -> str:
    """Get network interface information.

    Retrieves all network interfaces with their operational state, IP addresses,
    and traffic statistics (bytes/packets sent/received, errors, dropped packets).
    """
    try:
        interfaces = {}
        stats = {}

        # Get brief interface info
        brief_cmd = get_command("network_interfaces", "brief")
        returncode, stdout, _ = await brief_cmd.run(host=host)

        if returncode == 0 and stdout:
            interfaces = parse_ip_brief(stdout)

        # Get network statistics from /proc/net/dev
        stats_cmd = get_command("network_interfaces", "stats")
        returncode, stdout, _ = await stats_cmd.run(host=host)

        if returncode == 0 and stdout:
            stats = parse_proc_net_dev(stdout)

        return format_network_interfaces(interfaces, stats)
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
    """Get active network connections.

    Retrieves all established and pending network connections including protocol,
    state, local/remote addresses and ports, and associated process information.
    """
    try:
        cmd = get_command("network_connections")

        returncode, stdout, stderr = await cmd.run(host=host)

        if returncode == 0 and stdout:
            connections = parse_ss_connections(stdout)
            return format_network_connections(connections)
        return f"Error getting network connections: return code {returncode}, stderr: {stderr}"
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
    """Get listening ports.

    Retrieves all ports with services actively listening for connections,
    including protocol (TCP/UDP), bind address, port number, and process name.
    """
    try:
        cmd = get_command("listening_ports")

        returncode, stdout, stderr = await cmd.run(host=host)

        if returncode == 0 and stdout:
            ports = parse_ss_listening(stdout)
            return format_listening_ports(ports)
        return f"Error getting listening ports: return code {returncode}, stderr: {stderr}"
    except Exception as e:
        return f"Error getting listening ports: {str(e)}"
