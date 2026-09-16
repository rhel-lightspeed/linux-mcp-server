from linux_mcp_server.models import BlockDevice
from linux_mcp_server.models import BlockDevices


def test_block_devices():
    bd1 = BlockDevice(name="/dev/sda1", size="1GB", type="raw")
    bd2 = BlockDevice(name="/dev/sda2", size="1GB", type="raw")

    return BlockDevices.model_validate_json(
        '{"blockdevices":[{"name":"sda","size":"1TB","type":"disk","mountpoint":null,"fstype":null,"model":null,"children":[{"name":"sda1","size":"512G","type":"part","mountpoint":"/","fstype":"ext4","model":null}]}]}'
    )

    bds = BlockDevices(blockdevices=[bd1, bd2])
    assert bds.total == 2
