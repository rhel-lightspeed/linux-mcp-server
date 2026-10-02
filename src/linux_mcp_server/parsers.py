"""Shared output parsers for command results.

This module provides functions to parse raw command output into
structured data that can be used by formatters.
"""

import csv
import io
import re
import zoneinfo

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from datetime import tzinfo
from pathlib import Path

from linux_mcp_server.models import CpuInfo
from linux_mcp_server.models import ListeningPort
from linux_mcp_server.models import MemoryInfo
from linux_mcp_server.models import NetworkConnection
from linux_mcp_server.models import NetworkInterface
from linux_mcp_server.models import NodeEntry
from linux_mcp_server.models import PCPSample
from linux_mcp_server.models import PCPTimeRange
from linux_mcp_server.models import ProcessInfo
from linux_mcp_server.models import SwapInfo
from linux_mcp_server.models import SystemInfo
from linux_mcp_server.models import SystemMemory


def parse_ss_connections(stdout: str) -> list[NetworkConnection]:
    """Parse ss -tunap output into NetworkConnection objects.

    Args:
        stdout: Raw output from ss -tunap command.

    Returns:
        List of NetworkConnection objects.
    """
    connections = []
    lines = stdout.strip().split("\n")

    # Skip header line
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 5:
            continue

        # ss output format: Netid State Recv-Q Send-Q Local Address:Port Peer Address:Port Process
        protocol = parts[0].upper()
        state = parts[1] if protocol == "TCP" else "UNCONN"

        # Parse local address
        local = parts[4] if len(parts) > 4 else ""
        if ":" in local:
            local_addr, local_port = local.rsplit(":", 1)
        else:
            local_addr, local_port = local, ""

        # Parse remote address
        remote = parts[5] if len(parts) > 5 else ""
        if ":" in remote:
            remote_addr, remote_port = remote.rsplit(":", 1)
        else:
            remote_addr, remote_port = remote, ""

        # Parse process info (last column if present)
        process = ""
        if len(parts) > 6:
            process = " ".join(parts[6:])

        connections.append(
            NetworkConnection(
                protocol=protocol,
                state=state,
                local_address=local_addr,
                local_port=local_port,
                remote_address=remote_addr,
                remote_port=remote_port,
                process=process,
            )
        )

    return connections


def parse_ss_listening(stdout: str) -> list[ListeningPort]:
    """Parse ss -tulnp output into ListeningPort objects.

    Args:
        stdout: Raw output from ss -tulnp command.

    Returns:
        List of ListeningPort objects.
    """
    ports = []
    lines = stdout.strip().split("\n")

    # Skip header line
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 5:
            continue

        protocol = parts[0].upper()

        # Parse local address
        local = parts[4] if len(parts) > 4 else ""
        if ":" in local:
            local_addr, local_port = local.rsplit(":", 1)
        else:
            local_addr, local_port = local, ""

        # Parse process info
        process = ""
        if len(parts) > 6:
            process = " ".join(parts[6:])

        ports.append(
            ListeningPort(
                protocol=protocol,
                local_address=local_addr,
                local_port=local_port,
                process=process,
            )
        )

    return ports


def parse_ps_output(stdout: str) -> list[ProcessInfo]:
    """Parse ps aux output into ProcessInfo objects.

    Args:
        stdout: Raw output from ps aux command.

    Returns:
        List of ProcessInfo objects.
    """
    processes = []
    lines = stdout.strip().split("\n")

    # Skip header line
    for line in lines[1:]:
        parts = line.split(None, 10)  # Split into max 11 parts
        if len(parts) < 11:
            continue

        try:
            processes.append(
                ProcessInfo(
                    user=parts[0],
                    pid=int(parts[1]),
                    cpu_percent=float(parts[2]),
                    mem_percent=float(parts[3]),
                    vsz=int(parts[4]),
                    rss=int(parts[5]),
                    tty=parts[6],
                    stat=parts[7],
                    start=parts[8],
                    time=parts[9],
                    command=parts[10] if len(parts) > 10 else "",
                )
            )
        except ValueError:
            # Silently skip invalid process lines
            continue

    return processes


def parse_os_release(stdout: str) -> dict[str, str]:
    """Parse /etc/os-release content into key-value pairs.

    Args:
        stdout: Raw content of /etc/os-release file.

    Returns:
        Dictionary of key-value pairs.
    """
    result = {}
    for line in stdout.strip().split("\n"):
        line = line.strip()
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value.strip('"')
    return result


def parse_free_output(stdout: str) -> SystemMemory:
    """Parse free -b -w output into SystemMemory object.

    Args:
        stdout: Raw output from free -b -w command.

    Returns:
        SystemMemory object containing RAM and swap info.
    """
    ram = MemoryInfo(total=0, used=0, free=0)
    swap = None

    lines = stdout.strip().split("\n")
    for line in lines:
        if line.startswith("Mem:"):
            parts = line.split()
            if len(parts) >= 4:
                ram = MemoryInfo(
                    total=int(parts[1]),
                    used=int(parts[2]),
                    free=int(parts[3]),
                    shared=int(parts[4]) if len(parts) > 4 else 0,
                    buffers=int(parts[5]) if len(parts) > 5 else 0,
                    cached=int(parts[6]) if len(parts) > 6 else 0,
                    available=int(parts[7]) if len(parts) > 7 else int(parts[3]),
                )
        elif line.startswith("Swap:"):
            parts = line.split()
            if len(parts) >= 4:
                swap = SwapInfo(
                    total=int(parts[1]),
                    used=int(parts[2]),
                    free=int(parts[3]),
                )

    return SystemMemory(ram=ram, swap=swap)


def parse_proc_net_dev(stdout: str) -> dict[str, NetworkInterface]:
    """Parse /proc/net/dev content into NetworkInterface objects.

    Args:
        stdout: Raw content of /proc/net/dev file.

    Returns:
        Dictionary mapping interface names to NetworkInterface objects.
    """
    interfaces: dict[str, NetworkInterface] = {}
    lines = stdout.strip().split("\n")

    # Skip first two header lines
    for line in lines[2:]:
        if ":" not in line:
            continue

        name, stats = line.split(":", 1)
        name = name.strip()
        parts = stats.split()

        if len(parts) >= 16:
            interfaces[name] = NetworkInterface(
                name=name,
                rx_bytes=int(parts[0]),
                rx_packets=int(parts[1]),
                rx_errors=int(parts[2]),
                rx_dropped=int(parts[3]),
                tx_bytes=int(parts[8]),
                tx_packets=int(parts[9]),
                tx_errors=int(parts[10]),
                tx_dropped=int(parts[11]),
            )

    return interfaces


def parse_ip_brief(stdout: str) -> dict[str, NetworkInterface]:
    """Parse ip -brief address output.

    Args:
        stdout: Raw output from ip -brief address command.

    Returns:
        Dictionary mapping interface names to NetworkInterface objects.
    """
    interfaces: dict[str, NetworkInterface] = {}
    lines = stdout.strip().split("\n")

    for line in lines:
        parts = line.split()
        if len(parts) >= 2:
            name = parts[0]
            status = parts[1]
            addresses = parts[2:] if len(parts) > 2 else []

            interfaces[name] = NetworkInterface(
                name=name,
                status=status,
                addresses=addresses,
            )

    return interfaces


def parse_system_info(results: dict[str, str]) -> SystemInfo:
    """Parse system info command results into SystemInfo object.

    Args:
        results: Dictionary of command name to output.

    Returns:
        SystemInfo object.
    """
    hostname = ""
    os_name = ""
    os_version = ""
    kernel = ""
    arch = ""
    uptime = ""
    boot_time = ""

    if "hostname" in results:
        hostname = results["hostname"].strip()

    if "os_release" in results:
        os_data = parse_os_release(results["os_release"])
        os_name = os_data.get("PRETTY_NAME", "Unknown")
        os_version = os_data.get("VERSION_ID", "")

    if "kernel" in results:
        kernel = results["kernel"].strip()

    if "arch" in results:
        arch = results["arch"].strip()

    if "uptime" in results:
        uptime = results["uptime"].strip()

    if "boot_time" in results:
        boot_time = results["boot_time"].strip()

    return SystemInfo(
        hostname=hostname,
        os_name=os_name,
        os_version=os_version,
        kernel=kernel,
        arch=arch,
        uptime=uptime,
        boot_time=boot_time,
    )


def _parse_pcp_archive_timestamp(line: str) -> datetime | None:
    """Extract epoch timestamp from pmdumplog -l output"""
    match = re.search(r"\s[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,9})?\s+[0-9]{4}\s+([0-9]+)\s*$", line)
    if match is None:
        return None

    try:
        return datetime.fromtimestamp(int(match[1]), tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def parse_pcp_archive_ranges(stdout: str, timezone_name: str, grace_period_hours: int = 1) -> list[PCPTimeRange]:
    """Parse pmdumplog -l -x -x -x output into time ranges.

    Args:
        stdout: Raw output from pmdumplog -l -x -x -x.
        timezone_name: Target system's timezone.
        grace_period_hours: Maximum gap in hours to merge adjacent ranges.

    Returns:
        List of merged PCPTimeRange objects with times in target timezone.
    """
    if grace_period_hours < 0:
        raise ValueError("grace_period_hours must be nonnegative")

    try:
        tz = zoneinfo.ZoneInfo(timezone_name)
    except KeyError as e:
        raise ValueError(f"Invalid timezone: {timezone_name}") from e

    ranges: list[tuple[datetime, datetime]] = []
    start: datetime | None = None

    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith(("--- archive ", "Log Label")):
            start = None
        elif line.startswith("commencing "):
            start = _parse_pcp_archive_timestamp(line)
        elif line.startswith("ending "):
            end = _parse_pcp_archive_timestamp(line)
            if start is not None and end is not None and start <= end:
                ranges.append((start, end))
            start = None

    if not ranges:
        return []

    ranges.sort()
    grace_period = timedelta(hours=grace_period_hours)
    collapsed: list[tuple[datetime, datetime]] = []
    current_start, current_end = ranges[0]

    for next_start, next_end in ranges[1:]:
        if next_start - current_end <= grace_period:
            current_end = max(current_end, next_end)
        else:
            collapsed.append((current_start, current_end))
            current_start, current_end = next_start, next_end

    collapsed.append((current_start, current_end))
    return [PCPTimeRange(start=start.astimezone(tz), end=end.astimezone(tz)) for start, end in collapsed]


def parse_pmrep_csv(stdout: str, tz: tzinfo | None = None) -> list[PCPSample]:
    """Parse pmrep -o csv output into samples, with UTC timestamps rendered in ``tz``.

    Raises:
        ValueError: If ``tz`` is given and a timestamp cannot be read.
    """
    rows = [row for row in csv.reader(io.StringIO(stdout)) if row]
    if len(rows) < 2:
        return []

    metric_names = rows[0][1:]
    samples = []

    for row in rows[1:]:
        metrics = {name: value for name, value in zip(metric_names, row[1:]) if value != ""}
        if metrics:
            samples.append(PCPSample(time=_localize_pmrep_time(row[0], tz), metrics=metrics))

    return samples


def _localize_pmrep_time(stamp: str, tz: tzinfo | None) -> str:
    """Convert a UTC pmrep timestamp into an RFC-3339 string in ``tz``."""
    if tz is None:
        return stamp
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError(f"Unrecognised timestamp in pmrep output: {stamp!r}") from e
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(tz).isoformat()


def _parse_load_avg(load_avg_str: str) -> tuple[float, float, float]:
    """Parse load average string into tuple of floats."""
    parts = load_avg_str.strip().split()
    if len(parts) >= 3:
        try:
            return float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            pass
    return 0.0, 0.0, 0.0


def _count_physical_cores(physical_cores_str: str) -> int:
    """Count unique physical core IDs."""
    core_ids = set()
    for line in physical_cores_str.strip().split("\n"):
        if ":" in line:
            core_id = line.split(":", 1)[1].strip()
            core_ids.add(core_id)
    return len(core_ids)


def _extract_cpu_line(top_snapshot: str) -> str:
    """Extract CPU usage line from top snapshot."""
    for line in top_snapshot.split("\n"):
        if "Cpu(s):" in line or "%Cpu" in line:
            return line.strip()
    return ""


def parse_cpu_info(results: dict[str, str]) -> CpuInfo:
    """Parse CPU info command results into CpuInfo object.

    Args:
        results: Dictionary of command name to output.

    Returns:
        CpuInfo object.
    """
    model = ""
    logical_cores = 0
    physical_cores = 0
    frequency_mhz = 0.0
    load_avg_1m, load_avg_5m, load_avg_15m = 0.0, 0.0, 0.0
    cpu_line = ""

    if "model" in results and ":" in results["model"]:
        model = results["model"].split(":", 1)[1].strip()

    if "logical_cores" in results:
        try:
            logical_cores = int(results["logical_cores"].strip())
        except ValueError:
            pass

    if "physical_cores" in results:
        physical_cores = _count_physical_cores(results["physical_cores"])

    if "frequency" in results and ":" in results["frequency"]:
        try:
            frequency_mhz = float(results["frequency"].split(":", 1)[1].strip())
        except ValueError:
            pass

    if "load_avg" in results:
        load_avg_1m, load_avg_5m, load_avg_15m = _parse_load_avg(results["load_avg"])

    if "top_snapshot" in results:
        cpu_line = _extract_cpu_line(results["top_snapshot"])

    return CpuInfo(
        model=model,
        logical_cores=logical_cores,
        physical_cores=physical_cores,
        frequency_mhz=frequency_mhz,
        load_avg_1m=load_avg_1m,
        load_avg_5m=load_avg_5m,
        load_avg_15m=load_avg_15m,
        cpu_line=cpu_line,
    )


def parse_proc_status(stdout: str) -> dict[str, str]:
    """Parse /proc/{pid}/status content into key-value pairs.

    Args:
        stdout: Raw content of /proc/{pid}/status file.

    Returns:
        Dictionary of relevant fields.
    """
    result = {}
    relevant_fields = {
        "Name",
        "State",
        "Tgid",
        "Pid",
        "PPid",
        "Threads",
        "VmPeak",
        "VmSize",
        "VmRSS",
    }

    for line in stdout.strip().split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            if key in relevant_fields:
                result[key] = value.strip()

    return result


def parse_service_count(stdout: str) -> int:
    """Count services from systemctl list-units output.

    Args:
        stdout: Raw output from systemctl list-units command.

    Returns:
        Number of services found.
    """
    count = 0
    for line in stdout.split("\n"):
        if ".service" in line:
            count += 1
    return count


def _parse_timestamp_with_offset(value: str) -> datetime:
    """Parse a timestamp with the target's offset to match target-local log entries."""
    timestamp, offset = value.split(":", 1)
    tz = datetime.strptime(offset, "%z").tzinfo
    return datetime.fromtimestamp(float(timestamp), tz=tz)


def parse_directory_listing(
    stdout: str,
    sort_by: str,
) -> list[NodeEntry]:
    """Parse directory listing output into NodeEntry objects.

    Args:
        stdout: Raw output from find/du command.
        sort_by: Sort field - "size", "name", or "modified".

    Returns:
        List of NodeEntry objects.
    """
    entries = []
    lines = stdout.strip().split("\n")
    last = len(lines)

    for idx, line in enumerate(lines, 1):
        if not line.strip():
            continue

        if sort_by == "size":
            # Format: SIZE\tNAME (from du -b)
            size, path = line.split("\t", 1)
            size = int(size)
            path = Path(path)
            # Omit the last line since it containers the parent directory
            if idx < last:
                entries.append(NodeEntry(size=size, name=path.name))
        elif sort_by == "modified":
            # Format: TIMESTAMP:OFFSET\tNAME (from find -printf "%T@:%Tz\t%f\n")
            parts = line.split("\t", 1)
            if len(parts) == 2:
                try:
                    modified = _parse_timestamp_with_offset(parts[0])
                    name = parts[1]
                    entries.append(NodeEntry(modified=modified, name=name))
                except (ValueError, OverflowError, OSError):
                    continue
        else:
            # Format: NAME (from find -printf "%f\n")
            entries.append(NodeEntry(name=line.strip()))

    return entries


def parse_file_listing(
    stdout: str,
    sort_by: str,
) -> list[NodeEntry]:
    """Parse file listing output into NodeEntry objects.

    Args:
        stdout: Raw output from find command.
        sort_by: Sort field - "size", "name", or "modified".

    Returns:
        List of NodeEntry objects.
    """
    entries = []
    lines = stdout.strip().split("\n")

    for line in lines:
        if not line.strip():
            continue

        if sort_by == "size":
            # Format: SIZE\tNAME (from find -printf "%s\t%f\n")
            parts = line.split("\t", 1)
            if len(parts) == 2:
                try:
                    size = int(parts[0])
                    name = parts[1]
                    entries.append(NodeEntry(size=size, name=name))
                except ValueError:
                    continue
        elif sort_by == "modified":
            # Format: TIMESTAMP:OFFSET\tNAME (from find -printf "%T@:%Tz\t%f\n")
            parts = line.split("\t", 1)
            if len(parts) == 2:
                try:
                    modified = _parse_timestamp_with_offset(parts[0])
                    name = parts[1]
                    entries.append(NodeEntry(modified=modified, name=name))
                except (ValueError, OverflowError, OSError):
                    continue
        else:
            # Format: NAME (from find -printf "%f\n")
            entries.append(NodeEntry(name=line.strip()))

    return entries
