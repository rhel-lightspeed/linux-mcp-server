"""Tests for network diagnostic tools."""

import pytest

from linux_mcp_server.tools import network


@pytest.fixture
def mock_execute(mocker):
    """Mock execute_with_fallback for network module."""
    return mocker.patch.object(network, "execute_with_fallback")


class TestGetNetworkInterfaces:
    """Test get_network_interfaces function."""

    @pytest.mark.parametrize(
        ("host", "responses", "expected_interfaces"),
        [
            pytest.param(
                None,
                [
                    (
                        0,
                        "eth0             UP             192.168.1.100/24\nlo               UNKNOWN        127.0.0.1/8",
                        "",
                    ),
                    (
                        0,
                        "Inter-|   Receive                                                |  Transmit\n face |bytes    packets\n    lo: 1234567   12345    0    0    0     0          0         0  1234567   12345    0    0    0     0       0          0\n  eth0: 9876543   98765   10    5    0     0          0       100  5432100   54321   20   10    0     0       0          0",
                        "",
                    ),
                ],
                ["eth0", "lo"],
                id="local",
            ),
            pytest.param(
                "remote.example.com",
                [
                    (0, "eth0             UP             192.168.1.100/24", ""),
                    (0, "eth0: 1024 2048 0 0 0 0 0 0 512 1024 0 0 0 0 0 0", ""),
                ],
                ["eth0"],
                id="remote",
            ),
        ],
    )
    async def test_get_network_interfaces_success(self, mock_execute, host, responses, expected_interfaces):
        """Test getting network interfaces with success."""
        mock_execute.side_effect = responses

        result = await network.get_network_interfaces(host=host)

        assert isinstance(result, str)
        assert "Network Interfaces" in result
        for iface in expected_interfaces:
            assert iface in result
        assert mock_execute.call_count == 2

    async def test_get_network_interfaces_partial_failure(self, mock_execute):
        """Test getting network interfaces with partial failures."""
        mock_execute.side_effect = [
            (0, "eth0             UP             192.168.1.100/24", ""),
            (1, "", "Command failed"),
        ]

        result = await network.get_network_interfaces()

        assert isinstance(result, str)
        assert "Network Interfaces" in result
        assert "eth0" in result

    async def test_get_network_interfaces_error(self, mock_execute):
        """Test getting network interfaces with error."""
        mock_execute.side_effect = Exception("Network error")

        result = await network.get_network_interfaces()

        assert isinstance(result, str)
        assert "Error getting network interface information" in result
        assert "Network error" in result


class TestGetNetworkConnections:
    """Test get_network_connections function."""

    @pytest.mark.parametrize(
        ("host", "mock_output", "expected_content"),
        [
            pytest.param(
                None,
                """Netid  State      Recv-Q Send-Q Local Address:Port   Peer Address:Port
tcp    ESTAB      0      0      192.168.1.100:22     192.168.1.1:54321
tcp    LISTEN     0      128    0.0.0.0:80           0.0.0.0:*""",
                ["192.168.1.100", "Total connections: 2"],
                id="local",
            ),
            pytest.param(
                "remote.host",
                """Netid  State      Recv-Q Send-Q Local Address:Port   Peer Address:Port
tcp    ESTAB      0      0      10.0.0.5:443         10.0.0.1:12345""",
                ["10.0.0.5"],
                id="remote",
            ),
        ],
    )
    async def test_get_network_connections_success(self, mock_execute, host, mock_output, expected_content):
        """Test getting network connections with success."""
        mock_execute.return_value = (0, mock_output, "")

        result = await network.get_network_connections(host=host)

        assert isinstance(result, str)
        assert "Active Network Connections" in result
        for content in expected_content:
            assert content in result

    @pytest.mark.parametrize(
        ("return_value",),
        [
            pytest.param((1, "", "Command not found"), id="command_fails"),
            pytest.param((0, "", ""), id="empty_output"),
        ],
    )
    async def test_get_network_connections_failure(self, mock_execute, return_value):
        """Test getting network connections when command fails or returns empty."""
        mock_execute.return_value = return_value

        result = await network.get_network_connections()

        assert isinstance(result, str)
        assert "Error" in result or "Neither ss nor netstat" in result

    async def test_get_network_connections_error(self, mock_execute):
        """Test getting network connections with general error."""
        mock_execute.side_effect = Exception("Network error")

        result = await network.get_network_connections()

        assert isinstance(result, str)
        assert "Error getting network connections" in result
        assert "Network error" in result


class TestGetListeningPorts:
    """Test get_listening_ports function."""

    @pytest.mark.parametrize(
        ("host", "mock_output", "expected_content"),
        [
            pytest.param(
                None,
                """Netid  State      Recv-Q Send-Q Local Address:Port   Peer Address:Port
tcp    LISTEN     0      128    0.0.0.0:80           0.0.0.0:*
udp    UNCONN     0      0      0.0.0.0:53           0.0.0.0:*""",
                ["0.0.0.0:80", "Total listening ports: 2"],
                id="local",
            ),
            pytest.param(
                "remote.host",
                """Netid  State      Recv-Q Send-Q Local Address:Port   Peer Address:Port
tcp    LISTEN     0      128    0.0.0.0:22           0.0.0.0:*""",
                ["0.0.0.0:22"],
                id="remote",
            ),
        ],
    )
    async def test_get_listening_ports_success(self, mock_execute, host, mock_output, expected_content):
        """Test getting listening ports with success."""
        mock_execute.return_value = (0, mock_output, "")

        result = await network.get_listening_ports(host=host)

        assert isinstance(result, str)
        assert "Listening Ports" in result
        for content in expected_content:
            assert content in result

    @pytest.mark.parametrize(
        ("return_value",),
        [
            pytest.param((1, "", "Command not found"), id="command_fails"),
            pytest.param((0, "", ""), id="empty_output"),
        ],
    )
    async def test_get_listening_ports_failure(self, mock_execute, return_value):
        """Test getting listening ports when command fails or returns empty."""
        mock_execute.return_value = return_value

        result = await network.get_listening_ports()

        assert isinstance(result, str)
        assert "Error" in result or "Neither ss nor netstat" in result

    async def test_get_listening_ports_error(self, mock_execute):
        """Test getting listening ports with general error."""
        mock_execute.side_effect = Exception("Network error")

        result = await network.get_listening_ports()

        assert isinstance(result, str)
        assert "Error getting listening ports" in result
        assert "Network error" in result
