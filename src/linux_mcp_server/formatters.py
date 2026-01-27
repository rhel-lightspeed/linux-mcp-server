"""Shared output formatters for tool results.

This module provides functions to format parsed data into
human-readable strings for tool output.
"""

from datetime import datetime
from pathlib import Path

from linux_mcp_server.models import NodeEntry
from linux_mcp_server.utils import format_bytes
from linux_mcp_server.utils.types import ListeningPort
from linux_mcp_server.utils.types import NetworkConnection
from linux_mcp_server.utils.types import NetworkInterface
from linux_mcp_server.utils.types import ProcessInfo


def format_network_connections(
    connections: list[NetworkConnection],
    header: str = "=== Active Network Connections ===\n",
) -> str:
    """Format network connections into a readable string.

    Args:
        connections: List of NetworkConnection objects.
        header: Header text for the output.

    Returns:
        Formatted string representation.
    """
    lines = [header]
    lines.append(f"{'Proto':<8} {'Local Address':<30} {'Remote Address':<30} {'Status':<15} {'PID/Program'}")
    lines.append("-" * 110)

    for conn in connections:
        local = f"{conn.local_address}:{conn.local_port}"
        remote = f"{conn.remote_address}:{conn.remote_port}" if conn.remote_address else "N/A"
        lines.append(f"{conn.protocol:<8} {local:<30} {remote:<30} {conn.state:<15} {conn.process}")

    lines.append(f"\n\nTotal connections: {len(connections)}")
    return "\n".join(lines)


def format_listening_ports(
    ports: list[ListeningPort],
    header: str = "=== Listening Ports ===\n",
) -> str:
    """Format listening ports into a readable string.

    Args:
        ports: List of ListeningPort objects.
        header: Header text for the output.

    Returns:
        Formatted string representation.
    """
    lines = [header]
    lines.append(f"{'Proto':<8} {'Local Address':<30} {'Status':<15} {'PID/Program'}")
    lines.append("-" * 80)

    for port in ports:
        local = f"{port.local_address}:{port.local_port}"
        lines.append(f"{port.protocol:<8} {local:<30} {'LISTEN':<15} {port.process}")

    lines.append(f"\n\nTotal listening ports: {len(ports)}")
    return "\n".join(lines)


def format_process_list(
    processes: list[ProcessInfo],
    max_display: int | None = None,
    header: str = "=== Running Processes ===\n",
) -> str:
    """Format process list into a readable string.

    Args:
        processes: List of ProcessInfo objects.
        max_display: Maximum number of processes to display.
        header: Header text for the output.

    Returns:
        Formatted string representation.
    """
    lines = [header]
    lines.append(f"{'PID':<8} {'User':<12} {'CPU%':<8} {'Memory%':<10} {'Status':<12} {'Name':<30} {'Command'}")
    lines.append("-" * 120)

    displayed = processes[:max_display] if max_display is not None else processes
    for proc in displayed:
        # Truncate username if too long
        username = proc.user
        if len(username) > 12:
            username = username[:9] + "..."

        # Truncate command if too long
        cmd = proc.command
        if len(cmd) > 40:
            cmd = cmd[:37] + "..."

        lines.append(
            f"{proc.pid:<8} {username:<12} {proc.cpu_percent:<8} {proc.mem_percent:<10} "
            f"{proc.stat:<12} {proc.command[:30]:<30} {cmd}"
        )

    lines.append(f"\n\nTotal processes: {len(processes)}")
    if max_display is not None and len(processes) > max_display:
        lines.append(f"Showing: First {max_display} processes")

    return "\n".join(lines)


def format_network_interfaces(
    interfaces: dict[str, NetworkInterface],
    stats: dict[str, NetworkInterface] | None = None,
) -> str:
    """Format network interface information into a readable string.

    Args:
        interfaces: Dictionary of interface name to NetworkInterface objects.
        stats: Optional dictionary of interface statistics.

    Returns:
        Formatted string representation.
    """
    lines = ["=== Network Interfaces ===\n"]

    for name, iface in sorted(interfaces.items()):
        lines.append(f"\n{name}:")
        if iface.status:
            lines.append(f"  Status: {iface.status}")
        for addr in iface.addresses:
            lines.append(f"  Address: {addr}")

        # Add stats if available
        if stats and name in stats:
            stat = stats[name]
            lines.append(f"  RX: {format_bytes(stat.rx_bytes)} ({stat.rx_packets} packets)")
            lines.append(f"  TX: {format_bytes(stat.tx_bytes)} ({stat.tx_packets} packets)")
            if stat.rx_errors or stat.tx_errors:
                lines.append(f"  Errors: RX={stat.rx_errors}, TX={stat.tx_errors}")
            if stat.rx_dropped or stat.tx_dropped:
                lines.append(f"  Dropped: RX={stat.rx_dropped}, TX={stat.tx_dropped}")

    return "\n".join(lines)


def format_process_detail(
    ps_output: str,
    proc_status: dict[str, str] | None = None,
    pid: int | None = None,
) -> str:
    """Format detailed process information.

    Args:
        ps_output: Raw output from ps command for the process.
        proc_status: Parsed /proc/{pid}/status content.
        pid: Process ID for the header.

    Returns:
        Formatted string representation.
    """
    lines = []

    if pid:
        lines.append(f"=== Process Information for PID {pid} ===\n")

    lines.append(ps_output.strip())

    if proc_status:
        lines.append("\n=== Detailed Status (/proc) ===")
        for key, value in proc_status.items():
            lines.append(f"{key}: {value}")

    return "\n".join(lines)


def format_services_list(stdout: str, running_count: int | None = None) -> str:
    """Format service list output.

    Args:
        stdout: Raw output from systemctl list-units.
        running_count: Optional count of running services.

    Returns:
        Formatted string representation.
    """
    lines = ["=== System Services ===\n"]
    lines.append(stdout)

    if running_count is not None:
        lines.append(f"\n\nSummary: {running_count} services currently running")

    return "\n".join(lines)


def format_service_status(stdout: str, service_name: str) -> str:
    """Format service status output.

    Args:
        stdout: Raw output from systemctl status.
        service_name: Name of the service.

    Returns:
        Formatted string representation.
    """
    lines = [f"=== Status of {service_name} ===\n"]
    lines.append(stdout)
    return "\n".join(lines)


def format_service_logs(stdout: str, service_name: str, lines_count: int) -> str:
    """Format service logs output.

    Args:
        stdout: Raw output from journalctl.
        service_name: Name of the service.
        lines_count: Number of log lines requested.

    Returns:
        Formatted string representation.
    """
    lines = [f"=== Last {lines_count} log entries for {service_name} ===\n"]
    lines.append(stdout)
    return "\n".join(lines)


def format_journal_logs(
    stdout: str,
    lines_count: int,
    unit: str | None = None,
    priority: str | None = None,
    since: str | None = None,
    transport: str | None = None,
) -> str:
    """Format journal logs output.

    Args:
        stdout: Raw output from journalctl.
        lines_count: Number of log lines.
        unit: Optional unit filter.
        priority: Optional priority filter.
        since: Optional time filter.
        transport: Optional transport filter (e.g., 'audit', 'kernel').

    Returns:
        Formatted string representation.
    """
    filters = []
    if unit:
        filters.append(f"unit={unit}")
    if priority:
        filters.append(f"priority={priority}")
    if since:
        filters.append(f"since={since}")

    log_type = f"{transport.title()} Logs" if transport else "Journal Logs"
    filter_str = f", {', '.join(filters)}" if filters else (", no filters" if not transport else "")
    header = f"=== {log_type} (last {lines_count} entries{filter_str}) ===\n"

    lines = [header]
    lines.append(stdout)
    return "\n".join(lines)


def format_log_file(stdout: str, log_path: Path, lines_count: int) -> str:
    """Format log file output.

    Args:
        stdout: Raw content from log file.
        log_path: Path to the log file.
        lines_count: Number of lines read.

    Returns:
        Formatted string representation.
    """
    lines = [f"=== Log File: {log_path} (last {lines_count} lines) ===\n"]
    lines.append(stdout)
    return "\n".join(lines)


def format_disk_usage(stdout: str, disk_io: str | None = None) -> str:
    """Format disk usage output.

    Args:
        stdout: Raw output from df command.
        disk_io: Optional disk I/O statistics.

    Returns:
        Formatted string representation.
    """
    lines = ["=== Filesystem Usage ===\n"]
    lines.append(stdout)

    if disk_io:
        lines.append("\n=== Disk I/O Statistics (since boot) ===")
        lines.append(disk_io)

    return "\n".join(lines)


def format_hardware_info(results: dict[str, str]) -> str:
    """Format hardware information output.

    Args:
        results: Dictionary of command name to output.

    Returns:
        Formatted string representation.
    """
    lines = ["=== Hardware Information ===\n"]

    if "lscpu" in results and results["lscpu"]:
        lines.append("=== CPU Architecture (lscpu) ===")
        lines.append(results["lscpu"])

    if "lspci" in results and results["lspci"]:
        pci_lines = results["lspci"].strip().split("\n")
        lines.append("\n=== PCI Devices ===")
        # Show first 50 devices
        for line in pci_lines[:50]:
            lines.append(line)
        if len(pci_lines) > 50:
            lines.append(f"\n... and {len(pci_lines) - 50} more PCI devices")

    if "lsusb" in results and results["lsusb"]:
        lines.append("\n\n=== USB Devices ===")
        lines.append(results["lsusb"])

    if len(lines) == 1:  # Only header
        lines.append("No hardware information tools available.")

    return "\n".join(lines)


def format_file_listing(
    entries: list[NodeEntry],
    path: str | Path,
    sort_by: str,
    reverse: bool = False,
) -> str:
    """Format file listing into a readable string.

    Args:
        entries: List of NodeEntry objects.
        path: Path that was listed.
        sort_by: Sort field used.
        reverse: Whether the sort was reversed.

    Returns:
        Formatted string representation.
    """
    lines = [f"=== Files in {path} ===\n"]

    # Sort entries
    if sort_by == "size":
        sorted_entries = sorted(entries, key=lambda e: e.size, reverse=reverse)
    elif sort_by == "modified":
        sorted_entries = sorted(entries, key=lambda e: e.modified, reverse=reverse)
    else:
        sorted_entries = sorted(entries, key=lambda e: e.name.lower(), reverse=reverse)

    for entry in sorted_entries:
        if sort_by == "size":
            lines.append(f"{format_bytes(entry.size):>12}  {entry.name}")
        elif sort_by == "modified":
            dt = datetime.fromtimestamp(entry.modified)
            lines.append(f"{dt.strftime('%Y-%m-%d %H:%M:%S')}  {entry.name}")
        else:
            lines.append(f"  {entry.name}")

    lines.append(f"\nTotal files: {len(entries)}")
    return "\n".join(lines)
