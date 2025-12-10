"""Tests for network diagnostic tools."""

import socket

import psutil
import pytest

from linux_mcp_server.server import mcp
from linux_mcp_server.tools.network import _build_connection_table_header
from linux_mcp_server.tools.network import _format_connection_line
from linux_mcp_server.tools.network import _should_filter_connection
from tests.conftest import GLOBAL_IPV6
from tests.conftest import IPV4_ADDR
from tests.conftest import LINK_LOCAL_FILTER_CASES_NETWORK
from tests.conftest import LINK_LOCAL_IPV6
from tests.conftest import make_mixed_connections_network
from tests.conftest import make_mixed_listening_ports
from tests.conftest import MockAddr
from tests.conftest import MockConnection


def extract_tool_output(result) -> str:
    """Extract text output from MCP tool result tuple."""
    assert isinstance(result, tuple) and len(result) == 2
    assert isinstance(result[0], list)
    return result[0][0].text


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


class TestConnectionFormattingHelpers:
    """Test helper functions for connection formatting and filtering."""

    @pytest.mark.parametrize(
        "laddr_ip,raddr_ip,expected",
        [
            (LINK_LOCAL_IPV6, IPV4_ADDR, True),  # Link-local laddr -> filter
            (IPV4_ADDR, LINK_LOCAL_IPV6, True),  # Link-local raddr -> filter
            (LINK_LOCAL_IPV6, LINK_LOCAL_IPV6, True),  # Both link-local -> filter
            (IPV4_ADDR, GLOBAL_IPV6, False),  # No link-local -> don't filter
            (GLOBAL_IPV6, IPV4_ADDR, False),  # Global IPv6 -> don't filter
        ],
        ids=[
            "laddr-link-local",
            "raddr-link-local",
            "both-link-local",
            "no-link-local",
            "global-ipv6",
        ],
    )
    def test_should_filter_connection(self, laddr_ip, raddr_ip, expected):
        """Test filtering logic for link-local addresses."""
        conn = MockConnection(
            type_=socket.SOCK_STREAM,
            laddr=MockAddr(laddr_ip, 8080),
            raddr=MockAddr(raddr_ip, 54321),
            status="ESTABLISHED",
            pid=1234,
        )
        assert _should_filter_connection(conn) == expected

    @pytest.mark.parametrize(
        "laddr,raddr,expected",
        [
            (None, MockAddr(IPV4_ADDR, 8080), False),  # No laddr -> don't filter
            (MockAddr(IPV4_ADDR, 8080), None, False),  # No raddr -> don't filter
            (None, None, False),  # No addresses -> don't filter
        ],
        ids=["no-laddr", "no-raddr", "no-addresses"],
    )
    def test_should_filter_connection_missing_addresses(self, laddr, raddr, expected):
        """Test filtering with missing addresses."""
        conn = MockConnection(
            type_=socket.SOCK_STREAM,
            laddr=laddr,
            raddr=raddr,
            status="ESTABLISHED",
            pid=1234,
        )
        assert _should_filter_connection(conn) == expected

    @pytest.mark.parametrize(
        "include_remote,expect_remote_col,separator_width",
        [
            (True, True, 110),
            (False, False, 80),
        ],
        ids=["with-remote", "without-remote"],
    )
    def test_build_connection_table_header(self, include_remote, expect_remote_col, separator_width):
        """Test building table header with/without remote address column."""
        result = _build_connection_table_header(include_remote=include_remote)
        assert len(result) == 2
        assert "Proto" in result[0]
        assert "Local Address" in result[0]
        assert ("Remote Address" in result[0]) == expect_remote_col
        assert "Status" in result[0]
        assert "PID/Program" in result[0]
        assert len(result[1]) == separator_width

    @pytest.mark.parametrize(
        "type_,expected_proto",
        [
            (socket.SOCK_STREAM, "TCP"),
            (socket.SOCK_DGRAM, "UDP"),
        ],
        ids=["tcp", "udp"],
    )
    def test_format_connection_line_protocol(self, type_, expected_proto, mock_network_process):
        """Test protocol detection (TCP/UDP)."""
        mock_network_process("test")
        conn = MockConnection(
            type_=type_,
            laddr=MockAddr(IPV4_ADDR, 8080),
            raddr=MockAddr(IPV4_ADDR, 54321),
            status="ESTABLISHED",
            pid=1234,
        )
        result = _format_connection_line(conn, include_remote=True)
        assert result.startswith(expected_proto)

    @pytest.mark.parametrize(
        "laddr,raddr,status,pid,include_remote,expected_in,expected_not_in",
        [
            (
                MockAddr("192.168.1.100", 8080),
                MockAddr("10.0.0.5", 54321),
                "ESTABLISHED",
                1234,
                True,
                ["TCP", "192.168.1.100:8080", "10.0.0.5:54321", "ESTABLISHED", "1234/test"],
                [],
            ),
            (
                MockAddr("0.0.0.0", 80),
                None,
                "LISTEN",
                5678,
                False,
                ["TCP", "0.0.0.0:80", "LISTEN", "5678/test"],
                ["10.0.0.5:54321"],  # No remote address
            ),
        ],
        ids=["with-remote", "without-remote"],
    )
    def test_format_connection_line_include_remote(
        self, mock_network_process, laddr, raddr, status, pid, include_remote, expected_in, expected_not_in
    ):
        """Test formatting connection line with/without remote address."""
        mock_network_process("test")
        conn = MockConnection(type_=socket.SOCK_STREAM, laddr=laddr, raddr=raddr, status=status, pid=pid)
        result = _format_connection_line(conn, include_remote=include_remote)
        for expected in expected_in:
            assert expected in result
        for not_expected in expected_not_in:
            assert not_expected not in result

    @pytest.mark.parametrize(
        "laddr,raddr,status,include_remote,expected_laddr,expected_raddr,expected_status",
        [
            (None, None, None, True, "N/A", "N/A", "N/A"),  # All None with remote
            (None, None, None, False, "N/A", None, "LISTENING"),  # All None without remote
            (
                MockAddr(IPV4_ADDR, 8080),
                None,
                "LISTEN",
                True,
                f"{IPV4_ADDR}:8080",
                "N/A",
                "LISTEN",
            ),  # No raddr
            (
                MockAddr(IPV4_ADDR, 8080),
                None,
                None,
                False,
                f"{IPV4_ADDR}:8080",
                None,
                "LISTENING",
            ),  # UDP listening
        ],
        ids=["all-none-with-remote", "all-none-without-remote", "no-raddr", "udp-listening"],
    )
    def test_format_connection_line_edge_cases(
        self,
        mocker,
        laddr,
        raddr,
        status,
        include_remote,
        expected_laddr,
        expected_raddr,
        expected_status,
    ):
        """Test edge cases for connection formatting."""
        conn = MockConnection(
            type_=socket.SOCK_DGRAM,
            laddr=laddr,
            raddr=raddr,
            status=status,
            pid=None,
        )
        result = _format_connection_line(conn, include_remote=include_remote)
        assert expected_laddr in result
        assert expected_status in result
        if include_remote and expected_raddr:
            assert expected_raddr in result
        assert "N/A" in result  # PID should be N/A

    def test_format_connection_line_ipv6(self, mock_network_process):
        """Test formatting with IPv6 addresses."""
        mock_network_process("test")
        conn = MockConnection(
            type_=socket.SOCK_STREAM,
            laddr=MockAddr(GLOBAL_IPV6, 8080),
            raddr=MockAddr(GLOBAL_IPV6, 54321),
            status="ESTABLISHED",
            pid=9999,
        )
        result = _format_connection_line(conn, include_remote=True)
        assert f"{GLOBAL_IPV6}:8080" in result
        assert f"{GLOBAL_IPV6}:54321" in result


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

    async def test_get_network_connections_local_success(self, mocker, mock_network_process):
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
        mock_network_process("python3")
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)

        output = extract_tool_output(await mcp.call_tool("get_network_connections", {}))
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

        output = extract_tool_output(await mcp.call_tool("get_network_connections", {}))
        assert "Active Network Connections" in output
        assert "N/A" in output

    async def test_get_network_connections_local_no_addresses(self, mocker, mock_network_process):
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
        mock_network_process("python3")
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)

        output = extract_tool_output(await mcp.call_tool("get_network_connections", {}))
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
        mocker.patch("linux_mcp_server.tools.network.psutil.Process", side_effect=psutil.NoSuchProcess(1234))

        output = extract_tool_output(await mcp.call_tool("get_network_connections", {}))
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
        mocker.patch("linux_mcp_server.tools.network.psutil.Process", side_effect=psutil.AccessDenied(1234))

        output = extract_tool_output(await mcp.call_tool("get_network_connections", {}))
        assert "1234" in output  # Should still show PID

    async def test_get_network_connections_local_access_denied(self, mocker):
        """Test getting network connections with permission denied."""
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", side_effect=psutil.AccessDenied())

        output = extract_tool_output(await mcp.call_tool("get_network_connections", {}))
        assert "Permission denied" in output
        assert "elevated privileges" in output

    async def test_get_network_connections_local_error(self, mocker):
        """Test getting network connections with general error."""
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", side_effect=Exception("Network error"))

        output = extract_tool_output(await mcp.call_tool("get_network_connections", {}))
        assert "Error getting network connections" in output
        assert "Network error" in output

    async def test_get_network_connections_remote_ss_success(self, mocker):
        """Test getting network connections remotely using ss command."""
        mock_output = """Netid  State      Recv-Q Send-Q Local Address:Port   Peer Address:Port
tcp    ESTAB      0      0      192.168.1.100:22     192.168.1.1:54321
tcp    LISTEN     0      128    0.0.0.0:80           0.0.0.0:*"""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        mock_execute.return_value = (0, mock_output, "")

        output = extract_tool_output(await mcp.call_tool("get_network_connections", {"host": "remote.example.com"}))
        assert "Active Network Connections" in output
        assert "192.168.1.100" in output
        assert "Total connections: 2" in output

    async def test_get_network_connections_remote_netstat_fallback(self, mocker):
        """Test getting network connections remotely falling back to netstat."""
        mock_output = """Proto Recv-Q Send-Q Local Address           Foreign Address         State
tcp        0      0 192.168.1.100:22        192.168.1.1:54321      ESTABLISHED"""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        mock_execute.side_effect = [(1, "", "ss not found"), (0, mock_output, "")]

        output = extract_tool_output(await mcp.call_tool("get_network_connections", {"host": "remote.example.com"}))
        assert "Active Network Connections" in output
        assert "192.168.1.100" in output
        assert mock_execute.call_count == 2

    async def test_get_network_connections_remote_both_fail(self, mocker):
        """Test getting network connections remotely when both commands fail."""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        mock_execute.side_effect = [(1, "", "ss not found"), (1, "", "netstat not found")]

        output = extract_tool_output(await mcp.call_tool("get_network_connections", {"host": "remote.example.com"}))
        assert "Error: Neither ss nor netstat command available" in output

    async def test_get_network_connections_remote_ss_empty_output(self, mocker):
        """Test getting network connections remotely with empty ss output."""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        mock_execute.side_effect = [(0, None, ""), (1, "", "netstat not found")]

        output = extract_tool_output(await mcp.call_tool("get_network_connections", {"host": "remote.example.com"}))
        assert "Error: Neither ss nor netstat command available" in output

    @pytest.mark.parametrize("laddr_ip,raddr_ip,expectation", LINK_LOCAL_FILTER_CASES_NETWORK)
    async def test_get_network_connections_filters_link_local(
        self, mocker, mock_network_process, laddr_ip, raddr_ip, expectation
    ):
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
        mock_network_process("python3")
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)

        output = extract_tool_output(await mcp.call_tool("get_network_connections", {}))  # noqa: F841 - used in eval
        assert eval(expectation)

    async def test_get_network_connections_mixed_link_local_filtering(self, mocker, mock_network_process):
        """Test filtering with mix of link-local and regular connections."""
        mock_network_process("test")
        mocker.patch(
            "linux_mcp_server.tools.network.psutil.net_connections", return_value=make_mixed_connections_network()
        )

        output = extract_tool_output(await mcp.call_tool("get_network_connections", {}))
        assert "Total connections: 1 (filtered 2 link-local)" in output
        assert f"{IPV4_ADDR}:80" in output  # The non-filtered connection


class TestGetListeningPorts:
    """Test get_listening_ports function."""

    async def test_get_listening_ports_local_success(self, mocker, mock_network_process):
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
        mock_network_process("nginx")
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)

        output = extract_tool_output(await mcp.call_tool("get_listening_ports", {}))
        assert "Listening Ports" in output
        assert "TCP" in output
        assert "UDP" in output
        assert "0.0.0.0:80" in output
        assert "0.0.0.0:53" in output
        assert "LISTEN" in output
        assert "LISTENING" in output
        assert "1234/nginx" in output
        assert "5678/nginx" in output
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

        output = extract_tool_output(await mcp.call_tool("get_listening_ports", {}))
        assert "Listening Ports" in output
        assert "N/A" in output

    async def test_get_listening_ports_local_no_laddr(self, mocker, mock_network_process):
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
        mock_network_process("python3")
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)

        output = extract_tool_output(await mcp.call_tool("get_listening_ports", {}))
        assert "N/A" in output

    async def test_get_listening_ports_local_no_status(self, mocker, mock_network_process):
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
        mock_network_process("dnsmasq")
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)

        output = extract_tool_output(await mcp.call_tool("get_listening_ports", {}))
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
        mocker.patch("linux_mcp_server.tools.network.psutil.Process", side_effect=psutil.NoSuchProcess(1234))

        output = extract_tool_output(await mcp.call_tool("get_listening_ports", {}))
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
        mocker.patch("linux_mcp_server.tools.network.psutil.Process", side_effect=psutil.AccessDenied(1234))

        output = extract_tool_output(await mcp.call_tool("get_listening_ports", {}))
        assert "1234" in output  # Should still show PID

    async def test_get_listening_ports_local_access_denied(self, mocker):
        """Test getting listening ports with permission denied."""
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", side_effect=psutil.AccessDenied())

        output = extract_tool_output(await mcp.call_tool("get_listening_ports", {}))
        assert "Permission denied" in output
        assert "elevated privileges" in output

    async def test_get_listening_ports_local_error(self, mocker):
        """Test getting listening ports with general error."""
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", side_effect=Exception("Network error"))

        output = extract_tool_output(await mcp.call_tool("get_listening_ports", {}))
        assert "Error getting listening ports" in output
        assert "Network error" in output

    async def test_get_listening_ports_remote_ss_success(self, mocker):
        """Test getting listening ports remotely using ss command."""
        mock_output = """Netid  State      Recv-Q Send-Q Local Address:Port   Peer Address:Port
tcp    LISTEN     0      128    0.0.0.0:80           0.0.0.0:*
udp    UNCONN     0      0      0.0.0.0:53           0.0.0.0:*"""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        mock_execute.return_value = (0, mock_output, "")

        output = extract_tool_output(await mcp.call_tool("get_listening_ports", {"host": "remote.example.com"}))
        assert "Listening Ports" in output
        assert "0.0.0.0:80" in output
        assert "Total listening ports: 2" in output

    async def test_get_listening_ports_remote_netstat_fallback(self, mocker):
        """Test getting listening ports remotely falling back to netstat."""
        mock_output = """Proto Recv-Q Send-Q Local Address           Foreign Address         State
tcp        0      0 0.0.0.0:80              0.0.0.0:*               LISTEN"""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        mock_execute.side_effect = [(1, "", "ss not found"), (0, mock_output, "")]

        output = extract_tool_output(await mcp.call_tool("get_listening_ports", {"host": "remote.example.com"}))
        assert "Listening Ports" in output
        assert "0.0.0.0:80" in output
        assert mock_execute.call_count == 2

    async def test_get_listening_ports_remote_both_fail(self, mocker):
        """Test getting listening ports remotely when both commands fail."""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        mock_execute.side_effect = [(1, "", "ss not found"), (1, "", "netstat not found")]

        output = extract_tool_output(await mcp.call_tool("get_listening_ports", {"host": "remote.example.com"}))
        assert "Error: Neither ss nor netstat command available" in output

    async def test_get_listening_ports_remote_ss_empty_output(self, mocker):
        """Test getting listening ports remotely with empty ss output."""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        mock_execute.side_effect = [(0, None, ""), (1, "", "netstat not found")]

        output = extract_tool_output(await mcp.call_tool("get_listening_ports", {"host": "remote.example.com"}))
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
    async def test_get_listening_ports_filters_link_local(
        self, mocker, mock_network_process, laddr_ip, should_be_filtered
    ):
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
        mock_network_process("nginx")
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)

        output = extract_tool_output(await mcp.call_tool("get_listening_ports", {}))
        if should_be_filtered:
            assert "filtered 1 link-local" in output
            assert "Total listening ports: 0" in output
        else:
            assert "filtered" not in output
            assert "Total listening ports: 1" in output

    async def test_get_listening_ports_mixed_link_local_filtering(self, mocker, mock_network_process):
        """Test filtering with mix of link-local and regular listening ports."""
        mock_network_process("test")
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=make_mixed_listening_ports())

        output = extract_tool_output(await mcp.call_tool("get_listening_ports", {}))

        assert "Total listening ports: 2 (filtered 1 link-local)" in output
        assert f"{IPV4_ADDR}:80" in output
        assert f"{GLOBAL_IPV6}:53" in output
