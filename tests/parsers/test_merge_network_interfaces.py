from linux_mcp_server.models import NetworkInterface
from linux_mcp_server.parsers import merge_network_interfaces


def test_merge_network_interfaces_empty():
    """Test merging with no inputs."""
    assert merge_network_interfaces({}) == []
    assert merge_network_interfaces({}, {}) == []


def test_merge_network_interfaces_interfaces_only():
    """Test merging when only address info is available."""
    interfaces = {
        "eth0": NetworkInterface(name="eth0", status="UP", addresses=["192.168.1.100/24"]),
        "lo": NetworkInterface(name="lo", status="UNKNOWN", addresses=["127.0.0.1/8"]),
    }

    result = merge_network_interfaces(interfaces)

    assert len(result) == 2
    assert result[0].name == "eth0"
    assert result[0].status == "UP"
    assert result[0].addresses == ["192.168.1.100/24"]
    assert result[0].rx_bytes == 0
    assert result[1].name == "lo"


def test_merge_network_interfaces_with_stats():
    """Test merging address info with traffic statistics."""
    interfaces = {
        "eth0": NetworkInterface(name="eth0", status="UP", addresses=["192.168.1.100/24"]),
    }
    stats = {
        "eth0": NetworkInterface(
            name="eth0",
            rx_bytes=1000000,
            tx_bytes=500000,
            rx_packets=10000,
            tx_packets=5000,
            rx_errors=10,
            tx_errors=5,
            rx_dropped=2,
            tx_dropped=1,
        ),
    }

    result = merge_network_interfaces(interfaces, stats)

    assert len(result) == 1
    iface = result[0]
    assert iface.name == "eth0"
    assert iface.status == "UP"
    assert iface.addresses == ["192.168.1.100/24"]
    assert iface.rx_bytes == 1000000
    assert iface.tx_bytes == 500000
    assert iface.rx_packets == 10000
    assert iface.tx_packets == 5000
    assert iface.rx_errors == 10
    assert iface.tx_errors == 5
    assert iface.rx_dropped == 2
    assert iface.tx_dropped == 1


def test_merge_network_interfaces_stats_only_ignored():
    """Test that stats-only interfaces are not included."""
    stats = {
        "eth0": NetworkInterface(name="eth0", rx_bytes=1000, tx_bytes=500),
    }

    assert merge_network_interfaces({}, stats) == []
