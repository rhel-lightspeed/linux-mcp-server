"""Tests for network diagnostic tools."""

import re

import pytest

from fastmcp.exceptions import ToolError


@pytest.fixture
def mock_execute(mock_execute_with_fallback_for):
    """Mock execute_with_fallback for network module."""
    return mock_execute_with_fallback_for("linux_mcp_server.commands")


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
                    (
                        0,
                        "Inter-|   Receive                                                |  Transmit\n face |bytes    packets\n  eth0: 1024 2048 0 0 0 0 0 0 512 1024 0 0 0 0 0 0",
                        "",
                    ),
                ],
                ["eth0"],
                id="remote",
            ),
        ],
    )
    async def test_get_network_interfaces_success(self, mcp_client, mock_execute, host, responses, expected_interfaces):
        """Test getting network interfaces with success."""
        mock_execute.side_effect = responses
        result = await mcp_client.call_tool("get_network_interfaces", arguments={"host": host})
        content = result.structured_content["result"]

        assert content is not None
        assert len(content) == len(expected_interfaces)
        names = [iface["name"] for iface in content]
        assert names == sorted(expected_interfaces)

        eth0 = next(iface for iface in content if iface["name"] == "eth0")
        assert eth0["status"] == "UP"
        assert "192.168.1.100/24" in eth0["addresses"]
        if host is None:
            assert eth0["rx_bytes"] == 9876543
            assert eth0["tx_bytes"] == 5432100
            assert eth0["rx_errors"] == 10
            assert eth0["tx_errors"] == 20
        else:
            assert eth0["rx_bytes"] == 1024
            assert eth0["tx_bytes"] == 512

        if "lo" in expected_interfaces:
            lo = next(iface for iface in content if iface["name"] == "lo")
            assert lo["status"] == "UNKNOWN"
            assert "127.0.0.1/8" in lo["addresses"]
            assert lo["rx_bytes"] == 1234567

        assert mock_execute.call_count == 2

    async def test_get_network_interfaces_partial_failure(self, mcp_client, mock_execute):
        """Test getting network interfaces with partial failures."""
        mock_execute.side_effect = [
            (0, "eth0             UP             192.168.1.100/24", ""),
            (1, "", "Command failed"),
        ]

        result = await mcp_client.call_tool("get_network_interfaces")
        content = result.structured_content["result"]

        assert len(content) == 1
        assert content[0]["name"] == "eth0"
        assert content[0]["status"] == "UP"
        assert content[0]["rx_bytes"] == 0

    async def test_get_network_interfaces_full_failure(self, mcp_client, mock_execute):
        """Test getting network interfaces with full failures."""
        mock_execute.side_effect = [
            (1, "", "Command failed"),
            (1, "", "Command failed"),
        ]

        result = await mcp_client.call_tool("get_network_interfaces")
        assert result.structured_content["result"] == []

    async def test_get_network_interfaces_error(self, mcp_client, mock_execute):
        """Test getting network interfaces with error."""
        mock_execute.side_effect = ValueError("Raised intentionally")
        match = re.compile(r"error calling tool.*raised intentionally", flags=re.I)

        with pytest.raises(ToolError, match=match):
            await mcp_client.call_tool("get_network_interfaces")


class TestGetNetworkConnections:
    """Test get_network_connections function."""

    @pytest.mark.parametrize(
        ("host", "mock_output", "expected_count", "expected_local"),
        [
            pytest.param(
                None,
                """Netid  State      Recv-Q Send-Q Local Address:Port   Peer Address:Port
tcp    ESTAB      0      0      192.168.1.100:22     192.168.1.1:54321
tcp    LISTEN     0      128    0.0.0.0:80           0.0.0.0:*""",
                2,
                "192.168.1.100:22",
                id="local",
            ),
            pytest.param(
                "remote.host",
                """Netid  State      Recv-Q Send-Q Local Address:Port   Peer Address:Port
tcp    ESTAB      0      0      10.0.0.5:443         10.0.0.1:12345""",
                1,
                "10.0.0.5:443",
                id="remote",
            ),
        ],
    )
    async def test_get_network_connections_success(
        self, mcp_client, mock_execute, host, mock_output, expected_count, expected_local
    ):
        """Test getting network connections with success."""
        mock_execute.return_value = (0, mock_output, "")
        result = await mcp_client.call_tool("get_network_connections", arguments={"host": host})
        content = result.structured_content["result"]

        assert len(content) == expected_count
        estab = next(conn for conn in content if conn["local_address"] == expected_local.split(":")[0])
        assert estab["protocol"] == "TCP"
        assert estab["local_port"] == expected_local.split(":")[1]
        if host is None:
            assert any(conn["state"] == "LISTEN" for conn in content)

    @pytest.mark.parametrize(
        ("return_value",),
        [
            pytest.param((1, "", "Command not found"), id="command_fails"),
            pytest.param((0, "", ""), id="empty_output"),
        ],
    )
    async def test_get_network_connections_failure(self, mcp_client, mock_execute, return_value):
        """Test getting network connections when command fails or returns empty."""
        mock_execute.return_value = return_value
        with pytest.raises(ToolError, match="Error getting network connections"):
            await mcp_client.call_tool("get_network_connections")

    async def test_get_network_connections_error(self, mcp_client, mock_execute):
        """Test getting network connections with general error."""
        mock_execute.side_effect = ValueError("Raised intentionally")
        match = re.compile(r"error calling tool.*raised intentionally", flags=re.I)
        with pytest.raises(ToolError, match=match):
            await mcp_client.call_tool("get_network_connections")


class TestGetListeningPorts:
    """Test get_listening_ports function."""

    @pytest.mark.parametrize(
        ("host", "mock_output", "expected_count", "expected_locals"),
        [
            pytest.param(
                None,
                """Netid  State      Recv-Q Send-Q Local Address:Port   Peer Address:Port
tcp    LISTEN     0      128    0.0.0.0:80           0.0.0.0:*
udp    UNCONN     0      0      0.0.0.0:53           0.0.0.0:*""",
                2,
                ["0.0.0.0:80", "0.0.0.0:53"],
                id="local",
            ),
            pytest.param(
                "remote.host",
                """Netid  State      Recv-Q Send-Q Local Address:Port   Peer Address:Port
tcp    LISTEN     0      128    0.0.0.0:22           0.0.0.0:*""",
                1,
                ["0.0.0.0:22"],
                id="remote",
            ),
        ],
    )
    async def test_get_listening_ports_success(
        self, mcp_client, mock_execute, host, mock_output, expected_count, expected_locals
    ):
        """Test getting listening ports with success."""
        mock_execute.return_value = (0, mock_output, "")
        result = await mcp_client.call_tool("get_listening_ports", arguments={"host": host})
        content = result.structured_content["result"]

        assert len(content) == expected_count
        mcp_locals = {f"{port['local_address']}:{port['local_port']}" for port in content}
        assert mcp_locals == set(expected_locals)
        assert all(port["protocol"] in ("TCP", "UDP") for port in content)

    @pytest.mark.parametrize(
        ("return_value",),
        [
            pytest.param((1, "", "Command not found"), id="command_fails"),
            pytest.param((0, "", ""), id="empty_output"),
        ],
    )
    async def test_get_listening_ports_failure(self, mcp_client, mock_execute, return_value):
        """Test getting listening ports when command fails or returns empty."""
        mock_execute.return_value = return_value
        with pytest.raises(ToolError, match="Error getting listening ports"):
            await mcp_client.call_tool("get_listening_ports")

    async def test_get_listening_ports_error(self, mcp_client, mock_execute):
        """Test getting listening ports with general error."""
        mock_execute.side_effect = ValueError("Raised intentionally")
        match = re.compile(r"error calling tool.*raised intentionally", flags=re.I)
        with pytest.raises(ToolError, match=match):
            await mcp_client.call_tool("get_listening_ports")
