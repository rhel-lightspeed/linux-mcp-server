"""Tests for service management tools."""

import sys

import pytest

from fastmcp.exceptions import ToolError


@pytest.mark.skipif(sys.platform != "linux", reason="Only passes on Linux")
class TestServices:
    async def test_list_services(self, mcp_client):
        result = await mcp_client.call_tool("list_services")
        result_text = result.content[0].text.casefold()
        expected = (
            ("service", "unit"),
            ("active", "inactive", "running"),
        )

        assert all(any(n in result_text for n in case) for case in expected), "Did not find all expected values"

    async def test_get_service_status(self, mock_execute_with_fallback, mcp_client):
        """Test getting service status with mocked systemctl output (no real sshd unit required)."""
        mock_output = "● sshd.service - OpenSSH server\n   Loaded: loaded\n   Active: active (running)"
        mock_execute_with_fallback.return_value = (0, mock_output, "")

        result = await mcp_client.call_tool("get_service_status", arguments={"service_name": "sshd.service"})
        result_text = result.content[0].text.casefold()

        assert "sshd.service" in result_text
        assert "loaded" in result_text
        assert "active" in result_text
        mock_execute_with_fallback.assert_called()

    async def test_get_service_status_with_nonexistent_service(self, mcp_client):
        with pytest.raises(ToolError, match="Service 'nonexistent-service-xyz123.service' not found on this system."):
            await mcp_client.call_tool("get_service_status", arguments={"service_name": "nonexistent-service-xyz123"})

    async def test_get_service_status_error(self, mock_execute_with_fallback, mcp_client):
        """Test that get_service_status raises ToolError when systemctl fails."""
        mock_execute_with_fallback.return_value = (1, "", "Failed to get unit file state: Connection refused")

        with pytest.raises(ToolError, match="Error getting service status: Failed to get unit file state"):
            await mcp_client.call_tool("get_service_status", arguments={"service_name": "sshd"})

    async def test_get_service_logs(self, mock_execute_with_fallback, mcp_client):
        """Test getting service logs with mocked output."""
        mock_output = (
            "Jan 01 12:00:00 host sshd[1234]: session opened for user test\n"
            "Jan 01 12:00:01 host sshd[1234]: session closed for user test"
        )
        mock_execute_with_fallback.return_value = (0, mock_output, "")

        result = await mcp_client.call_tool("get_service_logs", arguments={"service_name": "sshd.service", "lines": 5})

        assert result.structured_content is not None, "Expected structured data"
        content = result.structured_content
        assert content["lines_count"] == 2
        assert len(content["entries"]) == 2
        assert "session opened for user test" in content["entries"][0]
        assert content["unit"] == "sshd.service"
        mock_execute_with_fallback.assert_called()

    async def test_get_service_logs_with_nonexistent_service(self, mock_execute_with_fallback, mcp_client):
        """Empty journal (e.g. unknown unit with no lines) raises; real journalctl output is not deterministic."""
        mock_execute_with_fallback.return_value = (0, "", "")

        with pytest.raises(ToolError, match="No log entries found for service 'nonexistent-service-xyz123.service'."):
            await mcp_client.call_tool(
                "get_service_logs", arguments={"service_name": "nonexistent-service-xyz123", "lines": 10}
            )

        mock_execute_with_fallback.assert_called()

    async def test_get_service_logs_error(self, mock_execute_with_fallback, mcp_client):
        """Test that get_service_logs raises ToolError when journalctl fails."""
        mock_execute_with_fallback.return_value = (1, "", "Failed to access journal: Permission denied")

        with pytest.raises(ToolError, match="Error getting service logs: Failed to access journal"):
            await mcp_client.call_tool("get_service_logs", arguments={"service_name": "sshd", "lines": 10})

    async def test_list_services_error(self, mock_execute_with_fallback, mcp_client):
        """Test that list_services raises ToolError when systemctl fails."""
        mock_execute_with_fallback.return_value = (1, "", "Failed to connect to bus: No such file or directory")

        with pytest.raises(ToolError, match="Error listing services: Failed to connect to bus"):
            await mcp_client.call_tool("list_services")


class TestRemoteServices:
    """Test remote service management."""

    async def test_list_services_remote(self, mock_execute_with_fallback, mcp_client):
        """Test listing services on a remote host."""
        mock_output = '[{"unit":"nginx.service","load":"loaded","active":"active","sub":"running","description":"Nginx HTTP Server"}]'
        mock_execute_with_fallback.return_value = (0, mock_output, "")

        result = await mcp_client.call_tool("list_services", arguments={"host": "remote.example.com"})

        assert result.structured_content is not None
        services = result.structured_content["result"]
        assert isinstance(services, list)
        assert services[0]["unit"] == "nginx.service"
        assert services[0]["load"] == "loaded"
        assert services[0]["active"] == "active"
        assert services[0]["sub"] == "running"
        assert services[0]["description"] == "Nginx HTTP Server"
        mock_execute_with_fallback.assert_called()

    async def test_get_service_status_remote(self, mock_execute_with_fallback, mcp_client):
        """Test getting service status on a remote host."""
        mock_output = "● nginx.service - Nginx HTTP Server\n   Loaded: loaded\n   Active: active (running)"
        mock_execute_with_fallback.return_value = (0, mock_output, "")

        result = await mcp_client.call_tool(
            "get_service_status", arguments={"service_name": "nginx", "host": "remote.example.com"}
        )
        result_text = result.content[0].text.casefold()

        assert "nginx.service" in result_text
        assert "active" in result_text
        mock_execute_with_fallback.assert_called()

    async def test_get_service_logs_remote(self, mock_execute_with_fallback, mcp_client):
        """Test getting service logs on a remote host."""
        mock_output = "Jan 01 12:00:00 remote nginx[1]: Starting Nginx\nJan 01 12:00:01 remote nginx[1]: Started"
        mock_execute_with_fallback.return_value = (0, mock_output, "")

        result = await mcp_client.call_tool(
            "get_service_logs", arguments={"service_name": "nginx", "host": "remote.example.com", "lines": 50}
        )

        assert result.structured_content is not None
        content = result.structured_content

        assert content["lines_count"] == 2
        assert len(content["entries"]) == 2
        assert "Starting Nginx" in content["entries"][0]
        assert "Started" in content["entries"][1]
        assert content["unit"] == "nginx.service"
        mock_execute_with_fallback.assert_called()
