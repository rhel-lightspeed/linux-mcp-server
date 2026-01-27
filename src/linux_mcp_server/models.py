import typing as t

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from linux_mcp_server.utils.format import format_bytes


### Default factory functions ###
def field_length(field: str) -> t.Callable[[t.Any], int]:
    """Return the length of the given field"""

    def _field_length(data: t.Any) -> int:
        return len(data[field])

    return _field_length


### Storage models ###
class BlockDevice(BaseModel):
    name: str
    size: str
    type: str
    mountpoint: str | None = None
    fstype: str | None = None
    model: str | None = None
    children: list["BlockDevice"] = []


class BlockDevices(BaseModel):
    block_devices: list[BlockDevice] = Field(alias="blockdevices")
    total: int = Field(default_factory=field_length("block_devices"))


class NodeEntry(BaseModel):
    """A node entry model that is used by both directories and files listing."""

    size: int = 0
    modified: float = 0.0
    human_size: str = Field(default_factory=lambda data: format_bytes(data["size"]))
    human_modified: datetime = Field(default_factory=lambda data: datetime.fromtimestamp(data["modified"]))
    name: str = ""


class StorageNodes(BaseModel):
    nodes: list[NodeEntry]
    total: int = Field(default_factory=field_length("nodes"))
