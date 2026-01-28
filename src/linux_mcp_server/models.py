import typing as t

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator

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
    name: str = ""
    human_size: str = ""
    human_modified: datetime = datetime.fromtimestamp(0.0)

    @model_validator(mode="after")
    def human_values(self):
        self.human_size = format_bytes(self.size)
        self.human_modified = datetime.fromtimestamp(self.modified)

        return self


class StorageNodes(BaseModel):
    nodes: list[NodeEntry]
    total: int = Field(default_factory=field_length("nodes"))
