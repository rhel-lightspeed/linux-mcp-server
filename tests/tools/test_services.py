"""Tests for service management tools."""

import sys

import pytest

from fastmcp.exceptions import ToolError


@pytest.fixture
def mock_execute_with_fallback(mock_execute_with_fallback_for):
    """Services-specific execute_with_fallback mock using the shared factory."""
    return mock_execute_with_fallback_for("linux_mcp_server.commands")


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

    async def test_get_service_logs(self, mcp_client):
        result = await mcp_client.call_tool("get_service_logs", arguments={"service_name": "sshd.service", "lines": 5})
        # Filter out empty lines, header lines (=), and journalctl boot markers (--)
        result_lines = [
            line
            for line in result.content[0].text.split("\n")
            if line and not line.startswith("=") and not line.startswith("--")
        ]

        assert len(result_lines) <= 5, "Got more lines than expected"

    async def test_get_service_logs_with_nonexistent_service(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_service_logs", arguments={"service_name": "nonexistent-service-xyz123", "lines": 10}
        )
        result_text = result.content[0].text.casefold()
        expected = (
            "not found",
            "no entries",
            "error",
        )

        assert any(n in result_text for n in expected), "Did not find any expected values"


class TestRemoteServices:
    """Test remote service management."""

    async def test_list_services_remote(self, mock_execute_with_fallback, mcp_client):
        """Test listing services on a remote host."""
        mock_output = "UNIT                     LOAD   ACTIVE SUB     DESCRIPTION\nnginx.service           loaded active running Nginx server\n"
        mock_execute_with_fallback.return_value = (0, mock_output, "")

        result = await mcp_client.call_tool("list_services", arguments={"host": "remote.example.com"})
        result_text = result.content[0].text.casefold()

        assert "nginx.service" in result_text
        assert "system services" in result_text
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
        mock_output = "Jan 01 12:00:00 host nginx[1234]: Starting Nginx\nJan 01 12:00:01 host nginx[1234]: Started"
        mock_execute_with_fallback.return_value = (0, mock_output, "")

        result = await mcp_client.call_tool(
            "get_service_logs", arguments={"service_name": "nginx", "host": "remote.example.com", "lines": 50}
        )
        result_text = result.content[0].text.casefold()

        assert "nginx" in result_text
        assert "starting" in result_text
        mock_execute_with_fallback.assert_called()
