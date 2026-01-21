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

    async def test_get_service_status(self, mcp_client):
        """Test getting service status returns structured data."""
        result = await mcp_client.call_tool("get_service_status", arguments={"service_name": "sshd.service"})

        # The tool returns structured data (dict), so check the structured content
        assert result.structured_content is not None, "Expected structured data"

        # Verify we have service status fields
        data = result.structured_content
        assert "LoadState" in data or "ActiveState" in data, "Expected service status fields in structured data"

        # ActiveState should be one of the valid states
        if "ActiveState" in data:
            assert data["ActiveState"] in ("active", "inactive", "activating", "deactivating", "failed"), (
                f"Unexpected ActiveState: {data['ActiveState']}"
            )

    async def test_get_service_status_with_nonexistent_service(self, mcp_client):
        """Test that nonexistent service raises ToolError."""

        with pytest.raises(ToolError, match="Service 'nonexistent-service-xyz123.service' not found on this system."):
            await mcp_client.call_tool("get_service_status", arguments={"service_name": "nonexistent-service-xyz123"})

    async def test_get_service_status_error(self, mock_execute_with_fallback, mcp_client):
        """Test that get_service_status raises ToolError when systemctl fails."""
        mock_execute_with_fallback.return_value = (1, "", "Failed to get unit file state: Connection refused")

        with pytest.raises(ToolError, match="Error getting service status: Failed to get unit file state"):
            await mcp_client.call_tool("get_service_status", arguments={"service_name": "sshd"})

    async def test_get_service_logs(self, mock_execute_with_fallback, mcp_client):
        """Test getting service logs with mocked output."""
        mock_output = '[{"__REALTIME_TIMESTAMP": "1600000000000000", "MESSAGE": "sshd: session opened for user test", "PRIORITY": "6", "_PID": "1234"}, {"__REALTIME_TIMESTAMP": "1600000001000000", "MESSAGE": "sshd: session closed for user test", "PRIORITY": "6", "_PID": "1234"}]'
        mock_execute_with_fallback.return_value = (0, mock_output, "")

        result = await mcp_client.call_tool("get_service_logs", arguments={"service_name": "sshd.service", "lines": 5})

        assert result.structured_content is not None, "Expected structured data"
        logs = result.structured_content["result"]
        assert isinstance(logs, list)
        assert len(logs) == 2
        assert logs[0]["MESSAGE"] == "sshd: session opened for user test"
        mock_execute_with_fallback.assert_called()

    async def test_get_service_logs_with_nonexistent_service(self, mcp_client):
        with pytest.raises(ToolError, match="No log entries found for service 'nonexistent-service-xyz123.service'."):
            await mcp_client.call_tool(
                "get_service_logs", arguments={"service_name": "nonexistent-service-xyz123", "lines": 10}
            )

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
        # Mock systemctl show output (key=value format)
        mock_output = "LoadState=loaded\nActiveState=active\nSubState=running\nDescription=Nginx HTTP Server"
        mock_execute_with_fallback.return_value = (0, mock_output, "")

        result = await mcp_client.call_tool(
            "get_service_status", arguments={"service_name": "nginx", "host": "remote.example.com"}
        )

        # The tool now returns structured data
        assert result.structured_content is not None
        data = result.structured_content

        assert data.get("LoadState") == "loaded"
        assert data.get("ActiveState") == "active"
        assert data.get("SubState") == "running"
        mock_execute_with_fallback.assert_called()

    async def test_get_service_logs_remote(self, mock_execute_with_fallback, mcp_client):
        """Test getting service logs on a remote host."""
        mock_output = '[{"_REALTIME_TIMESTAMP": "Jan 01 12:00:00", "_PID": "1234", "MESSAGE": "Starting Nginx"}, {"_REALTIME_TIMESTAMP": "Jan 01 12:00:01", "_PID": "1234", "MESSAGE": "Started"}]'
        mock_execute_with_fallback.return_value = (0, mock_output, "")

        result = await mcp_client.call_tool(
            "get_service_logs", arguments={"service_name": "nginx", "host": "remote.example.com", "lines": 50}
        )

        assert result.structured_content is not None
        data = result.structured_content["result"]

        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["MESSAGE"] == "Starting Nginx"
        assert data[1]["MESSAGE"] == "Started"
        mock_execute_with_fallback.assert_called()
