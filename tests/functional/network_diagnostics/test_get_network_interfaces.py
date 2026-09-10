# Copyright Contributors to the linux-mcp-server project
# SPDX-License-Identifier: Apache-2.0
import json

from utils.shell import shell


async def test_network_interfaces(mcp_session):
    """
    Verify that the server lists correctly all the available network interfaces.
    """
    response = await mcp_session.call_tool("get_network_interfaces")
    assert response is not None

    actual_network_interfaces = shell("ip -j a", silent=True).stdout.strip()
    interfaces = json.loads(actual_network_interfaces)
    content = response.structured_content["result"]
    assert content is not None

    content_by_name = {iface["name"]: iface for iface in content}

    for iface in interfaces:
        if iface["link_type"] == "loopback":
            continue
        name = iface["ifname"]
        status = iface["operstate"]

        addr_info = iface.get("addr_info", [])
        addresses = []
        if addr_info:
            for addr in addr_info:
                if addr["family"] == "inet" or addr["family"] == "inet6":
                    addresses.append(f"{addr['local']}/{addr['prefixlen']}")

        assert addresses, f"No addresses found for interface {name}"
        assert name in content_by_name, f"Interface {name} not found in structured output"
        result_iface = content_by_name[name]
        assert result_iface["status"] == status
        for address in addresses:
            assert address in result_iface["addresses"]
