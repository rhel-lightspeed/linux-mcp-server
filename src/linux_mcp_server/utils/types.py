"""Type definitions for linux-mcp-server."""

import typing as t

from pydantic import BaseModel
from pydantic import Field
from pydantic import StringConstraints


# Annotated types
Host = t.Annotated[str | None, Field(description="Remote host to connect to via SSH")]
UpperCase = t.Annotated[str, StringConstraints(to_upper=True)]


# Network types
class NetworkConnection(BaseModel):
    """Parsed network connection from ss/netstat output."""

    protocol: str
    state: str
    local_address: str
    local_port: str
    remote_address: str
    remote_port: str
    process: str = ""


class ListeningPort(BaseModel):
    """Parsed listening port from ss/netstat output."""

    protocol: str
    local_address: str
    local_port: str
    process: str = ""


class NetworkInterface(BaseModel):
    """Parsed network interface information."""

    name: str
    status: str = ""
    addresses: list[str] = Field(default_factory=list)
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_packets: int = 0
    tx_packets: int = 0
    rx_errors: int = 0
    tx_errors: int = 0
    rx_dropped: int = 0
    tx_dropped: int = 0


# Process types
class ProcessInfo(BaseModel):
    """Parsed process information from ps output."""

    pid: int
    user: str
    cpu_percent: float
    mem_percent: float
    vsz: int
    rss: int
    tty: str
    stat: str
    start: str
    time: str
    command: str


# Memory types
class MemoryInfo(BaseModel):
    """Parsed memory information from free command."""

    total: int
    used: int
    free: int
    shared: int = 0
    buffers: int = 0
    cached: int = 0
    available: int = 0


class SwapInfo(BaseModel):
    """Parsed swap information from free command."""

    total: int
    used: int
    free: int


class SystemMemory(BaseModel):
    """Combined memory and swap information."""

    ram: MemoryInfo
    swap: SwapInfo | None = None


# System types
class SystemInfo(BaseModel):
    """Parsed system information."""

    hostname: str = ""
    os_name: str = ""
    os_version: str = ""
    kernel: str = ""
    arch: str = ""
    uptime: str = ""
    boot_time: str = ""


class CpuInfo(BaseModel):
    """Parsed CPU information."""

    model: str = ""
    logical_cores: int = 0
    physical_cores: int = 0
    frequency_mhz: float = 0.0
    load_avg_1m: float = 0.0
    load_avg_5m: float = 0.0
    load_avg_15m: float = 0.0
    cpu_line: str = ""  # Raw CPU usage line from top


class FilesystemInfo(BaseModel):
    """Individual filesystem entry from findmnt output."""

    source: str = ""
    fstype: str = ""
    size: str = ""
    used: str = ""
    avail: str = ""
    use_percent: str = Field(default="", alias="use%")
    target: str = ""

    model_config = {"populate_by_name": True}


class DiskUsage(BaseModel):
    """Disk usage information from findmnt --df --json."""

    filesystems: list[FilesystemInfo] = Field(default_factory=list)


# Storage types
class NodeEntry(BaseModel):
    """A node entry model that is used by both directories and files listing."""

    size: int = 0
    modified: float = 0.0
    name: str = ""
