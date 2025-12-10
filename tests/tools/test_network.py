"""Tests for network diagnostic tools."""

import socket

from unittest.mock import MagicMock

import psutil
import pytest

from linux_mcp_server.server import mcp
from tests.conftest import GLOBAL_IPV6
from tests.conftest import IPV4_ADDR
from tests.conftest import LINK_LOCAL_FILTER_CASES_NETWORK
from tests.conftest import LINK_LOCAL_IPV6
from tests.conftest import make_mixed_connections_network
from tests.conftest import make_mixed_listening_ports
from tests.conftest import MockAddr
from tests.conftest import MockConnection


class MockAddress:
    """Mock network address object (for interface addresses)."""

    def __init__(self, family, address, netmask=None, broadcast=None):
        self.family = family
        self.address = address
        self.netmask = netmask
        self.broadcast = broadcast


class MockInterfaceStats:
    """Mock network interface statistics."""

    def __init__(self, isup=True, speed=1000, mtu=1500):
        self.isup = isup
        self.speed = speed
        self.mtu = mtu


class MockNetIOCounters:
    """Mock network I/O counters."""

    def __init__(self):
        self.bytes_sent = 1024 * 1024 * 100  # 100 MB
        self.bytes_recv = 1024 * 1024 * 200  # 200 MB
        self.packets_sent = 50000
        self.packets_recv = 75000
        self.errin = 5
        self.errout = 3
        self.dropin = 2
        self.dropout = 1


class TestGetNetworkInterfaces:
    """Test get_network_interfaces function."""

    async def test_get_network_interfaces_local_success(self, mocker):
        """Test getting network interfaces locally with success."""
        # Mock psutil functions
        mock_net_if_addrs = {
            "eth0": [
                MockAddress(socket.AF_INET, "192.168.1.100", "255.255.255.0", "192.168.1.255"),
                MockAddress(socket.AF_INET6, "2001:db8::1", "ffff:ffff:ffff:ffff::"),
                # Link-local address should be filtered out
                MockAddress(socket.AF_INET6, "fe80::1%eth0", "ffff:ffff:ffff:ffff::"),
                MockAddress(psutil.AF_LINK, "00:11:22:33:44:55"),
            ],
            "lo": [
                MockAddress(socket.AF_INET, "127.0.0.1", "255.0.0.0"),
            ],
        }

        mock_net_if_stats = {
            "eth0": MockInterfaceStats(isup=True, speed=1000, mtu=1500),
            "lo": MockInterfaceStats(isup=True, speed=0, mtu=65536),
        }

        mock_net_io = MockNetIOCounters()

        mocker.patch("linux_mcp_server.tools.network.psutil.net_if_addrs", return_value=mock_net_if_addrs)
        mocker.patch("linux_mcp_server.tools.network.psutil.net_if_stats", return_value=mock_net_if_stats)
        mocker.patch("linux_mcp_server.tools.network.psutil.net_io_counters", return_value=mock_net_io)

        result = await mcp.call_tool("get_network_interfaces", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Network Interfaces" in output
        assert "eth0" in output
        assert "lo" in output
        assert "192.168.1.100" in output
        assert "127.0.0.1" in output
        assert "2001:db8::1" in output  # Global IPv6 should be shown
        assert "fe80::" not in output  # Link-local should be filtered out
        assert "00:11:22:33:44:55" in output
        assert "Status: UP" in output
        assert "Speed: 1000 Mbps" in output
        assert "MTU: 1500" in output
        assert "Network I/O Statistics" in output
        assert "Bytes Sent" in output
        assert "Bytes Received" in output
        assert "Packets Sent: 50000" in output
        assert "Packets Received: 75000" in output
        assert "Errors In: 5" in output
        assert "Errors Out: 3" in output
        assert "Drops In: 2" in output
        assert "Drops Out: 1" in output

    async def test_get_network_interfaces_local_without_optional_fields(self, mocker):
        """Test getting network interfaces locally without optional fields."""
        mock_net_if_addrs = {
            "eth0": [
                MockAddress(socket.AF_INET, "192.168.1.100"),  # No netmask/broadcast
            ],
        }

        mock_net_if_stats = {
            "eth0": MockInterfaceStats(isup=False, speed=0, mtu=1500),
        }

        mock_net_io = MockNetIOCounters()

        mocker.patch("linux_mcp_server.tools.network.psutil.net_if_addrs", return_value=mock_net_if_addrs)
        mocker.patch("linux_mcp_server.tools.network.psutil.net_if_stats", return_value=mock_net_if_stats)
        mocker.patch("linux_mcp_server.tools.network.psutil.net_io_counters", return_value=mock_net_io)

        result = await mcp.call_tool("get_network_interfaces", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "eth0" in output
        assert "Status: DOWN" in output
        assert "192.168.1.100" in output

    async def test_get_network_interfaces_local_interface_not_in_stats(self, mocker):
        """Test getting network interfaces when interface is not in stats."""
        mock_net_if_addrs = {
            "eth0": [
                MockAddress(socket.AF_INET, "192.168.1.100", "255.255.255.0"),
            ],
        }

        mock_net_if_stats = {}  # Empty stats

        mock_net_io = MockNetIOCounters()

        mocker.patch("linux_mcp_server.tools.network.psutil.net_if_addrs", return_value=mock_net_if_addrs)
        mocker.patch("linux_mcp_server.tools.network.psutil.net_if_stats", return_value=mock_net_if_stats)
        mocker.patch("linux_mcp_server.tools.network.psutil.net_io_counters", return_value=mock_net_io)

        result = await mcp.call_tool("get_network_interfaces", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "eth0" in output
        assert "192.168.1.100" in output
        # Should not have status info since interface not in stats

    async def test_get_network_interfaces_local_error(self, mocker):
        """Test getting network interfaces locally with error."""
        mocker.patch(
            "linux_mcp_server.tools.network.psutil.net_if_addrs",
            side_effect=Exception("Network error"),
        )

        result = await mcp.call_tool("get_network_interfaces", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Error getting network interface information" in output
        assert "Network error" in output

    async def test_get_network_interfaces_remote_success(self, mocker):
        """Test getting network interfaces remotely with success."""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")

        # Mock responses for different commands
        mock_execute.side_effect = [
            (0, "eth0             UP             192.168.1.100/24", ""),  # ip -brief address
            (
                0,
                "1: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500\n    inet 192.168.1.100/24",
                "",
            ),  # ip address
            (0, "eth0: 1024 2048 0 0 0 0 0 0", ""),  # /proc/net/dev
        ]

        result = await mcp.call_tool("get_network_interfaces", {"host": "remote.example.com"})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Network Interfaces" in output
        assert "eth0" in output
        assert "192.168.1.100" in output
        assert "Detailed Interface Information" in output
        assert "Network I/O Statistics" in output
        assert mock_execute.call_count == 3

    async def test_get_network_interfaces_remote_partial_failure(self, mocker):
        """Test getting network interfaces remotely with partial failures."""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")

        # First command succeeds, others fail
        mock_execute.side_effect = [
            (0, "eth0             UP             192.168.1.100/24", ""),
            (1, "", "Command failed"),
            (1, "", "Command failed"),
        ]

        result = await mcp.call_tool("get_network_interfaces", {"host": "remote.example.com"})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Network Interfaces" in output
        assert "eth0" in output

    async def test_get_network_interfaces_remote_all_empty(self, mocker):
        """Test getting network interfaces remotely with empty outputs."""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")

        # All commands return empty
        mock_execute.side_effect = [
            (1, None, ""),
            (1, None, ""),
            (1, None, ""),
        ]

        result = await mcp.call_tool("get_network_interfaces", {"host": "remote.example.com"})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Network Interfaces" in output


class TestGetNetworkConnections:
    """Test get_network_connections function."""

    async def test_get_network_connections_local_success(self, mocker):
        """Test getting network connections locally with success."""
        mock_connections = [
            MockConnection(
                type_=socket.SOCK_STREAM,
                laddr=MockAddr("127.0.0.1", 8080),
                raddr=MockAddr("127.0.0.1", 54321),
                status="ESTABLISHED",
                pid=1234,
            ),
            MockConnection(
                type_=socket.SOCK_DGRAM,
                laddr=MockAddr("0.0.0.0", 53),
                raddr=None,
                status=None,
                pid=5678,
            ),
        ]

        mock_process = MagicMock()
        mock_process.name.return_value = "python3"

        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)
        mocker.patch("linux_mcp_server.tools.network.psutil.Process", return_value=mock_process)

        result = await mcp.call_tool("get_network_connections", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Active Network Connections" in output
        assert "TCP" in output
        assert "UDP" in output
        assert "127.0.0.1:8080" in output
        assert "127.0.0.1:54321" in output
        assert "0.0.0.0:53" in output
        assert "ESTABLISHED" in output
        assert "1234/python3" in output
        assert "5678/python3" in output
        assert "Total connections: 2" in output

    async def test_get_network_connections_local_no_pid(self, mocker):
        """Test getting network connections locally without PID."""
        mock_connections = [
            MockConnection(
                type_=socket.SOCK_STREAM,
                laddr=MockAddr("127.0.0.1", 8080),
                raddr=MockAddr("127.0.0.1", 54321),
                status="ESTABLISHED",
                pid=None,
            ),
        ]

        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)

        result = await mcp.call_tool("get_network_connections", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Active Network Connections" in output
        assert "N/A" in output

    async def test_get_network_connections_local_no_addresses(self, mocker):
        """Test getting network connections locally without addresses."""
        mock_connections = [
            MockConnection(
                type_=socket.SOCK_STREAM,
                laddr=None,
                raddr=None,
                status=None,
                pid=1234,
            ),
        ]

        mock_process = MagicMock()
        mock_process.name.return_value = "python3"

        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)
        mocker.patch("linux_mcp_server.tools.network.psutil.Process", return_value=mock_process)

        result = await mcp.call_tool("get_network_connections", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "N/A" in output

    async def test_get_network_connections_local_process_not_found(self, mocker):
        """Test getting network connections when process is not found."""
        mock_connections = [
            MockConnection(
                type_=socket.SOCK_STREAM,
                laddr=MockAddr("127.0.0.1", 8080),
                raddr=MockAddr("127.0.0.1", 54321),
                status="ESTABLISHED",
                pid=1234,
            ),
        ]

        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)
        mocker.patch(
            "linux_mcp_server.tools.network.psutil.Process",
            side_effect=psutil.NoSuchProcess(1234),
        )

        result = await mcp.call_tool("get_network_connections", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "1234" in output  # Should still show PID

    async def test_get_network_connections_local_access_denied_process(self, mocker):
        """Test getting network connections when process access is denied."""
        mock_connections = [
            MockConnection(
                type_=socket.SOCK_STREAM,
                laddr=MockAddr("127.0.0.1", 8080),
                raddr=MockAddr("127.0.0.1", 54321),
                status="ESTABLISHED",
                pid=1234,
            ),
        ]

        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)
        mocker.patch(
            "linux_mcp_server.tools.network.psutil.Process",
            side_effect=psutil.AccessDenied(1234),
        )

        result = await mcp.call_tool("get_network_connections", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "1234" in output  # Should still show PID

    async def test_get_network_connections_local_access_denied(self, mocker):
        """Test getting network connections with permission denied."""
        mocker.patch(
            "linux_mcp_server.tools.network.psutil.net_connections",
            side_effect=psutil.AccessDenied(),
        )

        result = await mcp.call_tool("get_network_connections", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Permission denied" in output
        assert "elevated privileges" in output

    async def test_get_network_connections_local_error(self, mocker):
        """Test getting network connections with general error."""
        mocker.patch(
            "linux_mcp_server.tools.network.psutil.net_connections",
            side_effect=Exception("Network error"),
        )

        result = await mcp.call_tool("get_network_connections", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Error getting network connections" in output
        assert "Network error" in output

    async def test_get_network_connections_remote_ss_success(self, mocker):
        """Test getting network connections remotely using ss command."""
        mock_output = """Netid  State      Recv-Q Send-Q Local Address:Port   Peer Address:Port
tcp    ESTAB      0      0      192.168.1.100:22     192.168.1.1:54321
tcp    LISTEN     0      128    0.0.0.0:80           0.0.0.0:*"""

        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        mock_execute.return_value = (0, mock_output, "")

        result = await mcp.call_tool("get_network_connections", {"host": "remote.example.com"})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Active Network Connections" in output
        assert "192.168.1.100" in output
        assert "Total connections: 2" in output

    async def test_get_network_connections_remote_netstat_fallback(self, mocker):
        """Test getting network connections remotely falling back to netstat."""
        mock_output = """Proto Recv-Q Send-Q Local Address           Foreign Address         State
tcp        0      0 192.168.1.100:22        192.168.1.1:54321      ESTABLISHED"""

        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        # ss fails, netstat succeeds
        mock_execute.side_effect = [
            (1, "", "ss not found"),
            (0, mock_output, ""),
        ]

        result = await mcp.call_tool("get_network_connections", {"host": "remote.example.com"})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Active Network Connections" in output
        assert "192.168.1.100" in output
        assert mock_execute.call_count == 2

    async def test_get_network_connections_remote_both_fail(self, mocker):
        """Test getting network connections remotely when both commands fail."""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        mock_execute.side_effect = [
            (1, "", "ss not found"),
            (1, "", "netstat not found"),
        ]

        result = await mcp.call_tool("get_network_connections", {"host": "remote.example.com"})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Error: Neither ss nor netstat command available" in output

    async def test_get_network_connections_remote_ss_empty_output(self, mocker):
        """Test getting network connections remotely with empty ss output."""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        mock_execute.side_effect = [
            (0, None, ""),  # ss returns None
            (1, "", "netstat not found"),
        ]

        result = await mcp.call_tool("get_network_connections", {"host": "remote.example.com"})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Error: Neither ss nor netstat command available" in output

    @pytest.mark.parametrize("laddr_ip,raddr_ip,expectation", LINK_LOCAL_FILTER_CASES_NETWORK)
    async def test_get_network_connections_filters_link_local(self, mocker, laddr_ip, raddr_ip, expectation):
        """Test that connections with link-local addresses are filtered."""
        mock_connections = [
            MockConnection(
                type_=socket.SOCK_STREAM,
                laddr=MockAddr(laddr_ip, 8080),
                raddr=MockAddr(raddr_ip, 54321),
                status="ESTABLISHED",
                pid=1234,
            ),
        ]

        mock_process = MagicMock()
        mock_process.name.return_value = "python3"

        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)
        mocker.patch("linux_mcp_server.tools.network.psutil.Process", return_value=mock_process)

        result = await mcp.call_tool("get_network_connections", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text  # noqa: F841 - used in eval

        assert eval(expectation)

    async def test_get_network_connections_mixed_link_local_filtering(self, mocker):
        """Test filtering with mix of link-local and regular connections."""
        mock_process = MagicMock()
        mock_process.name.return_value = "test"
        mocker.patch(
            "linux_mcp_server.tools.network.psutil.net_connections", return_value=make_mixed_connections_network()
        )
        mocker.patch("linux_mcp_server.tools.network.psutil.Process", return_value=mock_process)

        result = await mcp.call_tool("get_network_connections", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "Total connections: 1 (filtered 2 link-local)" in output
        assert f"{IPV4_ADDR}:80" in output  # The non-filtered connection


class TestGetListeningPorts:
    """Test get_listening_ports function."""

    async def test_get_listening_ports_local_success(self, mocker):
        """Test getting listening ports locally with success."""
        mock_connections = [
            MockConnection(
                type_=socket.SOCK_STREAM,
                laddr=MockAddr("0.0.0.0", 80),
                raddr=None,
                status="LISTEN",
                pid=1234,
            ),
            MockConnection(
                type_=socket.SOCK_DGRAM,
                laddr=MockAddr("0.0.0.0", 53),
                raddr=None,
                status=None,
                pid=5678,
            ),
            MockConnection(
                type_=socket.SOCK_STREAM,
                laddr=MockAddr("127.0.0.1", 8080),
                raddr=MockAddr("127.0.0.1", 54321),
                status="ESTABLISHED",
                pid=9999,
            ),
        ]

        mock_process = MagicMock()
        mock_process.name.return_value = "nginx"

        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)
        mocker.patch("linux_mcp_server.tools.network.psutil.Process", return_value=mock_process)

        result = await mcp.call_tool("get_listening_ports", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Listening Ports" in output
        assert "TCP" in output
        assert "UDP" in output
        assert "0.0.0.0:80" in output
        assert "0.0.0.0:53" in output
        assert "LISTEN" in output
        assert "LISTENING" in output
        assert "1234/nginx" in output
        assert "5678/nginx" in output
        # ESTABLISHED connection should be filtered out
        assert "Total listening ports: 2" in output

    async def test_get_listening_ports_local_no_pid(self, mocker):
        """Test getting listening ports locally without PID."""
        mock_connections = [
            MockConnection(
                type_=socket.SOCK_STREAM,
                laddr=MockAddr("0.0.0.0", 80),
                raddr=None,
                status="LISTEN",
                pid=None,
            ),
        ]

        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)

        result = await mcp.call_tool("get_listening_ports", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Listening Ports" in output
        assert "N/A" in output

    async def test_get_listening_ports_local_no_laddr(self, mocker):
        """Test getting listening ports locally without local address."""
        mock_connections = [
            MockConnection(
                type_=socket.SOCK_STREAM,
                laddr=None,
                raddr=None,
                status="LISTEN",
                pid=1234,
            ),
        ]

        mock_process = MagicMock()
        mock_process.name.return_value = "python3"

        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)
        mocker.patch("linux_mcp_server.tools.network.psutil.Process", return_value=mock_process)

        result = await mcp.call_tool("get_listening_ports", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "N/A" in output

    async def test_get_listening_ports_local_no_status(self, mocker):
        """Test getting listening ports locally without status."""
        mock_connections = [
            MockConnection(
                type_=socket.SOCK_DGRAM,
                laddr=MockAddr("0.0.0.0", 53),
                raddr=None,
                status=None,
                pid=1234,
            ),
        ]

        mock_process = MagicMock()
        mock_process.name.return_value = "dnsmasq"

        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)
        mocker.patch("linux_mcp_server.tools.network.psutil.Process", return_value=mock_process)

        result = await mcp.call_tool("get_listening_ports", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "LISTENING" in output  # Default status for UDP

    async def test_get_listening_ports_local_process_not_found(self, mocker):
        """Test getting listening ports when process is not found."""
        mock_connections = [
            MockConnection(
                type_=socket.SOCK_STREAM,
                laddr=MockAddr("0.0.0.0", 80),
                raddr=None,
                status="LISTEN",
                pid=1234,
            ),
        ]

        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)
        mocker.patch(
            "linux_mcp_server.tools.network.psutil.Process",
            side_effect=psutil.NoSuchProcess(1234),
        )

        result = await mcp.call_tool("get_listening_ports", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "1234" in output  # Should still show PID

    async def test_get_listening_ports_local_access_denied_process(self, mocker):
        """Test getting listening ports when process access is denied."""
        mock_connections = [
            MockConnection(
                type_=socket.SOCK_STREAM,
                laddr=MockAddr("0.0.0.0", 80),
                raddr=None,
                status="LISTEN",
                pid=1234,
            ),
        ]

        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)
        mocker.patch(
            "linux_mcp_server.tools.network.psutil.Process",
            side_effect=psutil.AccessDenied(1234),
        )

        result = await mcp.call_tool("get_listening_ports", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "1234" in output  # Should still show PID

    async def test_get_listening_ports_local_access_denied(self, mocker):
        """Test getting listening ports with permission denied."""
        mocker.patch(
            "linux_mcp_server.tools.network.psutil.net_connections",
            side_effect=psutil.AccessDenied(),
        )

        result = await mcp.call_tool("get_listening_ports", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Permission denied" in output
        assert "elevated privileges" in output

    async def test_get_listening_ports_local_error(self, mocker):
        """Test getting listening ports with general error."""
        mocker.patch(
            "linux_mcp_server.tools.network.psutil.net_connections",
            side_effect=Exception("Network error"),
        )

        result = await mcp.call_tool("get_listening_ports", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Error getting listening ports" in output
        assert "Network error" in output

    async def test_get_listening_ports_remote_ss_success(self, mocker):
        """Test getting listening ports remotely using ss command."""
        mock_output = """Netid  State      Recv-Q Send-Q Local Address:Port   Peer Address:Port
tcp    LISTEN     0      128    0.0.0.0:80           0.0.0.0:*
udp    UNCONN     0      0      0.0.0.0:53           0.0.0.0:*"""

        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        mock_execute.return_value = (0, mock_output, "")

        result = await mcp.call_tool("get_listening_ports", {"host": "remote.example.com"})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Listening Ports" in output
        assert "0.0.0.0:80" in output
        assert "Total listening ports: 2" in output

    async def test_get_listening_ports_remote_netstat_fallback(self, mocker):
        """Test getting listening ports remotely falling back to netstat."""
        mock_output = """Proto Recv-Q Send-Q Local Address           Foreign Address         State
tcp        0      0 0.0.0.0:80              0.0.0.0:*               LISTEN"""

        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        # ss fails, netstat succeeds
        mock_execute.side_effect = [
            (1, "", "ss not found"),
            (0, mock_output, ""),
        ]

        result = await mcp.call_tool("get_listening_ports", {"host": "remote.example.com"})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Listening Ports" in output
        assert "0.0.0.0:80" in output
        assert mock_execute.call_count == 2

    async def test_get_listening_ports_remote_both_fail(self, mocker):
        """Test getting listening ports remotely when both commands fail."""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        mock_execute.side_effect = [
            (1, "", "ss not found"),
            (1, "", "netstat not found"),
        ]

        result = await mcp.call_tool("get_listening_ports", {"host": "remote.example.com"})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Error: Neither ss nor netstat command available" in output

    async def test_get_listening_ports_remote_ss_empty_output(self, mocker):
        """Test getting listening ports remotely with empty ss output."""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        mock_execute.side_effect = [
            (0, None, ""),  # ss returns None
            (1, "", "netstat not found"),
        ]

        result = await mcp.call_tool("get_listening_ports", {"host": "remote.example.com"})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert isinstance(output, str)
        assert "Error: Neither ss nor netstat command available" in output

    @pytest.mark.parametrize(
        "laddr_ip,should_be_filtered",
        [
            (LINK_LOCAL_IPV6, True),  # Link-local should be filtered
            (IPV4_ADDR, False),  # IPv4 should be shown
            (GLOBAL_IPV6, False),  # Global IPv6 should be shown
        ],
        ids=["link-local-filtered", "ipv4-shown", "global-ipv6-shown"],
    )
    async def test_get_listening_ports_filters_link_local(self, mocker, laddr_ip, should_be_filtered):
        """Test that listening ports with link-local addresses are filtered."""
        mock_connections = [
            MockConnection(
                type_=socket.SOCK_STREAM,
                laddr=MockAddr(laddr_ip, 80),
                raddr=None,
                status="LISTEN",
                pid=1234,
            ),
        ]

        mock_process = MagicMock()
        mock_process.name.return_value = "nginx"

        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)
        mocker.patch("linux_mcp_server.tools.network.psutil.Process", return_value=mock_process)

        result = await mcp.call_tool("get_listening_ports", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        if should_be_filtered:
            assert "filtered 1 link-local" in output
            assert "Total listening ports: 0" in output
        else:
            assert "filtered" not in output
            assert "Total listening ports: 1" in output

    async def test_get_listening_ports_mixed_link_local_filtering(self, mocker):
        """Test filtering with mix of link-local and regular listening ports."""
        mock_process = MagicMock()
        mock_process.name.return_value = "test"
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=make_mixed_listening_ports())
        mocker.patch("linux_mcp_server.tools.network.psutil.Process", return_value=mock_process)

        result = await mcp.call_tool("get_listening_ports", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "Total listening ports: 2 (filtered 1 link-local)" in output
        assert f"{IPV4_ADDR}:80" in output
        assert f"{GLOBAL_IPV6}:53" in output
