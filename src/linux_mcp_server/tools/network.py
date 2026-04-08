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
from linux_mcp_server.utils import StrEnum
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.validation import is_successful_output


class RouteFamily(StrEnum):
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    ALL = "all"


def _format_route_output(stdout: str, label: str) -> str:
    lines = [f"=== IP Route Table ({label}) ===\n"]
    lines.append(stdout.strip())
    return "\n".join(lines)


@mcp.tool(
    title="Get network interfaces",
    description="Get detailed information about network interfaces including address and traffic statistics.",
    tags={"connectivity", "interfaces", "network"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_network_interfaces(
    host: Host = None,
) -> str:
    """Get network interface information.

    Retrieves all network interfaces with their operational state, IP addresses,
    and traffic statistics (bytes/packets sent/received, errors, dropped packets).
    """
    interfaces = {}
    stats = {}

    # Get brief interface info
    brief_cmd = get_command("network_interfaces", "brief")
    returncode, stdout, _ = await brief_cmd.run(host=host)

    if is_successful_output(returncode, stdout):
        interfaces = parse_ip_brief(stdout)

    # Get network statistics from /proc/net/dev
    stats_cmd = get_command("network_interfaces", "stats")
    returncode, stdout, _ = await stats_cmd.run(host=host)

    if is_successful_output(returncode, stdout):
        stats = parse_proc_net_dev(stdout)

    return format_network_interfaces(interfaces, stats)


@mcp.tool(
    title="Get network connections",
    description="Get detailed information about active network connections.",
    tags={"connections", "connectivity", "network"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_network_connections(
    host: Host = None,
) -> str:
    """Get active network connections.

    Retrieves all established and pending network connections including protocol,
    state, local/remote addresses and ports, and associated process information.
    """
    cmd = get_command("network_connections")

    returncode, stdout, stderr = await cmd.run(host=host)

    if is_successful_output(returncode, stdout):
        connections = parse_ss_connections(stdout)
        return format_network_connections(connections)
    return f"Error getting network connections: return code {returncode}, stderr: {stderr}"


@mcp.tool(
    title="Get listening ports",
    description="Get details on listening port, protocols, and services.",
    tags={"connectivity", "network", "ports"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_listening_ports(
    host: Host = None,
) -> str:
    """Get listening ports.

    Retrieves all ports with services actively listening for connections,
    including protocol (TCP/UDP), bind address, port number, and process name.
    """
    cmd = get_command("listening_ports")

    returncode, stdout, stderr = await cmd.run(host=host)

    if is_successful_output(returncode, stdout):
        ports = parse_ss_listening(stdout)
        return format_listening_ports(ports)
    return f"Error getting listening ports: return code {returncode}, stderr: {stderr}"


@mcp.tool(
    title="Get IP route table",
    description="Get IPv4/IPv6 route entries using ip route.",
    tags={"network", "routing"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_ip_route_table(
    family: RouteFamily = RouteFamily.IPV4,
    host: Host = None,
) -> str:
    """Get routing table entries.

    Retrieves routing table entries via the ip command for IPv4, IPv6, or both.
    """
    if family == RouteFamily.ALL:
        outputs: list[str] = []
        for subcommand, label in (("ipv4", "IPv4"), ("ipv6", "IPv6")):
            cmd = get_command("ip_route", subcommand)
            returncode, stdout, stderr = await cmd.run(host=host)
            if is_successful_output(returncode, stdout):
                outputs.append(_format_route_output(stdout, label))
            else:
                outputs.append(
                    f"Error getting {label} routes: return code {returncode}, stderr: {stderr}",
                )
        return "\n\n".join(outputs)

    cmd = get_command("ip_route", family.value)
    returncode, stdout, stderr = await cmd.run(host=host)

    if is_successful_output(returncode, stdout):
        label = "IPv4" if family == RouteFamily.IPV4 else "IPv6"
        return _format_route_output(stdout, label)
    return f"Error getting IP routes: return code {returncode}, stderr: {stderr}"
