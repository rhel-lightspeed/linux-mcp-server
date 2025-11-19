"""System information tools."""

import typing as t

from collections.abc import Callable

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


class PCIDevice(BaseModel):
    """PCI device information."""

    address: str
    vendor_id: str | None = None
    device_id: str | None = None
    class_id: str | None = None
    description: str | None = None


class USBDevice(BaseModel):
    """USB device information."""

    bus: str
    device: str
    vendor_id: str | None = None
    product_id: str | None = None
    description: str | None = None
    manufacturer: str | None = None


class DeviceInfo(BaseModel):
    """Device information model for PCI and USB devices."""

    pci_devices: list[PCIDevice] = Field(default_factory=list)
    pci_device_count: int = 0
    usb_devices: list[USBDevice] = Field(default_factory=list)
    usb_device_count: int = 0


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


def parse_df_output(output: str) -> list[DiskPartition]:
    """Parse the output of 'df -B1' command into disk partitions."""
    lines = output.strip().split("\n")
    result = []

    # Skip header line
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 6:
            device = parts[0]
            size = int(parts[1])
            used = int(parts[2])
            free = int(parts[3])
            percent_str = parts[4].rstrip("%")
            percent = float(percent_str) if percent_str else 0.0
            mountpoint = parts[5]

            result.append(
                DiskPartition(
                    device=device,
                    mountpoint=mountpoint,
                    size=size,
                    used=used,
                    free=free,
                    percent=percent,
                )
            )

    return result


def parse_diskstats_output(output: str) -> DiskIOStats | None:
    """Parse the contents of '/proc/diskstats' file into disk I/O stats.

    See https://www.kernel.org/doc/html/latest/admin-guide/iostats.html for
    details on the diskstats file format. Field defintions are copied here for convenience. Not all fields are collected into the DiskIOStats model.

    In diskstats, each line is prefixed with the major and minor device numbers and the device name. The remaining fields are the statistics for that device.

    Field 1 -- # of reads completed (unsigned long)
    This is the total number of reads completed successfully.

    Field 2 -- # of reads merged, field 6 -- # of writes merged (unsigned long)
    Reads and writes which are adjacent to each other may be merged for efficiency. Thus two 4K reads may become one 8K read before it is ultimately handed to the disk, and so it will be counted (and queued) as only one I/O. This field lets you know how often this was done.

    Field 3 -- # of sectors read (unsigned long)
    This is the total number of sectors read successfully.

    Field 4 -- # of milliseconds spent reading (unsigned int)
    This is the total number of milliseconds spent by all reads (as measured from blk_mq_alloc_request() to __blk_mq_end_request()).

    Field 5 -- # of writes completed (unsigned long)
    This is the total number of writes completed successfully.

    Field 6 -- # of writes merged (unsigned long)
    See the description of field 2.

    Field 7 -- # of sectors written (unsigned long)
    This is the total number of sectors written successfully.

    Field 8 -- # of milliseconds spent writing (unsigned int)
    This is the total number of milliseconds spent by all writes (as measured from blk_mq_alloc_request() to __blk_mq_end_request()).

    Field 9 -- # of I/Os currently in progress (unsigned int)
    The only field that should go to zero. Incremented as requests are given to appropriate struct request_queue and decremented as they finish.

    Field 10 -- # of milliseconds spent doing I/Os (unsigned int)
    This field increases so long as field 9 is nonzero.

    Since 5.0 this field counts jiffies when at least one request was started or completed. If request runs more than 2 jiffies then some I/O time might be not accounted in case of concurrent requests.

    Field 11 -- weighted # of milliseconds spent doing I/Os (unsigned int)
    This field is incremented at each I/O start, I/O completion, I/O merge, or read of these stats by the number of I/Os in progress (field 9) times the number of milliseconds spent doing I/O since the last update of this field. This can provide an easy measure of both I/O completion time and the backlog that may be accumulating.

    Field 12 -- # of discards completed (unsigned long)
    This is the total number of discards completed successfully.

    Field 13 -- # of discards merged (unsigned long)
    See the description of field 2

    Field 14 -- # of sectors discarded (unsigned long)
    This is the total number of sectors discarded successfully.

    Field 15 -- # of milliseconds spent discarding (unsigned int)
    This is the total number of milliseconds spent by all discards (as measured from blk_mq_alloc_request() to __blk_mq_end_request()).

    Field 16 -- # of flush requests completed
    This is the total number of flush requests completed successfully.

    Block layer combines flush requests and executes at most one at a time. This counts flush requests executed by disk. Not tracked for partitions.

    Field 17 -- # of milliseconds spent flushing
    This is the total number of milliseconds spent by all flush requests.
    """
    # Initialize counters for total read and write bytes and counts
    total_read_bytes = 0
    total_write_bytes = 0
    total_read_count = 0
    total_write_count = 0

    for line in output.strip().split("\n"):
        parts = line.split()

        # Each line is prefixed with the major and minor device numbers and the device name. The remaining fields are the statistics for that device.
        if len(parts) >= 14:
            # Element 0 and 1 are the major and minor device numbers
            # Element 2 is the device name
            device_name = parts[2]

            # Only count physical disks (e.g., sda, nvme0n1), skip partitions
            # Skip loop devices, ram devices, etc.
            if (
                device_name.startswith(("loop", "ram", "sr"))
                or any(c.isdigit() for c in device_name[-1])
                and not device_name.startswith("nvme")
            ):
                continue

            # Element 3 is the number of reads completed
            # Element 5 is the number of sectors read
            # Element 7 is the number of writes completed
            # Element 9 is the number of sectors written
            reads_completed = int(parts[3])
            sectors_read = int(parts[5])
            writes_completed = int(parts[7])
            sectors_written = int(parts[9])

            total_read_count += reads_completed
            total_read_bytes += sectors_read * 512
            total_write_count += writes_completed
            total_write_bytes += sectors_written * 512

    if total_read_bytes or total_write_bytes or total_read_count or total_write_count:
        return DiskIOStats(
            read_bytes=total_read_bytes,
            write_bytes=total_write_bytes,
            read_count=total_read_count,
            write_count=total_write_count,
        )

    return None


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
    partitions: list[DiskPartition] = []
    io_stats: DiskIOStats | None = None

    class DiskUsageAttribute(BaseModel):
        """Disk usage attribute."""

        names: list[str]
        command: list[str]
        parser: Callable[[str], t.Any]

    attributes = [
        DiskUsageAttribute(names=["partitions"], command=["df", "-B1"], parser=parse_df_output),
        DiskUsageAttribute(names=["io_stats"], command=["cat", "/proc/diskstats"], parser=parse_diskstats_output),
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
                case ["partitions"]:
                    partitions = parsed_output
                case ["io_stats"]:
                    io_stats = parsed_output
                case _:
                    raise ToolError(f"Unknown attribute: {attribute.names}")

    return DiskUsage(partitions=partitions, io_stats=io_stats)


async def parse_pci_devices(host: Host | None = None, username: Username | None = None) -> list[PCIDevice]:
    """
    Parse PCI devices from sysfs.

    Reads device information from /sys/bus/pci/devices/ without relying on lspci.
    """
    pci_devices = []

    # List all PCI devices
    returncode, stdout, stderr = await execute_command(
        ["find", "/sys/bus/pci/devices", "-maxdepth", "1", "-type", "l"],
        host=host,
        username=username,
    )

    if returncode != 0 or not stdout:
        return pci_devices

    device_paths = [
        path.strip() for path in stdout.strip().split("\n") if path.strip() and path != "/sys/bus/pci/devices"
    ]

    for device_path in device_paths:
        # Extract the device address from path (e.g., 0000:00:1f.2)
        address = device_path.split("/")[-1]

        device = PCIDevice(address=address)

        # Read all device attributes in a single command
        # Format: "key:value" for each file, one per line
        returncode, stdout, _ = await execute_command(
            [
                "sh",
                "-c",
                f"cd {device_path} && for f in vendor device class label; do echo \"$f:$(cat $f 2>/dev/null || echo '')\"; done",
            ],
            host=host,
            username=username,
        )

        if returncode == 0 and stdout:
            # Parse the output: each line is "key:value"
            for line in stdout.strip().split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    value = value.strip()
                    if value:  # Only set if value is not empty
                        match key:
                            case "vendor":
                                device.vendor_id = value
                            case "device":
                                device.device_id = value
                            case "class":
                                device.class_id = value
                            case "label":
                                device.description = value

        pci_devices.append(device)

    return pci_devices


async def parse_usb_devices(host: Host | None = None, username: Username | None = None) -> list[USBDevice]:
    """
    Parse USB devices from sysfs.

    Reads device information from /sys/bus/usb/devices/ without relying on lsusb.
    """
    usb_devices = []

    # List all USB devices
    returncode, stdout, stderr = await execute_command(
        ["find", "/sys/bus/usb/devices", "-maxdepth", "1", "-type", "l"],
        host=host,
        username=username,
    )

    if returncode != 0 or not stdout:
        return usb_devices

    device_paths = [
        path.strip() for path in stdout.strip().split("\n") if path.strip() and path != "/sys/bus/usb/devices"
    ]

    for device_path in device_paths:
        # Extract the bus-device identifier (e.g., 1-1, 2-1.1)
        # Skip root hubs (like usb1, usb2)
        device_name = device_path.split("/")[-1]
        if "-" not in device_name:
            continue

        # Parse bus and device from name (e.g., "1-1" -> bus 1, device path 1)
        parts = device_name.split("-")
        bus = parts[0]

        device = USBDevice(bus=bus, device=device_name)

        # Read all device attributes in a single command
        # Format: "key:value" for each file, one per line
        returncode, stdout, _ = await execute_command(
            [
                "sh",
                "-c",
                f"cd {device_path} && for f in idVendor idProduct product manufacturer; do echo \"$f:$(cat $f 2>/dev/null || echo '')\"; done",
            ],
            host=host,
            username=username,
        )

        if returncode == 0 and stdout:
            # Parse the output: each line is "key:value"
            for line in stdout.strip().split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    value = value.strip()
                    if value:  # Only set if value is not empty
                        match key:
                            case "idVendor":
                                device.vendor_id = value
                            case "idProduct":
                                device.product_id = value
                            case "product":
                                device.description = value
                            case "manufacturer":
                                device.manufacturer = value

        usb_devices.append(device)

    return usb_devices


@mcp.tool(
    title="Get device information",
    description="Get hardware device information including PCI and USB devices. Reads directly from sysfs without requiring lspci or lsusb utilities.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
async def get_device_information(
    host: Host | None = None,
    username: Username | None = None,
) -> DeviceInfo:
    """
    Get device information for PCI and USB devices.

    This tool reads device information directly from the Linux sysfs filesystem
    (/sys/bus/pci/devices/ and /sys/bus/usb/devices/) and does not rely on
    external utilities like lspci or lsusb which may not be installed.
    """
    try:
        # Parse PCI devices
        pci_devices = await parse_pci_devices(host=host, username=username)

        # Parse USB devices
        usb_devices = await parse_usb_devices(host=host, username=username)

        return DeviceInfo(
            pci_devices=pci_devices,
            pci_device_count=len(pci_devices),
            usb_devices=usb_devices,
            usb_device_count=len(usb_devices),
        )
    except Exception as e:
        raise ToolError(f"Error: {str(e)}") from e
