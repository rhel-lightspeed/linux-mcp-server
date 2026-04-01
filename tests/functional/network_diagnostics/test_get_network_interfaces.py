# Copyright Red Hat
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
    for iface in interfaces:
        if iface["link_type"] == "loopback":
            # Skip the loopback as it has different attributes
            # (I did not want to parse them now)
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
        matching_string = f"{name}:\n  Status: {status}\n"
        matching_string += "\n".join(f"  Address: {address}" for address in addresses)

        assert matching_string in response.content[0].text
