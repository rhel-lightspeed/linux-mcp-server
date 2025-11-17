"""System information tools."""

import os
import platform

from datetime import datetime

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


class CPUFrequency(BaseModel):
    """CPU frequency information."""

    current: float | None = None
    min: float | None = None
    max: float | None = None


class LoadAverage(BaseModel):
    """Load average information."""

    one_min: float
    five_min: float
    fifteen_min: float


class CPUInfo(BaseModel):
    """CPU information model."""

    cpu_model: str | None = None
    physical_cores: int | None = None
    logical_cores: int | None = None
    frequency_mhz: CPUFrequency | None = None
    load_average: LoadAverage | None = None
    cpu_usage_percent: float | None = None
    per_core_usage: list[float] | None = None
    cpu_details: str | None = None


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
async def get_system_information(  # noqa: C901
    host: Host | None = None,
) -> SystemInfo:
    """
    Get basic system information.
    """
    result = SystemInfo()

    try:
        if host:
            # Remote execution - use Linux commands
            # Hostname
            returncode, stdout, _ = await execute_command(
                ["hostname"],
                host=host,
            )
            if returncode == 0 and stdout:
                result.hostname = stdout.strip()

            # OS Information from /etc/os-release
            returncode, stdout, _ = await execute_command(
                ["cat", "/etc/os-release"],
                host=host,
            )
            if returncode == 0 and stdout:
                os_info = {}
                for line in stdout.split("\n"):
                    line = line.strip()
                    if "=" in line:
                        key, value = line.split("=", 1)
                        os_info[key] = value.strip('"')

                result.operating_system = os_info.get("PRETTY_NAME", "Unknown")
                if "VERSION_ID" in os_info:
                    result.os_version = os_info["VERSION_ID"]

            # Kernel version
            returncode, stdout, _ = await execute_command(
                ["uname", "-r"],
                host=host,
            )
            if returncode == 0 and stdout:
                result.kernel_version = stdout.strip()

            # Architecture
            returncode, stdout, _ = await execute_command(
                ["uname", "-m"],
                host=host,
            )
            if returncode == 0 and stdout:
                result.architecture = stdout.strip()

            # Uptime
            returncode, stdout, _ = await execute_command(
                ["uptime", "-p"],
                host=host,
            )
            if returncode == 0 and stdout:
                result.uptime = stdout.strip()

            # Boot time
            returncode, stdout, _ = await execute_command(
                ["uptime", "-s"],
                host=host,
            )
            if returncode == 0 and stdout:
                result.boot_time = stdout.strip()
        else:
            # Local execution - use psutil and platform
            # Hostname
            result.hostname = platform.node()

            # OS Information
            if os.path.exists("/etc/os-release"):
                os_info = {}
                with open("/etc/os-release") as f:
                    for line in f:
                        line = line.strip()
                        if "=" in line:
                            key, value = line.split("=", 1)
                            os_info[key] = value.strip('"')

                result.operating_system = os_info.get("PRETTY_NAME", "Unknown")
                if "VERSION_ID" in os_info:
                    result.os_version = os_info["VERSION_ID"]
            else:
                result.operating_system = f"{platform.system()} {platform.release()}"

            # Kernel version
            result.kernel_version = platform.release()

            # Architecture
            result.architecture = platform.machine()

            # Uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            result.uptime = f"{days}d {hours}h {minutes}m {seconds}s"
            result.boot_time = boot_time.strftime("%Y-%m-%d %H:%M:%S")

        return result
    except Exception as e:
        raise ToolError(f"Error: {str(e)}") from e


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

    try:
        if host:
            # Remote execution - use Linux commands
            # Get CPU model from /proc/cpuinfo
            returncode, stdout, _ = await execute_command(
                ["grep", "-m", "1", "model name", "/proc/cpuinfo"],
                host=host,
            )
            if returncode == 0 and stdout:
                result.cpu_model = stdout.split(":", 1)[1].strip() if ":" in stdout else stdout.strip()

            # Get CPU core counts from /proc/cpuinfo
            returncode, stdout, _ = await execute_command(
                ["grep", "-c", "^processor", "/proc/cpuinfo"],
                host=host,
            )
            if returncode == 0 and stdout:
                result.logical_cores = int(stdout.strip())

            # Get physical cores (using core id uniqueness)
            returncode, stdout, _ = await execute_command(
                ["grep", "^core id", "/proc/cpuinfo"],
                host=host,
            )
            if returncode == 0 and stdout:
                core_ids = {line.split(":", 1)[1].strip() for line in stdout.strip().split("\n") if ":" in line}
                result.physical_cores = len(core_ids)

            # Get CPU frequency from /proc/cpuinfo
            returncode, stdout, _ = await execute_command(
                ["grep", "-m", "1", "cpu MHz", "/proc/cpuinfo"],
                host=host,
            )
            if returncode == 0 and stdout and ":" in stdout:
                cpu_mhz = float(stdout.split(":", 1)[1].strip())
                result.frequency_mhz = CPUFrequency(current=cpu_mhz)

            # Get load average
            returncode, stdout, _ = await execute_command(
                ["cat", "/proc/loadavg"],
                host=host,
            )
            if returncode == 0 and stdout:
                load_parts = stdout.strip().split()
                if len(load_parts) >= 3:
                    result.load_average = LoadAverage(
                        one_min=float(load_parts[0]), five_min=float(load_parts[1]), fifteen_min=float(load_parts[2])
                    )

            # Get CPU usage using top (one iteration)
            returncode, stdout, _ = await execute_command(
                ["top", "-bn1"],
                host=host,
            )
            if returncode == 0 and stdout:
                for line in stdout.split("\n"):
                    if "Cpu(s):" in line or "%Cpu" in line:
                        result.cpu_details = line.strip()
                        break
        else:
            # Local execution - use psutil
            # CPU count
            result.physical_cores = psutil.cpu_count(logical=False)
            result.logical_cores = psutil.cpu_count(logical=True)

            # CPU frequency
            try:
                cpu_freq = psutil.cpu_freq()
                if cpu_freq:
                    result.frequency_mhz = CPUFrequency(current=cpu_freq.current, min=cpu_freq.min, max=cpu_freq.max)
            except Exception:
                pass  # CPU frequency might not be available

            # CPU usage per core
            cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)
            result.per_core_usage = cpu_percent

            # Overall CPU usage
            result.cpu_usage_percent = psutil.cpu_percent(interval=0.1)

            # Load average
            load_avg = os.getloadavg()
            result.load_average = LoadAverage(one_min=load_avg[0], five_min=load_avg[1], fifteen_min=load_avg[2])

            # Try to get CPU model info from /proc/cpuinfo
            try:
                with open("/proc/cpuinfo") as f:
                    for line in f:
                        if line.startswith("model name"):
                            result.cpu_model = line.split(":")[1].strip()
                            break
            except Exception:
                pass

        return result
    except Exception as e:
        raise ToolError(f"Error: {str(e)}") from e


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
    ram_stats = None
    swap_stats = None

    try:
        if host:
            # Remote execution - use free command
            returncode, stdout, _ = await execute_command(
                ["free", "-b"],
                host=host,
            )

            if returncode == 0 and stdout:
                lines = stdout.strip().split("\n")

                # Parse memory line
                for line in lines:
                    if line.startswith("Mem:"):
                        parts = line.split()
                        if len(parts) >= 7:
                            total = int(parts[1])
                            used = int(parts[2])
                            free = int(parts[3])
                            available = int(parts[6]) if len(parts) > 6 else free
                            percent = (used / total * 100) if total > 0 else 0

                            ram_stats = MemoryStats(
                                total=total, used=used, free=free, available=available, percent=percent
                            )

                    elif line.startswith("Swap:"):
                        parts = line.split()
                        if len(parts) >= 4:
                            total = int(parts[1])
                            used = int(parts[2])
                            free = int(parts[3])
                            percent = (used / total * 100) if total > 0 else 0

                            swap_stats = MemoryStats(total=total, used=used, free=free, percent=percent)
        else:
            # Local execution - use psutil
            # Virtual memory (RAM)
            mem = psutil.virtual_memory()
            ram_stats = MemoryStats(
                total=mem.total,
                used=mem.used,
                free=mem.free,
                available=mem.available,
                percent=mem.percent,
                buffers=getattr(mem, "buffers", None),
                cached=getattr(mem, "cached", None),
            )

            # Swap memory
            swap = psutil.swap_memory()
            swap_stats = MemoryStats(total=swap.total, used=swap.used, free=swap.free, percent=swap.percent)

        return MemoryInfo(ram=ram_stats, swap=swap_stats)
    except Exception as e:
        raise ToolError(f"Error: {str(e)}") from e


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
