"""System information tools."""

import typing as t

from collections.abc import Callable

import psutil

from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.server import mcp
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host


# Pydantic Models for structured output
class SystemInfo(BaseModel):
    """System information model."""

    hostname: str | None = None
    operating_system: str | None = None
    os_version: str | None = None
    kernel_version: str | None = None
    architecture: str | None = None
    uptime: str | None = None
    boot_time: str | None = None


class LoadAverage(BaseModel):
    """Load average information."""

    one_min: float
    five_min: float
    fifteen_min: float


class CPUInfo(BaseModel):
    """CPU information model."""

    cpu_model: str | None = None
    logical_cores: int | None = None
    physical_sockets: int | None = None
    physical_cores_per_processor: int | None = None
    frequency_mhz: float | None = None
    load_average: LoadAverage | None = None
    cpu_usage: str | None = None


class MemoryStats(BaseModel):
    """Memory statistics model."""

    total: int
    used: int
    free: int
    percent: float
    available: int | None = None
    buffers: int | None = None
    cached: int | None = None


class MemoryInfo(BaseModel):
    """Memory information model."""

    ram: MemoryStats | None = None
    swap: MemoryStats | None = None


class DiskPartition(BaseModel):
    """Disk partition information."""

    device: str
    mountpoint: str
    size: int
    used: int
    free: int
    percent: float
    filesystem: str | None = None


class DiskIOStats(BaseModel):
    """Disk I/O statistics."""

    read_bytes: int
    write_bytes: int
    read_count: int
    write_count: int


class DiskUsage(BaseModel):
    """Disk usage information model."""

    partitions: list[DiskPartition]
    io_stats: DiskIOStats | None = None


class HardwareInfo(BaseModel):
    """Hardware information model."""

    cpu_architecture: str | None = None
    pci_devices: list[str] = Field(default_factory=list)
    pci_device_count: int | None = None
    usb_devices: str | None = None
    memory_hardware: str | None = None


@mcp.tool(
    title="Get system information",
    description="Get basic system information such as operating system, distribution, kernel version, uptime, and last boot time.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_system_information(
    host: Host | None = None,
) -> SystemInfo:
    """
    Get basic system information.
    """
    result = SystemInfo()

    class SystemInfoAttribute(BaseModel):
        """System information attribute."""

        names: list[str]
        command: list[str]
        parser: Callable[[str], t.Any]

    attributes = [
        SystemInfoAttribute(names=["hostname"], command=["hostname"], parser=lambda x: x.strip()),
        SystemInfoAttribute(
            names=["operating_system", "os_version"],
            command=["cat", "/etc/os-release"],
            parser=lambda x: {
                line.strip().split("=", 1)[0]: line.strip().split("=", 1)[1] for line in x.split("\n") if "=" in line
            },
        ),
        SystemInfoAttribute(
            names=["kernel_version", "architecture"],
            command=["uname", "-r", "-m"],
            parser=lambda x: (
                lambda parts: {"kernel_version": parts[0], "architecture": parts[1] if len(parts) > 1 else None}
            )(x.strip().split(None, 1)),
        ),
        SystemInfoAttribute(names=["uptime"], command=["uptime", "-p"], parser=lambda x: x.strip()),
        SystemInfoAttribute(names=["boot_time"], command=["uptime", "-s"], parser=lambda x: x.strip()),
    ]

    for attribute in attributes:
        try:
            returncode, stdout, _ = await execute_command(
                attribute.command,
                host=host,
            )
        except ValueError or ConnectionError as e:
            raise ToolError(f"Error: {str(e)}") from e

        if returncode == 0 and stdout:
            parsed_output = attribute.parser(stdout)
            match attribute.names:
                case ["hostname"]:
                    result.hostname = parsed_output
                case ["operating_system", "os_version"]:
                    result.operating_system = parsed_output["PRETTY_NAME"]
                    result.os_version = parsed_output["VERSION_ID"]
                case ["kernel_version", "architecture"]:
                    result.kernel_version = parsed_output["kernel_version"]
                    result.architecture = parsed_output["architecture"]
                case ["uptime"]:
                    result.uptime = parsed_output
                case ["boot_time"]:
                    result.boot_time = parsed_output
                case _:
                    raise ToolError(f"Unknown attribute: {attribute.names}")
    return result


@mcp.tool(
    title="Get CPU information",
    description="Get CPU information.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_cpu_information(
    host: Host | None = None,
) -> CPUInfo:
    """
    Get CPU information.
    """
    result = CPUInfo()

    class CPUInfoAttribute(BaseModel):
        """CPU information attribute."""

        names: list[str]
        command: list[str]
        parser: Callable[[str], t.Any]

    attributes = [
        CPUInfoAttribute(
            names=["cpu_model"],
            command=["cat", "/proc/cpuinfo"],
            parser=lambda x: next(
                (line.split(":", 1)[1].strip() for line in x.strip().split("\n") if line.startswith("model name")), ""
            ),
        ),
        CPUInfoAttribute(
            names=["logical_cores"],
            command=["cat", "/proc/cpuinfo"],
            # count the number of processor entries to get number of logical cores
            parser=lambda x: sum(1 for line in x.strip().split("\n") if line.startswith("processor")),
        ),
        CPUInfoAttribute(
            names=["physical_sockets"],
            command=["cat", "/proc/cpuinfo"],
            parser=lambda x: len(set(line for line in x.strip().split("\n") if line.startswith("physical id"))),
        ),
        CPUInfoAttribute(
            names=["physical_cores_per_processor"],
            command=["cat", "/proc/cpuinfo"],
            parser=lambda x: next(
                (int(line.split(":", 1)[1].strip()) for line in x.strip().split("\n") if line.startswith("cpu cores")),
                0,
            ),
        ),
        CPUInfoAttribute(
            names=["frequency_mhz"],
            command=["cat", "/proc/cpuinfo"],
            parser=lambda x: float(
                next(
                    (line.split(":", 1)[1].strip() for line in x.strip().split("\n") if line.startswith("cpu MHz")), "0"
                )
            ),
        ),
        CPUInfoAttribute(
            names=["load_average"],
            command=["cat", "/proc/loadavg"],
            parser=lambda x: {
                "one_min": float(x.strip().split()[0]),
                "five_min": float(x.strip().split()[1]),
                "fifteen_min": float(x.strip().split()[2]),
            },
        ),
        CPUInfoAttribute(
            names=["cpu_usage"],
            command=["top", "-bn1"],
            parser=lambda x: x.strip() if "Cpu(s):" in x or "%Cpu" in x else None,
        ),
    ]

    for attribute in attributes:
        try:
            returncode, stdout, _ = await execute_command(
                attribute.command,
                host=host,
            )
        except ValueError or ConnectionError as e:
            raise ToolError(f"Error: {str(e)}") from e

        if returncode == 0 and stdout:
            parsed_output = attribute.parser(stdout)
            match attribute.names:
                case ["cpu_model"]:
                    result.cpu_model = parsed_output
                case ["logical_cores"]:
                    result.logical_cores = parsed_output
                case ["physical_sockets"]:
                    result.physical_sockets = parsed_output
                case ["physical_cores_per_processor"]:
                    result.physical_cores_per_processor = parsed_output
                case ["frequency_mhz"]:
                    result.frequency_mhz = parsed_output
                case ["load_average"]:
                    result.load_average = parsed_output
                case ["cpu_usage"]:
                    result.cpu_usage = parsed_output
                case _:
                    raise ToolError(f"Unknown attribute: {attribute.names}")
    return result


@mcp.tool(
    title="Get memory information",
    description="Get detailed memory including physical and swap.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_memory_information(
    host: Host | None = None,
) -> MemoryInfo:
    """
    Get memory information.
    """
    ram_stats: MemoryStats | None = None
    swap_stats: MemoryStats | None = None

    class MemoryStatsAttribute(BaseModel):
        """Memory statistics attribute."""

        names: list[str]
        command: list[str]
        parser: Callable[[str], t.Any]

    def parse_free_output(output: str) -> dict[str, MemoryStats]:
        """Parse the output of 'free -b' command into memory statistics."""
        lines = output.strip().split("\n")
        result = {}

        for line in lines:
            if line.startswith("Mem:"):
                parts = line.split()
                if len(parts) >= 7:
                    total = int(parts[1])
                    used = int(parts[2])
                    free = int(parts[3])
                    # parts[4] is shared memory (not used in MemoryStats)
                    buff_cache = int(parts[5]) if len(parts) > 5 else 0
                    available = int(parts[6]) if len(parts) > 6 else free
                    percent = (used / total * 100) if total > 0 else 0

                    result["ram"] = MemoryStats(
                        total=total,
                        used=used,
                        free=free,
                        available=available,
                        percent=percent,
                        buffers=buff_cache,  # buff/cache combined
                    )

            elif line.startswith("Swap:"):
                parts = line.split()
                if len(parts) >= 4:
                    total = int(parts[1])
                    used = int(parts[2])
                    free = int(parts[3])
                    percent = (used / total * 100) if total > 0 else 0

                    result["swap"] = MemoryStats(
                        total=total,
                        used=used,
                        free=free,
                        percent=percent,
                    )

        return result

    attributes = [
        MemoryStatsAttribute(names=["ram", "swap"], command=["free", "-b"], parser=parse_free_output),
    ]

    for attribute in attributes:
        try:
            returncode, stdout, _ = await execute_command(
                attribute.command,
                host=host,
            )
        except ValueError or ConnectionError as e:
            raise ToolError(f"Error: {str(e)}") from e

        if returncode == 0 and stdout:
            parsed_output = attribute.parser(stdout)
            match attribute.names:
                case ["ram", "swap"]:
                    ram_stats = parsed_output["ram"]
                    swap_stats = parsed_output["swap"]
                case _:
                    raise ToolError(f"Unknown attribute: {attribute.names}")

    return MemoryInfo(ram=ram_stats, swap=swap_stats)


@mcp.tool(
    title="Get disk usage",
    description="Get detailed disk space information including size, mount points, and utilization..",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_disk_usage(
    host: Host | None = None,
) -> DiskUsage:
    """
    Get disk usage information.
    """
    partitions = []
    io_stats = None

    try:
        if host:
            # Remote execution - use df command to get bytes
            returncode, stdout, _ = await execute_command(
                ["df", "-B1"],
                host=host,
            )

            if returncode == 0 and stdout:
                lines = stdout.strip().split("\n")
                # Skip header line
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) >= 6:
                        try:
                            device = parts[0]
                            size = int(parts[1])
                            used = int(parts[2])
                            free = int(parts[3])
                            percent_str = parts[4].rstrip("%")
                            percent = float(percent_str) if percent_str else 0.0
                            mountpoint = parts[5]

                            partitions.append(
                                DiskPartition(
                                    device=device,
                                    mountpoint=mountpoint,
                                    size=size,
                                    used=used,
                                    free=free,
                                    percent=percent,
                                )
                            )
                        except (ValueError, IndexError):
                            # Skip malformed lines
                            continue
        else:
            # Local execution - use psutil
            # Get all disk partitions
            disk_partitions = psutil.disk_partitions(all=False)

            for partition in disk_partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    partitions.append(
                        DiskPartition(
                            device=partition.device,
                            mountpoint=partition.mountpoint,
                            size=usage.total,
                            used=usage.used,
                            free=usage.free,
                            percent=usage.percent,
                            filesystem=partition.fstype,
                        )
                    )
                except PermissionError:
                    # Skip partitions we can't access
                    continue
                except Exception:
                    # Skip partitions with errors
                    continue

            # Disk I/O statistics
            try:
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    io_stats = DiskIOStats(
                        read_bytes=disk_io.read_bytes,
                        write_bytes=disk_io.write_bytes,
                        read_count=disk_io.read_count,
                        write_count=disk_io.write_count,
                    )
            except Exception:
                pass  # Disk I/O might not be available

        return DiskUsage(partitions=partitions, io_stats=io_stats)
    except Exception as e:
        raise ToolError(f"Error: {str(e)}") from e


@mcp.tool(
    title="Get hardware information",
    description="Get hardware information such as CPU details, PCI devices, USB devices, and hardware information from DMI.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
async def get_hardware_information(
    host: Host | None = None,
) -> HardwareInfo:
    """
    Get hardware information.
    """
    result = HardwareInfo()

    try:
        # Try lscpu for CPU info
        try:
            returncode, stdout, stderr = await execute_command(
                ["lscpu"],
                host=host,
            )

            if returncode == 0:
                result.cpu_architecture = stdout
        except FileNotFoundError:
            result.cpu_architecture = "lscpu command not available"

        # Try lspci for PCI devices
        try:
            returncode, stdout, stderr = await execute_command(
                ["lspci"],
                host=host,
            )

            if returncode == 0:
                pci_lines = stdout.strip().split("\n")
                # Store first 50 devices to avoid overwhelming output
                result.pci_devices = pci_lines[:50]
                result.pci_device_count = len(pci_lines)
        except FileNotFoundError:
            result.pci_devices = ["lspci command not available"]

        # Try lsusb for USB devices
        try:
            returncode, stdout, stderr = await execute_command(
                ["lsusb"],
                host=host,
            )

            if returncode == 0:
                result.usb_devices = stdout
        except FileNotFoundError:
            result.usb_devices = "lsusb command not available"

        # Memory hardware info from dmidecode (requires root)
        try:
            returncode, stdout, stderr = await execute_command(
                ["dmidecode", "-t", "memory"],
                host=host,
            )

            if returncode == 0:
                result.memory_hardware = stdout
            elif "Permission denied" in stderr:
                result.memory_hardware = "Requires root privileges (dmidecode)"
        except FileNotFoundError:
            result.memory_hardware = "dmidecode command not available"

        return result
    except Exception as e:
        raise ToolError(f"Error: {str(e)}") from e
