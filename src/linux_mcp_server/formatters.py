"""Shared output formatters for tool results.

This module provides functions to format parsed data into
human-readable strings for tool output.
"""

from linux_mcp_server.models import ListeningPort
from linux_mcp_server.models import ProcessInfo


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
