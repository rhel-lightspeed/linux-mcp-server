"""System information tools."""

import re
import typing as t

from mcp.types import ToolAnnotations
from pydantic import BaseModel
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.data_pipeline import CommandKey
from linux_mcp_server.data_pipeline import DataParser
from linux_mcp_server.data_pipeline import ParsedData
from linux_mcp_server.data_pipeline import RawCommandOutput
from linux_mcp_server.server import mcp
from linux_mcp_server.utils import StrEnum
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host


# Helper function for filter phase
def _apply_list_filter(
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


class DeviceClass(StrEnum):
    PCI = "pci"
    USB = "usb"


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

    total: int = 0
    used: int = 0
    free: int = 0
    shared: int = 0
    percent: float = 0.0
    available: int | None = None
    buffers: int | None = None
    cached: int | None = None


class MemoryInfo(BaseModel):
    """Memory information model."""

    ram: MemoryStats
    swap: MemoryStats


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

    read_bytes: int = 0
    write_bytes: int = 0
    read_count: int = 0
    write_count: int = 0


class DiskUsage(BaseModel):
    """Disk usage information model."""

    partitions: list[DiskPartition]
    io_stats: DiskIOStats


class PCIDevice(BaseModel):
    """PCI device information from lspci -vmm output."""

    slot: str
    class_name: str | None = None
    vendor: str | None = None
    device: str | None = None
    subsystem_vendor: str | None = None
    subsystem_device: str | None = None
    revision: str | None = None


class USBDevice(BaseModel):
    """USB device information from lsusb output."""

    bus: str
    device: str
    vendor_id: str | None = None
    product_id: str | None = None
    description: str | None = None


class DeviceInfo(BaseModel):
    """Device information model for PCI and USB devices."""

    pci_devices: list[PCIDevice] = Field(default_factory=list)
    usb_devices: list[USBDevice] = Field(default_factory=list)

    @property
    def pci_device_count(self) -> int:
        return len(self.pci_devices)

    @property
    def usb_device_count(self) -> int:
        return len(self.usb_devices)


async def _parse_system_information(raw_outputs: dict[CommandKey, RawCommandOutput]) -> ParsedData:
    """
    Parse phase: Convert raw command outputs into structured data for system information. Collects:
     - hostname
     - operating system
     - os version
     - kernel version
     - architecture
     - uptime
     - boot time

    Returns a dictionary with system information fields.
    """
    parsed: ParsedData = {}

    # Pre-create CommandKey objects for matching
    hostname_key = CommandKey(["hostname"])
    os_release_key = CommandKey(["cat", "/etc/os-release"])
    uname_key = CommandKey(["uname", "-r", "-m"])
    uptime_p_key = CommandKey(["uptime", "-p"])
    uptime_s_key = CommandKey(["uptime", "-s"])

    for command_key, output in raw_outputs.items():
        if command_key == hostname_key:
            # Parse hostname
            parsed["hostname"] = output.strip()
        elif command_key == os_release_key:
            # Parse os-release file
            os_release_data = {}
            for line in output.split("\n"):
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    os_release_data[key] = value.strip('"')
            parsed["operating_system"] = os_release_data.get("PRETTY_NAME")
            parsed["os_version"] = os_release_data.get("VERSION_ID")
        elif command_key == uname_key:
            # Parse uname output
            parts = output.strip().split(None, 1)
            parsed["kernel_version"] = parts[0] if len(parts) > 0 else None
            parsed["architecture"] = parts[1] if len(parts) > 1 else None
        elif command_key == uptime_p_key:
            # Parse uptime
            parsed["uptime"] = output.strip()
        elif command_key == uptime_s_key:
            # Parse boot time
            parsed["boot_time"] = output.strip()

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
    processor = DataParser(parse_func=_parse_system_information)
    filtered_data = await processor.process(commands, fields=fields, host=host)

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


def _parse_cpuinfo(output: str) -> ParsedData:
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


async def _parse_cpu_information(raw_outputs: dict[CommandKey, RawCommandOutput]) -> ParsedData:
    """
    Parse phase: Convert raw command outputs into structured CPU data for CPU information.

    Returns a dictionary with CPU information fields.
    """
    parsed: ParsedData = {}

    # Parse /proc/cpuinfo (only once for all fields)
    cpuinfo_key = CommandKey(["cat", "/proc/cpuinfo"])
    if cpuinfo_key in raw_outputs:
        cpuinfo = raw_outputs[cpuinfo_key]
        parsed.update(_parse_cpuinfo(cpuinfo))

    # Parse load average
    loadavg_key = CommandKey(["cat", "/proc/loadavg"])
    if loadavg_key in raw_outputs:
        parts = raw_outputs[loadavg_key].strip().split()
        if len(parts) >= 3:
            parsed["load_average"] = {
                "one_min": float(parts[0]),
                "five_min": float(parts[1]),
                "fifteen_min": float(parts[2]),
            }

    # Parse CPU usage from top
    top_key = CommandKey(["top", "-bn1"])
    if top_key in raw_outputs:
        top_output = raw_outputs[top_key]
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
    processor = DataParser(parse_func=_parse_cpu_information)
    filtered_data = await processor.process(commands, fields=fields, host=host)

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


async def _parse_memory_information(raw_outputs: dict[CommandKey, RawCommandOutput]) -> ParsedData:
    """
    Parse phase: Convert raw command outputs into structured memory data for memory information.

    Returns a dictionary with memory information fields.
    """
    parsed: ParsedData = {}

    # Parse free output
    free_key = CommandKey(["free", "-b"])
    if free_key in raw_outputs:
        lines = raw_outputs[free_key].strip().split("\n")

        for line in lines:
            if line.startswith("Mem:"):
                parts = line.split()
                if len(parts) >= 7:
                    total = int(parts[1])
                    used = int(parts[2])
                    free = int(parts[3])
                    shared = int(parts[4])
                    buff_cache = int(parts[5]) if len(parts) > 5 else 0
                    available = int(parts[6]) if len(parts) > 6 else free
                    percent = (used / total * 100) if total > 0 else 0

                    parsed["ram"] = {
                        "total": total,
                        "used": used,
                        "free": free,
                        "shared": shared,
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
@disallow_local_execution_in_containers
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
    processor = DataParser(parse_func=_parse_memory_information)
    filtered_data = await processor.process(commands, fields=fields, host=host)

    # Build MemoryInfo object from filtered data
    ram_data = filtered_data.get("ram")
    swap_data = filtered_data.get("swap")

    ram_stats = MemoryStats(**ram_data) if ram_data else MemoryStats()
    swap_stats = MemoryStats(**swap_data) if swap_data else MemoryStats()

    return MemoryInfo(ram=ram_stats, swap=swap_stats)


async def _parse_disk_usage(raw_outputs: dict[CommandKey, RawCommandOutput]) -> ParsedData:
    """
    Parse phase: Convert raw command outputs into structured disk usage data for disk usage.

    Returns a dictionary with disk usage information fields.
    """
    parsed: ParsedData = {}

    # Parse df output
    df_key = CommandKey(["df", "-B1"])
    if df_key in raw_outputs:
        lines = raw_outputs[df_key].strip().split("\n")
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
    diskstats_key = CommandKey(["cat", "/proc/diskstats"])
    if diskstats_key in raw_outputs:
        output = raw_outputs[diskstats_key]

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
    processor = DataParser(parse_func=_parse_disk_usage)
    filtered_data = await processor.process(commands, fields=fields, host=host)

    # Apply mountpoint filter to partitions
    partitions_data = filtered_data.get("partitions", [])
    if mountpoints is not None:
        partitions_data = _apply_list_filter(partitions_data, "mountpoint", mountpoints)

    # Build DiskUsage object from filtered data
    partitions = [DiskPartition(**p) for p in partitions_data]

    io_stats_data = filtered_data.get("io_stats")
    io_stats = DiskIOStats(**io_stats_data) if io_stats_data else DiskIOStats()

    return DiskUsage(partitions=partitions, io_stats=io_stats)


def _parse_lspci_vmm(output: str) -> list[PCIDevice]:
    """
    Parse lspci -vmm output into a list of PCIDevice objects.

    lspci -vmm produces machine-readable output with blocks separated by blank lines:
    Slot:	00:00.0
    Class:	Host bridge
    Vendor:	Intel Corporation
    Device:	8th Gen Core Processor Host Bridge/DRAM Registers
    SVendor:	Lenovo
    SDevice:	ThinkPad X1 Carbon 6th Gen
    Rev:	08
    """
    devices = []
    current_device: dict[str, str] = {}

    for line in output.strip().split("\n"):
        line = line.strip()
        if not line:
            # End of device block
            if current_device and "Slot" in current_device:
                devices.append(
                    PCIDevice(
                        slot=current_device["Slot"],
                        class_name=current_device.get("Class"),
                        vendor=current_device.get("Vendor"),
                        device=current_device.get("Device"),
                        subsystem_vendor=current_device.get("SVendor"),
                        subsystem_device=current_device.get("SDevice"),
                        revision=current_device.get("Rev"),
                    )
                )
            current_device = {}
        elif ":\t" in line:
            key, value = line.split(":\t", 1)
            current_device[key] = value

    # Handle last device if no trailing newline
    if current_device and "Slot" in current_device:
        devices.append(
            PCIDevice(
                slot=current_device["Slot"],
                class_name=current_device.get("Class"),
                vendor=current_device.get("Vendor"),
                device=current_device.get("Device"),
                subsystem_vendor=current_device.get("SVendor"),
                subsystem_device=current_device.get("SDevice"),
                revision=current_device.get("Rev"),
            )
        )

    return devices


def _parse_lsusb(output: str) -> list[USBDevice]:
    """
    Parse lsusb output into a list of USBDevice objects.

    lsusb produces output in the format:
    Bus 001 Device 003: ID 04f2:b604 Chicony Electronics Co., Ltd Integrated Camera
    Bus 001 Device 002: ID 8087:0a2b Intel Corp. Bluetooth wireless interface
    """
    devices = []
    # Pattern: Bus XXX Device YYY: ID vendor:product Description
    pattern = re.compile(r"Bus\s+(\d+)\s+Device\s+(\d+):\s+ID\s+([0-9a-fA-F]+):([0-9a-fA-F]+)\s*(.*)")

    for line in output.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        match = pattern.match(line)
        if match:
            bus, device_num, vendor_id, product_id, description = match.groups()
            devices.append(
                USBDevice(
                    bus=bus,
                    device=device_num,
                    vendor_id=vendor_id,
                    product_id=product_id,
                    description=description.strip() if description else None,
                )
            )

    return devices


async def _parse_device_information(raw_outputs: dict[CommandKey, RawCommandOutput]) -> ParsedData:
    """
    Parse phase: Convert lspci and lsusb outputs into structured device data.

    Returns a dictionary with pci_devices and usb_devices lists.
    """
    pci_devices: list[PCIDevice] = []
    usb_devices: list[USBDevice] = []

    lspci_key = CommandKey(["lspci", "-vmm"])
    lsusb_key = CommandKey(["lsusb"])

    for command_key, output in raw_outputs.items():
        if command_key == lspci_key:
            pci_devices = _parse_lspci_vmm(output)
        elif command_key == lsusb_key:
            usb_devices = _parse_lsusb(output)

    return {
        "pci_devices": pci_devices,
        "usb_devices": usb_devices,
    }


@mcp.tool(
    title="Get device information",
    description="Get hardware device information for PCI and USB devices.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_device_information(
    host: Host | None = None,
    device_types: t.Annotated[
        list[DeviceClass],
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

    This tool uses the lspci and lsusb utilities to gather device information.
    These utilities must be installed on the target system.
    """
    commands = [
        ["lspci", "-vmm"],
        ["lsusb"],
    ]

    data_parser = DataParser(parse_func=_parse_device_information)
    parsed_data = await data_parser.process(commands=commands, host=host)

    # Apply device type filter and limit
    should_include_pci = device_types is None or DeviceClass.PCI in device_types
    should_include_usb = device_types is None or DeviceClass.USB in device_types

    pci_devices: list[PCIDevice] = []
    usb_devices: list[USBDevice] = []

    if should_include_pci:
        pci_list = parsed_data.get("pci_devices", [])
        if limit is not None:
            pci_list = pci_list[:limit]
        pci_devices = [device if isinstance(device, PCIDevice) else PCIDevice(**device) for device in pci_list]

    if should_include_usb:
        usb_list = parsed_data.get("usb_devices", [])
        if limit is not None:
            usb_list = usb_list[:limit]
        usb_devices = [device if isinstance(device, USBDevice) else USBDevice(**device) for device in usb_list]

    return DeviceInfo(
        pci_devices=pci_devices,
        usb_devices=usb_devices,
    )
