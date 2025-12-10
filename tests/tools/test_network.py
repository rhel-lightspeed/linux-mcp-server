"""Tests for network diagnostic tools."""

import socket

import psutil
import pytest

from linux_mcp_server.server import mcp
from linux_mcp_server.tools.network import _format_interface_addresses
from linux_mcp_server.tools.network import _format_interface_stats
from linux_mcp_server.tools.network import _format_network_io_stats
from tests.conftest import GLOBAL_IPV6
from tests.conftest import IPV4_ADDR
from tests.conftest import LINK_LOCAL_FILTER_CASES_NETWORK
from tests.conftest import LINK_LOCAL_IPV6
from tests.conftest import make_mixed_connections_network
from tests.conftest import make_mixed_listening_ports
from tests.conftest import MockAddr
from tests.conftest import MockAddress
from tests.conftest import MockConnection
from tests.conftest import MockInterfaceStats
from tests.conftest import MockNetIOCounters


# =============================================================================
# Helper to extract text output from MCP tool results
# =============================================================================
async def call_tool_get_output(tool_name: str, args: dict | None = None) -> str:
    """Call an MCP tool and return the text output."""
    result = await mcp.call_tool(tool_name, args or {})
    assert isinstance(result, tuple) and len(result) == 2
    assert isinstance(result[0], list)
    output = result[0][0].text
    assert isinstance(output, str)
    return output


class TestInterfaceFormatters:
    """Test interface formatting helper functions."""

    @pytest.mark.parametrize(
        "family,address,netmask,broadcast,expected_lines",
        [
            # IPv4 with netmask and broadcast
            (
                socket.AF_INET,
                "192.168.1.100",
                "255.255.255.0",
                "192.168.1.255",
                [
                    "  IPv4 Address: 192.168.1.100",
                    "    Netmask: 255.255.255.0",
                    "    Broadcast: 192.168.1.255",
                ],
            ),
            # IPv4 with netmask only
            (
                socket.AF_INET,
                "192.168.1.100",
                "255.255.255.0",
                None,
                ["  IPv4 Address: 192.168.1.100", "    Netmask: 255.255.255.0"],
            ),
            # IPv4 without netmask/broadcast
            (socket.AF_INET, "192.168.1.100", None, None, ["  IPv4 Address: 192.168.1.100"]),
            # IPv6 global address with netmask
            (
                socket.AF_INET6,
                "2001:db8::1",
                "ffff:ffff:ffff:ffff::",
                None,
                ["  IPv6 Address: 2001:db8::1", "    Netmask: ffff:ffff:ffff:ffff::"],
            ),
            # IPv6 global address without netmask
            (socket.AF_INET6, "2001:db8::1", None, None, ["  IPv6 Address: 2001:db8::1"]),
            # MAC address
            (psutil.AF_LINK, "00:11:22:33:44:55", None, None, ["  MAC Address: 00:11:22:33:44:55"]),
        ],
        ids=[
            "ipv4-full",
            "ipv4-no-broadcast",
            "ipv4-minimal",
            "ipv6-with-netmask",
            "ipv6-minimal",
            "mac-address",
        ],
    )
    def test_format_interface_addresses_single(self, family, address, netmask, broadcast, expected_lines):
        """Test formatting single addresses of different types."""
        addrs = [MockAddress(family, address, netmask, broadcast)]
        result = _format_interface_addresses(addrs)
        assert result == expected_lines

    def test_format_interface_addresses_filters_link_local(self):
        """Test that link-local IPv6 addresses are filtered out."""
        addrs = [
            MockAddress(socket.AF_INET6, "fe80::1", "ffff:ffff:ffff:ffff::", None),
            MockAddress(socket.AF_INET6, "fe80::1%eth0", "ffff:ffff:ffff:ffff::", None),
        ]
        result = _format_interface_addresses(addrs)
        assert result == []

    def test_format_interface_addresses_empty_list(self):
        """Test formatting empty address list."""
        result = _format_interface_addresses([])
        assert result == []

    def test_format_interface_addresses_mixed_types(self):
        """Test formatting mixed address types."""
        addrs = [
            MockAddress(socket.AF_INET, "192.168.1.100", "255.255.255.0", "192.168.1.255"),
            MockAddress(socket.AF_INET6, "2001:db8::1", "ffff:ffff:ffff:ffff::", None),
            MockAddress(socket.AF_INET6, "fe80::1", "ffff:ffff:ffff:ffff::", None),  # Filtered
            MockAddress(psutil.AF_LINK, "00:11:22:33:44:55", None, None),
        ]
        result = _format_interface_addresses(addrs)
        expected = [
            "  IPv4 Address: 192.168.1.100",
            "    Netmask: 255.255.255.0",
            "    Broadcast: 192.168.1.255",
            "  IPv6 Address: 2001:db8::1",
            "    Netmask: ffff:ffff:ffff:ffff::",
            "  MAC Address: 00:11:22:33:44:55",
        ]
        assert result == expected

    def test_format_interface_addresses_unknown_family(self):
        """Test that unknown address families are silently skipped."""
        addrs = [
            MockAddress(socket.AF_INET, "192.168.1.100", "255.255.255.0", None),
            MockAddress(999, "unknown-addr", None, None),  # Unknown family
            MockAddress(psutil.AF_LINK, "00:11:22:33:44:55", None, None),
        ]
        result = _format_interface_addresses(addrs)
        # Unknown family should be skipped, only IPv4 and MAC shown
        expected = [
            "  IPv4 Address: 192.168.1.100",
            "    Netmask: 255.255.255.0",
            "  MAC Address: 00:11:22:33:44:55",
        ]
        assert result == expected

    @pytest.mark.parametrize(
        "isup,speed,mtu,expected_lines",
        [
            (True, 1000, 1500, ["  Status: UP", "  Speed: 1000 Mbps", "  MTU: 1500"]),
            (False, 0, 1500, ["  Status: DOWN", "  Speed: 0 Mbps", "  MTU: 1500"]),
            (True, 10000, 9000, ["  Status: UP", "  Speed: 10000 Mbps", "  MTU: 9000"]),
            (True, 0, 65536, ["  Status: UP", "  Speed: 0 Mbps", "  MTU: 65536"]),
        ],
        ids=["up-1000mbps", "down-no-speed", "up-10gbps", "up-loopback"],
    )
    def test_format_interface_stats(self, isup, speed, mtu, expected_lines):
        """Test formatting interface statistics with various values."""
        stats = MockInterfaceStats(isup=isup, speed=speed, mtu=mtu)
        result = _format_interface_stats(stats)
        assert result == expected_lines

    def test_format_interface_stats_none(self):
        """Test formatting when stats is None."""
        result = _format_interface_stats(None)
        assert result == []

    def test_format_network_io_stats(self):
        """Test formatting network I/O statistics."""
        net_io = MockNetIOCounters()
        result = _format_network_io_stats(net_io)
        expected = [
            "=== Network I/O Statistics (total) ===",
            "Bytes Sent: 100.0MB",
            "Bytes Received: 200.0MB",
            "Packets Sent: 50000",
            "Packets Received: 75000",
            "Errors In: 5",
            "Errors Out: 3",
            "Drops In: 2",
            "Drops Out: 1",
        ]
        assert result == expected

    def test_format_network_io_stats_large_values(self):
        """Test formatting with large byte values."""
        net_io = MockNetIOCounters()
        net_io.bytes_sent = 1024 * 1024 * 1024 * 5  # 5 GB
        net_io.bytes_recv = 1024 * 1024 * 1024 * 10  # 10 GB
        result = _format_network_io_stats(net_io)
        assert "Bytes Sent: 5.0GB" in result
        assert "Bytes Received: 10.0GB" in result


class TestGetNetworkInterfaces:
    """Test get_network_interfaces function."""

    async def test_get_network_interfaces_local_success(self, mocker, mock_net_io):
        """Test getting network interfaces locally with success."""
        mock_net_if_addrs = {
            "eth0": [
                MockAddress(socket.AF_INET, "192.168.1.100", "255.255.255.0", "192.168.1.255"),
                MockAddress(socket.AF_INET6, "2001:db8::1", "ffff:ffff:ffff:ffff::"),
                MockAddress(socket.AF_INET6, "fe80::1%eth0", "ffff:ffff:ffff:ffff::"),  # filtered
                MockAddress(psutil.AF_LINK, "00:11:22:33:44:55"),
            ],
            "lo": [MockAddress(socket.AF_INET, "127.0.0.1", "255.0.0.0")],
        }
        mock_net_if_stats = {
            "eth0": MockInterfaceStats(isup=True, speed=1000, mtu=1500),
            "lo": MockInterfaceStats(isup=True, speed=0, mtu=65536),
        }

        mocker.patch("linux_mcp_server.tools.network.psutil.net_if_addrs", return_value=mock_net_if_addrs)
        mocker.patch("linux_mcp_server.tools.network.psutil.net_if_stats", return_value=mock_net_if_stats)
        mocker.patch("linux_mcp_server.tools.network.psutil.net_io_counters", return_value=mock_net_io)

        output = await call_tool_get_output("get_network_interfaces")

        # Interface names and addresses
        assert all(s in output for s in ["eth0", "lo", "192.168.1.100", "127.0.0.1", "2001:db8::1"])
        assert "fe80::" not in output  # Link-local filtered
        assert "00:11:22:33:44:55" in output
        # Stats
        assert all(s in output for s in ["Status: UP", "Speed: 1000 Mbps", "MTU: 1500"])
        # I/O stats
        assert all(s in output for s in ["Network I/O Statistics", "Bytes Sent", "Bytes Received"])
        assert all(s in output for s in ["Packets Sent: 50000", "Errors In: 5", "Drops Out: 1"])

    @pytest.mark.parametrize(
        "addrs,stats,expected_in,expected_not_in",
        [
            # No optional fields (netmask/broadcast)
            (
                {"eth0": [MockAddress(socket.AF_INET, "192.168.1.100")]},
                {"eth0": MockInterfaceStats(isup=False)},
                ["eth0", "192.168.1.100", "Status: DOWN"],
                [],
            ),
            # Interface not in stats
            (
                {"eth0": [MockAddress(socket.AF_INET, "192.168.1.100", "255.255.255.0")]},
                {},
                ["eth0", "192.168.1.100"],
                ["Status:"],
            ),
        ],
        ids=["no-optional-fields", "no-stats"],
    )
    async def test_get_network_interfaces_local_variations(
        self, mocker, mock_net_io, addrs, stats, expected_in, expected_not_in
    ):
        """Test interface display with various field combinations."""
        mocker.patch("linux_mcp_server.tools.network.psutil.net_if_addrs", return_value=addrs)
        mocker.patch("linux_mcp_server.tools.network.psutil.net_if_stats", return_value=stats)
        mocker.patch("linux_mcp_server.tools.network.psutil.net_io_counters", return_value=mock_net_io)

        output = await call_tool_get_output("get_network_interfaces")

        for s in expected_in:
            assert s in output
        for s in expected_not_in:
            assert s not in output

    async def test_get_network_interfaces_local_error(self, mocker):
        """Test getting network interfaces locally with error."""
        mocker.patch(
            "linux_mcp_server.tools.network.psutil.net_if_addrs",
            side_effect=Exception("Network error"),
        )

        output = await call_tool_get_output("get_network_interfaces")
        assert "Error getting network interface information" in output
        assert "Network error" in output

    @pytest.mark.parametrize(
        "responses,expected_in,expected_call_count",
        [
            # All commands succeed
            (
                [
                    (0, "eth0             UP             192.168.1.100/24", ""),
                    (0, "1: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500\n    inet 192.168.1.100/24", ""),
                    (0, "eth0: 1024 2048 0 0 0 0 0 0", ""),
                ],
                ["Network Interfaces", "eth0", "192.168.1.100", "Detailed Interface Information"],
                3,
            ),
            # Partial failure (first succeeds)
            (
                [(0, "eth0             UP             192.168.1.100/24", ""), (1, "", ""), (1, "", "")],
                ["Network Interfaces", "eth0"],
                3,
            ),
            # All fail
            ([(1, None, ""), (1, None, ""), (1, None, "")], ["Network Interfaces"], 3),
        ],
        ids=["all-success", "partial-failure", "all-empty"],
    )
    async def test_get_network_interfaces_remote(self, mocker, responses, expected_in, expected_call_count):
        """Test remote interface retrieval with various response scenarios."""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        mock_execute.side_effect = responses

        output = await call_tool_get_output("get_network_interfaces", {"host": "remote.example.com"})

        for s in expected_in:
            assert s in output
        assert mock_execute.call_count == expected_call_count


class TestGetNetworkConnections:
    """Test get_network_connections function."""

    async def test_get_network_connections_local_success(self, mocker, mock_process):
        """Test getting network connections locally with success."""
        mock_connections = [
            MockConnection(
                type_=socket.SOCK_STREAM,
                laddr=MockAddr("127.0.0.1", 8080),
                raddr=MockAddr("127.0.0.1", 54321),
                status="ESTABLISHED",
                pid=1234,
            ),
            MockConnection(type_=socket.SOCK_DGRAM, laddr=MockAddr("0.0.0.0", 53), raddr=None, status=None, pid=5678),
        ]
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)

        output = await call_tool_get_output("get_network_connections")

        assert all(s in output for s in ["Active Network Connections", "TCP", "UDP"])
        assert all(s in output for s in ["127.0.0.1:8080", "127.0.0.1:54321", "0.0.0.0:53"])
        assert all(s in output for s in ["ESTABLISHED", "1234/python3", "5678/python3", "Total connections: 2"])

    @pytest.mark.parametrize(
        "connections,expected_in",
        [
            # No PID
            (
                [
                    MockConnection(
                        type_=socket.SOCK_STREAM,
                        laddr=MockAddr("127.0.0.1", 8080),
                        raddr=MockAddr("127.0.0.1", 54321),
                        status="ESTABLISHED",
                        pid=None,
                    )
                ],
                ["Active Network Connections", "N/A"],
            ),
            # No addresses
            (
                [MockConnection(type_=socket.SOCK_STREAM, laddr=None, raddr=None, status=None, pid=1234)],
                ["N/A"],
            ),
        ],
        ids=["no-pid", "no-addresses"],
    )
    async def test_get_network_connections_local_edge_cases(self, mocker, mock_process, connections, expected_in):
        """Test connection display edge cases."""
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=connections)
        output = await call_tool_get_output("get_network_connections")
        for s in expected_in:
            assert s in output

    @pytest.mark.parametrize(
        "exception,expected_in",
        [
            (psutil.NoSuchProcess(1234), ["1234"]),
            (psutil.AccessDenied(1234), ["1234"]),
        ],
        ids=["process-not-found", "process-access-denied"],
    )
    async def test_get_network_connections_process_errors(self, mocker, exception, expected_in):
        """Test graceful handling of process lookup errors."""
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
        mocker.patch("linux_mcp_server.tools.network.psutil.Process", side_effect=exception)

        output = await call_tool_get_output("get_network_connections")
        for s in expected_in:
            assert s in output

    @pytest.mark.parametrize(
        "exception,expected_in",
        [
            (psutil.AccessDenied(), ["Permission denied", "elevated privileges"]),
            (Exception("Network error"), ["Error getting network connections", "Network error"]),
        ],
        ids=["access-denied", "general-error"],
    )
    async def test_get_network_connections_errors(self, mocker, exception, expected_in):
        """Test error handling for net_connections failures."""
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", side_effect=exception)
        output = await call_tool_get_output("get_network_connections")
        for s in expected_in:
            assert s in output

    @pytest.mark.parametrize(
        "responses,expected_in,expected_call_count",
        [
            # ss succeeds
            (
                [(0, "Netid State\ntcp ESTAB 192.168.1.100:22 192.168.1.1:54321\ntcp LISTEN 0.0.0.0:80", "")],
                ["Active Network Connections", "192.168.1.100", "Total connections: 2"],
                1,
            ),
            # ss fails, netstat succeeds
            (
                [(1, "", "ss not found"), (0, "Proto\ntcp 192.168.1.100:22 ESTABLISHED", "")],
                ["Active Network Connections", "192.168.1.100"],
                2,
            ),
            # Both fail
            ([(1, "", "ss not found"), (1, "", "netstat not found")], ["Error: Neither ss nor netstat"], 2),
            # ss returns None
            ([(0, None, ""), (1, "", "netstat not found")], ["Error: Neither ss nor netstat"], 2),
        ],
        ids=["ss-success", "netstat-fallback", "both-fail", "ss-empty"],
    )
    async def test_get_network_connections_remote(self, mocker, responses, expected_in, expected_call_count):
        """Test remote connection retrieval with various response scenarios."""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        mock_execute.side_effect = responses

        output = await call_tool_get_output("get_network_connections", {"host": "remote.example.com"})

        for s in expected_in:
            assert s in output
        assert mock_execute.call_count == expected_call_count

    @pytest.mark.parametrize("laddr_ip,raddr_ip,expectation", LINK_LOCAL_FILTER_CASES_NETWORK)
    async def test_get_network_connections_filters_link_local(
        self, mocker, mock_process, laddr_ip, raddr_ip, expectation
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
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)

        output = await call_tool_get_output("get_network_connections")  # noqa: F841 - used in eval
        assert eval(expectation)

    async def test_get_network_connections_mixed_link_local_filtering(self, mocker, mock_process):
        """Test filtering with mix of link-local and regular connections."""
        mocker.patch(
            "linux_mcp_server.tools.network.psutil.net_connections", return_value=make_mixed_connections_network()
        )

        output = await call_tool_get_output("get_network_connections")

        assert "Total connections: 1 (filtered 2 link-local)" in output
        assert f"{IPV4_ADDR}:80" in output


class TestGetListeningPorts:
    """Test get_listening_ports function."""

    async def test_get_listening_ports_local_success(self, mocker, mock_process):
        """Test getting listening ports locally with success."""
        mock_process.name.return_value = "nginx"
        mock_connections = [
            MockConnection(
                type_=socket.SOCK_STREAM, laddr=MockAddr("0.0.0.0", 80), raddr=None, status="LISTEN", pid=1234
            ),
            MockConnection(type_=socket.SOCK_DGRAM, laddr=MockAddr("0.0.0.0", 53), raddr=None, status=None, pid=5678),
            MockConnection(
                type_=socket.SOCK_STREAM,
                laddr=MockAddr("127.0.0.1", 8080),
                raddr=MockAddr("127.0.0.1", 54321),
                status="ESTABLISHED",
                pid=9999,
            ),  # filtered out
        ]
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)

        output = await call_tool_get_output("get_listening_ports")

        assert all(s in output for s in ["Listening Ports", "TCP", "UDP", "0.0.0.0:80", "0.0.0.0:53"])
        assert all(s in output for s in ["LISTEN", "LISTENING", "1234/nginx", "5678/nginx"])
        assert "Total listening ports: 2" in output

    @pytest.mark.parametrize(
        "connections,expected_in",
        [
            # No PID
            (
                [
                    MockConnection(
                        type_=socket.SOCK_STREAM, laddr=MockAddr("0.0.0.0", 80), raddr=None, status="LISTEN", pid=None
                    )
                ],
                ["Listening Ports", "N/A"],
            ),
            # No local address
            ([MockConnection(type_=socket.SOCK_STREAM, laddr=None, raddr=None, status="LISTEN", pid=1234)], ["N/A"]),
            # No status (UDP defaults to LISTENING)
            (
                [
                    MockConnection(
                        type_=socket.SOCK_DGRAM, laddr=MockAddr("0.0.0.0", 53), raddr=None, status=None, pid=1234
                    )
                ],
                ["LISTENING"],
            ),
        ],
        ids=["no-pid", "no-laddr", "no-status-udp"],
    )
    async def test_get_listening_ports_local_edge_cases(self, mocker, mock_process, connections, expected_in):
        """Test listening port display edge cases."""
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=connections)
        output = await call_tool_get_output("get_listening_ports")
        for s in expected_in:
            assert s in output

    @pytest.mark.parametrize(
        "exception,expected_in",
        [
            (psutil.NoSuchProcess(1234), ["1234"]),
            (psutil.AccessDenied(1234), ["1234"]),
        ],
        ids=["process-not-found", "process-access-denied"],
    )
    async def test_get_listening_ports_process_errors(self, mocker, exception, expected_in):
        """Test graceful handling of process lookup errors."""
        mock_connections = [
            MockConnection(
                type_=socket.SOCK_STREAM, laddr=MockAddr("0.0.0.0", 80), raddr=None, status="LISTEN", pid=1234
            )
        ]
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)
        mocker.patch("linux_mcp_server.tools.network.psutil.Process", side_effect=exception)

        output = await call_tool_get_output("get_listening_ports")
        for s in expected_in:
            assert s in output

    @pytest.mark.parametrize(
        "exception,expected_in",
        [
            (psutil.AccessDenied(), ["Permission denied", "elevated privileges"]),
            (Exception("Network error"), ["Error getting listening ports", "Network error"]),
        ],
        ids=["access-denied", "general-error"],
    )
    async def test_get_listening_ports_errors(self, mocker, exception, expected_in):
        """Test error handling for net_connections failures."""
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", side_effect=exception)
        output = await call_tool_get_output("get_listening_ports")
        for s in expected_in:
            assert s in output

    @pytest.mark.parametrize(
        "responses,expected_in,expected_call_count",
        [
            # ss succeeds
            (
                [(0, "Netid State\ntcp LISTEN 0.0.0.0:80\nudp UNCONN 0.0.0.0:53", "")],
                ["Listening Ports", "0.0.0.0:80", "Total listening ports: 2"],
                1,
            ),
            # ss fails, netstat succeeds
            ([(1, "", "ss not found"), (0, "Proto\ntcp 0.0.0.0:80 LISTEN", "")], ["Listening Ports", "0.0.0.0:80"], 2),
            # Both fail
            ([(1, "", "ss not found"), (1, "", "netstat not found")], ["Error: Neither ss nor netstat"], 2),
            # ss returns None
            ([(0, None, ""), (1, "", "netstat not found")], ["Error: Neither ss nor netstat"], 2),
        ],
        ids=["ss-success", "netstat-fallback", "both-fail", "ss-empty"],
    )
    async def test_get_listening_ports_remote(self, mocker, responses, expected_in, expected_call_count):
        """Test remote listening port retrieval with various response scenarios."""
        mock_execute = mocker.patch("linux_mcp_server.tools.network.execute_command")
        mock_execute.side_effect = responses

        output = await call_tool_get_output("get_listening_ports", {"host": "remote.example.com"})

        for s in expected_in:
            assert s in output
        assert mock_execute.call_count == expected_call_count

    @pytest.mark.parametrize(
        "laddr_ip,should_be_filtered",
        [
            (LINK_LOCAL_IPV6, True),
            (IPV4_ADDR, False),
            (GLOBAL_IPV6, False),
        ],
        ids=["link-local-filtered", "ipv4-shown", "global-ipv6-shown"],
    )
    async def test_get_listening_ports_filters_link_local(self, mocker, mock_process, laddr_ip, should_be_filtered):
        """Test that listening ports with link-local addresses are filtered."""
        mock_connections = [
            MockConnection(
                type_=socket.SOCK_STREAM, laddr=MockAddr(laddr_ip, 80), raddr=None, status="LISTEN", pid=1234
            )
        ]
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=mock_connections)

        output = await call_tool_get_output("get_listening_ports")

        if should_be_filtered:
            assert "filtered 1 link-local" in output
            assert "Total listening ports: 0" in output
        else:
            assert "filtered" not in output
            assert "Total listening ports: 1" in output

    async def test_get_listening_ports_mixed_link_local_filtering(self, mocker, mock_process):
        """Test filtering with mix of link-local and regular listening ports."""
        mocker.patch("linux_mcp_server.tools.network.psutil.net_connections", return_value=make_mixed_listening_ports())

        output = await call_tool_get_output("get_listening_ports")

        assert "Total listening ports: 2 (filtered 1 link-local)" in output
        assert f"{IPV4_ADDR}:80" in output
        assert f"{GLOBAL_IPV6}:53" in output
