"""Tests for network diagnostic tools."""

from linux_mcp_server.tools import network


class TestGetNetworkInterfaces:
    """Test get_network_interfaces function."""

    async def test_get_network_interfaces_local_success(self, mocker):
        """Test getting network interfaces locally with success."""
        mock_execute = mocker.patch.object(network, "execute_with_fallback")

        # Mock responses for different commands
        mock_execute.side_effect = [
            (0, "eth0             UP             192.168.1.100/24\nlo               UNKNOWN        127.0.0.1/8", ""),
            (
                0,
                "Inter-|   Receive                                                |  Transmit\n face |bytes    packets\n    lo: 1234567   12345    0    0    0     0          0         0  1234567   12345    0    0    0     0       0          0\n  eth0: 9876543   98765   10    5    0     0          0       100  5432100   54321   20   10    0     0       0          0",
                "",
            ),
        ]

        result = await network.get_network_interfaces()

        assert isinstance(result, str)
        assert "Network Interfaces" in result
        assert "eth0" in result
        assert "lo" in result
        assert mock_execute.call_count == 2

    async def test_get_network_interfaces_remote_success(self, mocker):
        """Test getting network interfaces remotely with success."""
        mock_execute = mocker.patch.object(network, "execute_with_fallback")

        mock_execute.side_effect = [
            (0, "eth0             UP             192.168.1.100/24", ""),
            (0, "eth0: 1024 2048 0 0 0 0 0 0 512 1024 0 0 0 0 0 0", ""),
        ]

        result = await network.get_network_interfaces(host="remote.example.com")

        assert isinstance(result, str)
        assert "Network Interfaces" in result
        assert "eth0" in result
        assert mock_execute.call_count == 2

    async def test_get_network_interfaces_partial_failure(self, mocker):
        """Test getting network interfaces with partial failures."""
        mock_execute = mocker.patch.object(network, "execute_with_fallback")

        mock_execute.side_effect = [
            (0, "eth0             UP             192.168.1.100/24", ""),
            (1, "", "Command failed"),
        ]

        result = await network.get_network_interfaces()

        assert isinstance(result, str)
        assert "Network Interfaces" in result
        assert "eth0" in result

    async def test_get_network_interfaces_error(self, mocker):
        """Test getting network interfaces with error."""
        mock_execute = mocker.patch.object(network, "execute_with_fallback")
        mock_execute.side_effect = Exception("Network error")

        result = await network.get_network_interfaces()

        assert isinstance(result, str)
        assert "Error getting network interface information" in result
        assert "Network error" in result


class TestGetNetworkConnections:
    """Test get_network_connections function."""

    async def test_get_network_connections_success(self, mocker):
        """Test getting network connections with success."""
        mock_output = """Netid  State      Recv-Q Send-Q Local Address:Port   Peer Address:Port
tcp    ESTAB      0      0      192.168.1.100:22     192.168.1.1:54321
tcp    LISTEN     0      128    0.0.0.0:80           0.0.0.0:*"""

        mock_execute = mocker.patch.object(network, "execute_with_fallback")
        mock_execute.return_value = (0, mock_output, "")

        result = await network.get_network_connections()

        assert isinstance(result, str)
        assert "Active Network Connections" in result
        assert "192.168.1.100" in result
        assert "Total connections: 2" in result

    async def test_get_network_connections_remote(self, mocker):
        """Test getting network connections remotely."""
        mock_output = """Netid  State      Recv-Q Send-Q Local Address:Port   Peer Address:Port
tcp    ESTAB      0      0      10.0.0.5:443         10.0.0.1:12345"""

        mock_execute = mocker.patch.object(network, "execute_with_fallback")
        mock_execute.return_value = (0, mock_output, "")

        result = await network.get_network_connections(host="remote.host")

        assert isinstance(result, str)
        assert "Active Network Connections" in result
        assert "10.0.0.5" in result

    async def test_get_network_connections_command_fails(self, mocker):
        """Test getting network connections when command fails."""
        mock_execute = mocker.patch.object(network, "execute_with_fallback")
        mock_execute.return_value = (1, "", "Command not found")

        result = await network.get_network_connections()

        assert isinstance(result, str)
        assert "Error" in result or "Neither ss nor netstat" in result

    async def test_get_network_connections_error(self, mocker):
        """Test getting network connections with general error."""
        mock_execute = mocker.patch.object(network, "execute_with_fallback")
        mock_execute.side_effect = Exception("Network error")

        result = await network.get_network_connections()

        assert isinstance(result, str)
        assert "Error getting network connections" in result
        assert "Network error" in result

    async def test_get_network_connections_empty_output(self, mocker):
        """Test getting network connections with empty output."""
        mock_execute = mocker.patch.object(network, "execute_with_fallback")
        mock_execute.return_value = (0, "", "")

        result = await network.get_network_connections()

        assert "Error" in result or "Neither" in result


class TestGetListeningPorts:
    """Test get_listening_ports function."""

    async def test_get_listening_ports_success(self, mocker):
        """Test getting listening ports with success."""
        mock_output = """Netid  State      Recv-Q Send-Q Local Address:Port   Peer Address:Port
tcp    LISTEN     0      128    0.0.0.0:80           0.0.0.0:*
udp    UNCONN     0      0      0.0.0.0:53           0.0.0.0:*"""

        mock_execute = mocker.patch.object(network, "execute_with_fallback")
        mock_execute.return_value = (0, mock_output, "")

        result = await network.get_listening_ports()

        assert isinstance(result, str)
        assert "Listening Ports" in result
        assert "0.0.0.0:80" in result
        assert "Total listening ports: 2" in result

    async def test_get_listening_ports_remote(self, mocker):
        """Test getting listening ports remotely."""
        mock_output = """Netid  State      Recv-Q Send-Q Local Address:Port   Peer Address:Port
tcp    LISTEN     0      128    0.0.0.0:22           0.0.0.0:*"""

        mock_execute = mocker.patch.object(network, "execute_with_fallback")
        mock_execute.return_value = (0, mock_output, "")

        result = await network.get_listening_ports(host="remote.host")

        assert isinstance(result, str)
        assert "Listening Ports" in result
        assert "0.0.0.0:22" in result

    async def test_get_listening_ports_command_fails(self, mocker):
        """Test getting listening ports when command fails."""
        mock_execute = mocker.patch.object(network, "execute_with_fallback")
        mock_execute.return_value = (1, "", "Command not found")

        result = await network.get_listening_ports()

        assert isinstance(result, str)
        assert "Error" in result or "Neither ss nor netstat" in result

    async def test_get_listening_ports_error(self, mocker):
        """Test getting listening ports with general error."""
        mock_execute = mocker.patch.object(network, "execute_with_fallback")
        mock_execute.side_effect = Exception("Network error")

        result = await network.get_listening_ports()

        assert isinstance(result, str)
        assert "Error getting listening ports" in result
        assert "Network error" in result

    async def test_get_listening_ports_empty_output(self, mocker):
        """Test getting listening ports with empty output."""
        mock_execute = mocker.patch.object(network, "execute_with_fallback")
        mock_execute.return_value = (0, "", "")

        result = await network.get_listening_ports()

        assert "Error" in result or "Neither" in result
