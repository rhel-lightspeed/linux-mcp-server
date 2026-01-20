from pydantic import BaseModel


class BlockDevice(BaseModel):
    name: str
    size: str
    type: str
    mountpoint: str | None = None
    fstype: str | None = None
    model: str | None = None
    children: list["BlockDevice"] = []


class BlockDevices(BaseModel):
    blockdevices: list[BlockDevice]
