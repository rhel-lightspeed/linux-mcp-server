"""System information tools."""

import typing as t

from mcp.types import ToolAnnotations
from pydantic import BaseModel
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.processing import CommandKey
from linux_mcp_server.processing import ParsedData
from linux_mcp_server.processing import RawCommandOutput
from linux_mcp_server.processing import Rummager
from linux_mcp_server.server import mcp
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host


# Helper function for filter phase
def apply_list_filter(
    items: list[t.Any],
    filter_key: str,
    filter_values: list[str] | None,
) -> list[t.Any]:
    """
    Helper to filter a list of dictionaries by a specific key.

    If filter_values is None, return all items.
    """
    if filter_values is None:
        return items

    return [item for item in items if isinstance(item, dict) and item.get(filter_key) in filter_values]


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

    one_min: float = 0.0
    five_min: float = 0.0
    fifteen_min: float = 0.0


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


async def parse_system_information(raw_outputs: dict[CommandKey, RawCommandOutput]) -> ParsedData:
    """
    Parse phase: Convert raw command outputs into structured data for system information.

    Returns a dictionary with system information fields.
    """
    parsed: ParsedData = {}

    for command, output in raw_outputs.items():
        match command:
            case ("hostname",):
                # Parse hostname
                parsed["hostname"] = output.strip()
            case ("cat", "/etc/os-release"):
                # Parse os-release file
                os_release_data = {}
                for line in output.split("\n"):
                    if "=" in line:
                        key, value = line.strip().split("=", 1)
                        os_release_data[key] = value.strip('"')
                parsed["operating_system"] = os_release_data.get("PRETTY_NAME")
                parsed["os_version"] = os_release_data.get("VERSION_ID")
            case ("uname", "-r", "-m"):
                # Parse uname output
                parts = output.strip().split(None, 1)
                parsed["kernel_version"] = parts[0] if len(parts) > 0 else None
                parsed["architecture"] = parts[1] if len(parts) > 1 else None
            case ("uptime", "-p"):
                # Parse uptime
                parsed["uptime"] = output.strip()
            case ("uptime", "-s"):
                # Parse boot time
                parsed["boot_time"] = output.strip()
            case _:
                continue

    return parsed


@mcp.tool(
    title="Get system information",
    description="Get basic system information such as operating system, distribution, kernel version, uptime, and last boot time.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_system_information(
    host: Host | None = None,
    fields: t.Annotated[
        list[str],
        Field(
            description="List of fields to include. If None, all fields are included. Valid fields: hostname, operating_system, os_version, kernel_version, architecture, uptime, boot_time"
        ),
    ]
    | None = None,
) -> SystemInfo:
    """Get basic system information."""

    commands = [
        ["hostname"],
        ["cat", "/etc/os-release"],
        ["uname", "-r", "-m"],
        ["uptime", "-p"],
        ["uptime", "-s"],
    ]
    rummager = Rummager(parse_func=parse_system_information)
    filtered_data = await rummager.rummage(commands, fields=fields, host=host)

    # Build SystemInfo object from filtered data
    return SystemInfo(
        hostname=filtered_data.get("hostname"),
        operating_system=filtered_data.get("operating_system"),
        os_version=filtered_data.get("os_version"),
        kernel_version=filtered_data.get("kernel_version"),
        architecture=filtered_data.get("architecture"),
        uptime=filtered_data.get("uptime"),
        boot_time=filtered_data.get("boot_time"),
    )


def parse_cpuinfo(output: str) -> ParsedData:
    """Parse /proc/cpuinfo output into structured CPU data."""
    parsed: ParsedData = {}
    lines = output.strip().split("\n")

    # Extract cpu_model
    parsed["cpu_model"] = next((line.split(":", 1)[1].strip() for line in lines if line.startswith("model name")), None)
    # Count logical cores
    parsed["logical_cores"] = sum(1 for line in lines if line.startswith("processor"))
    # Count physical sockets
    parsed["physical_sockets"] = len(set(line for line in lines if line.startswith("physical id")))
    # Get physical cores per processor
    parsed["physical_cores_per_processor"] = next(
        (int(line.split(":", 1)[1].strip()) for line in lines if line.startswith("cpu cores")), None
    )
    # Get CPU frequency
    parsed["frequency_mhz"] = next(
        (float(line.split(":", 1)[1].strip()) for line in lines if line.startswith("cpu MHz")), 0.0
    )

    return parsed


async def parse_cpu_information(raw_outputs: dict[CommandKey, RawCommandOutput]) -> ParsedData:
    """
    Parse phase: Convert raw command outputs into structured CPU data for CPU information.

    Returns a dictionary with CPU information fields.
    """
    parsed: ParsedData = {}

    # Parse /proc/cpuinfo (only once for all fields)
    if ("cat", "/proc/cpuinfo") in raw_outputs:
        cpuinfo = raw_outputs[("cat", "/proc/cpuinfo")]
        parsed.update(parse_cpuinfo(cpuinfo))

    # Parse load average
    if ("cat", "/proc/loadavg") in raw_outputs:
        parts = raw_outputs[("cat", "/proc/loadavg")].strip().split()
        if len(parts) >= 3:
            parsed["load_average"] = {
                "one_min": float(parts[0]),
                "five_min": float(parts[1]),
                "fifteen_min": float(parts[2]),
            }

    # Parse CPU usage from top
    if ("top", "-bn1") in raw_outputs:
        top_output = raw_outputs[("top", "-bn1")]
        if "Cpu(s):" in top_output or "%Cpu" in top_output:
            parsed["cpu_usage"] = top_output.strip()

    return parsed


@mcp.tool(
    title="Get CPU information",
    description="Get CPU information.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_cpu_information(
    host: Host | None = None,
    fields: t.Annotated[
        list[str],
        Field(
            description="List of fields to include. If None, all fields are included. Valid fields: cpu_model, logical_cores, physical_sockets, physical_cores_per_processor, frequency_mhz, load_average, cpu_usage"
        ),
    ]
    | None = None,
) -> CPUInfo:
    """Get CPU information."""

    commands = [
        ["cat", "/proc/cpuinfo"],
        ["cat", "/proc/loadavg"],
        ["top", "-bn1"],
    ]
    rummager = Rummager(parse_func=parse_cpu_information)
    filtered_data = await rummager.rummage(commands, fields=fields, host=host)

    # Build CPUInfo object from filtered data
    load_avg_data = filtered_data.get("load_average")
    load_average = LoadAverage(**load_avg_data) if load_avg_data else LoadAverage()

    return CPUInfo(
        cpu_model=filtered_data.get("cpu_model"),
        logical_cores=filtered_data.get("logical_cores"),
        physical_sockets=filtered_data.get("physical_sockets"),
        physical_cores_per_processor=filtered_data.get("physical_cores_per_processor"),
        frequency_mhz=filtered_data.get("frequency_mhz"),
        load_average=load_average,
        cpu_usage=filtered_data.get("cpu_usage"),
    )


async def parse_memory_information(raw_outputs: dict[CommandKey, RawCommandOutput]) -> ParsedData:
    """
    Parse phase: Convert raw command outputs into structured memory data for memory information.

    Returns a dictionary with memory information fields.
    """
    parsed: ParsedData = {}

    # Parse free output
    if ("free", "-b") in raw_outputs:
        lines = raw_outputs[("free", "-b")].strip().split("\n")

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

                    parsed["ram"] = {
                        "total": total,
                        "used": used,
                        "free": free,
                        "available": available,
                        "percent": percent,
                        "buffers": buff_cache,
                    }

            elif line.startswith("Swap:"):
                parts = line.split()
                if len(parts) >= 4:
                    total = int(parts[1])
                    used = int(parts[2])
                    free = int(parts[3])
                    percent = (used / total * 100) if total > 0 else 0

                    parsed["swap"] = {
                        "total": total,
                        "used": used,
                        "free": free,
                        "percent": percent,
                    }

    return parsed


@mcp.tool(
    title="Get memory information",
    description="Get detailed memory including physical and swap.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
async def get_memory_information(
    host: Host | None = None,
    fields: t.Annotated[
        list[str],
        Field(
            description="List of fields to include. If None, all fields are included. Valid fields: ram, swap (and nested fields like ram.total, ram.used, etc.)"
        ),
    ]
    | None = None,
) -> MemoryInfo:
    """
    Get memory information.
    """
    # Collect phase: Execute command
    commands = [
        ["free", "-b"],
    ]
    rummager = Rummager(parse_func=parse_memory_information)
    filtered_data = await rummager.rummage(commands, fields=fields, host=host)

    # Build MemoryInfo object from filtered data
    ram_data = filtered_data.get("ram")
    swap_data = filtered_data.get("swap")

    ram_stats = MemoryStats(**ram_data) if ram_data else None
    swap_stats = MemoryStats(**swap_data) if swap_data else None

    return MemoryInfo(ram=ram_stats, swap=swap_stats)


async def parse_disk_usage(raw_outputs: dict[CommandKey, RawCommandOutput]) -> ParsedData:
    """
    Parse phase: Convert raw command outputs into structured disk usage data for disk usage.

    Returns a dictionary with disk usage information fields.
    """
    parsed: ParsedData = {}

    # Parse df output
    if ("df", "-B1") in raw_outputs:
        lines = raw_outputs[("df", "-B1")].strip().split("\n")
        partitions = []

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

                partitions.append(
                    {
                        "device": device,
                        "mountpoint": mountpoint,
                        "size": size,
                        "used": used,
                        "free": free,
                        "percent": percent,
                    }
                )

            parsed["partitions"] = partitions

    # Parse diskstats
    if ("cat", "/proc/diskstats") in raw_outputs:
        output = raw_outputs[("cat", "/proc/diskstats")]

        # Initialize counters for total read and write bytes and counts
        total_read_bytes = 0
        total_write_bytes = 0
        total_read_count = 0
        total_write_count = 0

        for line in output.strip().split("\n"):
            parts = line.split()

            # Each line is prefixed with the major and minor device numbers and the device name
            if len(parts) >= 14:
                device_name = parts[2]

                # Only count physical disks (e.g., sda, nvme0n1), skip partitions
                # Skip loop devices, ram devices, etc.
                if (
                    device_name.startswith(("loop", "ram", "sr"))
                    or any(c.isdigit() for c in device_name[-1])
                    and not device_name.startswith("nvme")
                ):
                    continue

                reads_completed = int(parts[3])
                sectors_read = int(parts[5])
                writes_completed = int(parts[7])
                sectors_written = int(parts[9])

                total_read_count += reads_completed
                total_read_bytes += sectors_read * 512
                total_write_count += writes_completed
                total_write_bytes += sectors_written * 512

        if total_read_bytes or total_write_bytes or total_read_count or total_write_count:
            parsed["io_stats"] = {
                "read_bytes": total_read_bytes,
                "write_bytes": total_write_bytes,
                "read_count": total_read_count,
                "write_count": total_write_count,
            }

    return parsed


@mcp.tool(
    title="Get disk usage",
    description="Get detailed disk space information including size, mount points, and utilization..",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_disk_usage(
    host: Host | None = None,
    mountpoints: t.Annotated[
        list[str], Field(description="List of mountpoints to include. If None, all mountpoints are included.")
    ]
    | None = None,
    fields: t.Annotated[
        list[str],
        Field(
            description="List of fields to include. If None, all fields are included. Valid fields: partitions, io_stats"
        ),
    ]
    | None = None,
) -> DiskUsage:
    """
    Get disk usage information.
    """
    # Collect phase: Execute commands
    commands = [
        ["df", "-B1"],
        ["cat", "/proc/diskstats"],
    ]
    rummager = Rummager(parse_func=parse_disk_usage)
    filtered_data = await rummager.rummage(commands, fields=fields, host=host)

    # Apply mountpoint filter to partitions
    partitions_data = filtered_data.get("partitions", [])
    if mountpoints is not None:
        partitions_data = apply_list_filter(partitions_data, "mountpoint", mountpoints)

    # Build DiskUsage object from filtered data
    partitions = [DiskPartition(**p) for p in partitions_data]

    io_stats_data = filtered_data.get("io_stats")
    io_stats = DiskIOStats(**io_stats_data) if io_stats_data else None

    return DiskUsage(partitions=partitions, io_stats=io_stats)


async def collect_device_information(
    commands: list[list[str]], host: Host | None = None
) -> dict[CommandKey, RawCommandOutput]:
    """
    Custom collect function for device information.

    This function dynamically discovers devices and reads their attributes.
    It doesn't use the commands parameter since device paths are discovered at runtime.
    """
    cache: dict[CommandKey, RawCommandOutput] = {}

    # Collect PCI devices
    pci_find_key = ("find", "/sys/bus/pci/devices", "-maxdepth", "1", "-type", "l")
    returncode, stdout, _ = await execute_command(list(pci_find_key[1:]), host=host)

    if returncode == 0 and stdout:
        cache[pci_find_key] = stdout
        device_paths = [
            path.strip() for path in stdout.strip().split("\n") if path.strip() and path != "/sys/bus/pci/devices"
        ]

        for device_path in device_paths:
            address = device_path.split("/")[-1]
            attrs = ["vendor", "device", "class", "label"]
            results = []
            for attr in attrs:
                file_path = f"{device_path}/{attr}"
                returncode, stdout, _ = await execute_command(["cat", file_path], host=host)
                # Handle both success and failure (file may not exist)
                value = stdout.strip() if returncode == 0 and stdout else ""
                results.append(f"{attr}:{value}")

            # Combine into single cache entry
            combined_output = "\n".join(results)
            cache[("pci_attrs", address)] = combined_output

    # Collect USB devices
    usb_find_key = ("find", "/sys/bus/usb/devices", "-maxdepth", "1", "-type", "l")
    returncode, stdout, _ = await execute_command(list(usb_find_key[1:]), host=host)

    if returncode == 0 and stdout:
        cache[usb_find_key] = stdout
        device_paths = [
            path.strip() for path in stdout.strip().split("\n") if path.strip() and path != "/sys/bus/usb/devices"
        ]

        for device_path in device_paths:
            device_name = device_path.split("/")[-1]
            # Skip root hubs (like usb1, usb2)
            if "-" not in device_name:
                continue

            attrs = ["idVendor", "idProduct", "product", "manufacturer"]
            results = []
            for attr in attrs:
                file_path = f"{device_path}/{attr}"
                returncode, stdout, _ = await execute_command(["cat", file_path], host=host)
                # Handle both success and failure (file may not exist)
                value = stdout.strip() if returncode == 0 and stdout else ""
                results.append(f"{attr}:{value}")

            # Combine into single cache entry
            combined_output = "\n".join(results)
            cache[("usb_attrs", device_name)] = combined_output

    return cache


def _parse_pci_device_attrs(address: str, output: str) -> PCIDevice:
    """Parse PCI device attributes from raw output."""
    device = PCIDevice(address=address)

    for line in output.strip().split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            value = value.strip()
            if value:
                match key:
                    case "vendor":
                        device.vendor_id = value
                    case "device":
                        device.device_id = value
                    case "class":
                        device.class_id = value
                    case "label":
                        device.description = value

    return device


def _parse_usb_device_attrs(device_name: str, output: str) -> USBDevice:
    """Parse USB device attributes from raw output."""
    parts = device_name.split("-")
    bus = parts[0]
    device = USBDevice(bus=bus, device=device_name)

    for line in output.strip().split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            value = value.strip()
            if value:
                match key:
                    case "idVendor":
                        device.vendor_id = value
                    case "idProduct":
                        device.product_id = value
                    case "product":
                        device.description = value
                    case "manufacturer":
                        device.manufacturer = value

    return device


async def parse_device_information(raw_outputs: dict[CommandKey, RawCommandOutput]) -> ParsedData:
    """
    Parse phase: Convert raw device outputs into structured device data.

    Returns a dictionary with pci_devices and usb_devices lists.
    """
    pci_devices = []
    usb_devices = []

    # Parse PCI and USB devices
    for command_key, output in raw_outputs.items():
        if command_key[0] == "pci_attrs" and len(command_key) == 2:
            address = command_key[1]
            pci_devices.append(_parse_pci_device_attrs(address, output))
        elif command_key[0] == "usb_attrs" and len(command_key) == 2:
            device_name = command_key[1]
            usb_devices.append(_parse_usb_device_attrs(device_name, output))

    return {
        "pci_devices": pci_devices,
        "usb_devices": usb_devices,
    }


async def filter_device_information(
    parsed_data: ParsedData, device_types: list[str] | None = None, limit: int | None = None
) -> ParsedData:
    """
    Filter phase: Apply device type and limit filters to device data.

    Args:
        parsed_data: The parsed device data containing pci_devices and usb_devices
        device_types: List of device types to include ('pci', 'usb'), or None for all
        limit: Maximum number of devices to return per type, or None for all

    Returns:
        Filtered device data
    """
    filtered = {}

    # Apply device type filter
    should_include_pci = device_types is None or "pci" in device_types
    should_include_usb = device_types is None or "usb" in device_types

    if should_include_pci and "pci_devices" in parsed_data:
        pci_devices = parsed_data["pci_devices"]
        if limit is not None:
            pci_devices = pci_devices[:limit]
        filtered["pci_devices"] = pci_devices

    if should_include_usb and "usb_devices" in parsed_data:
        usb_devices = parsed_data["usb_devices"]
        if limit is not None:
            usb_devices = usb_devices[:limit]
        filtered["usb_devices"] = usb_devices

    return filtered


@mcp.tool(
    title="Get device information",
    description="Get hardware device information including PCI and USB devices. Reads directly from sysfs without requiring lspci or lsusb utilities.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
async def get_device_information(
    host: Host | None = None,
    device_types: t.Annotated[
        list[str],
        Field(
            description="List of device types to include. If None, all types are included. Valid types: 'pci', 'usb'"
        ),
    ]
    | None = None,
    limit: t.Annotated[
        int, Field(description="Maximum number of devices to return per type. If None, all devices are returned.")
    ]
    | None = None,
) -> DeviceInfo:
    """
    Get device information for PCI and USB devices.

    This tool reads device information directly from the Linux sysfs filesystem
    (/sys/bus/pci/devices/ and /sys/bus/usb/devices/) and does not rely on
    external utilities like lspci or lsusb which may not be installed.
    """

    # Create a custom filter function that wraps filter_device_information
    # to match the FilterFunc signature
    async def custom_filter(parsed_data: ParsedData, fields: list[str] | None) -> ParsedData:
        return await filter_device_information(parsed_data, device_types=device_types, limit=limit)

    # Use Rummager with custom collect, parse, and filter functions
    rummager = Rummager(
        collect_func=collect_device_information,
        parse_func=parse_device_information,
        filter_func=custom_filter,
    )

    # Commands list is empty since collection is dynamic
    filtered_data = await rummager.rummage(commands=[], host=host)

    # Build DeviceInfo object from filtered data
    pci_devices = [
        device if isinstance(device, PCIDevice) else PCIDevice(**device)
        for device in filtered_data.get("pci_devices", [])
    ]
    usb_devices = [
        device if isinstance(device, USBDevice) else USBDevice(**device)
        for device in filtered_data.get("usb_devices", [])
    ]

    return DeviceInfo(
        pci_devices=pci_devices,
        pci_device_count=len(pci_devices),
        usb_devices=usb_devices,
        usb_device_count=len(usb_devices),
    )
