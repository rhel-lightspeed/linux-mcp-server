"""Tests for service management tools."""

import sys

import pytest


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

    @pytest.mark.parametrize(
        "service_name, expected",
        (
            ("sshd.service", ("active", "inactive", "loaded", "not found")),
            ("nonexistent-service-xyz123", ("not found", "could not", "error")),
        ),
    )
    async def test_get_service_status(self, mcp_client, service_name, expected):
        result = await mcp_client.call_tool("get_service_status", arguments={"service_name": service_name})
        result_text = result.content[0].text.casefold()

        assert any(n in result_text for n in expected), "Did not find any expected values"

    async def test_get_service_status_with_nonexistent_service(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_service_status", arguments={"service_name": "nonexistent-service-xyz123"}
        )
        result_text = result.content[0].text.casefold()
        expected = (
            "not found",
            "could not",
            "error",
        )
        assert any(n in result_text for n in expected), "Did not find any expected values"

    async def test_get_service_logs(self, mcp_client):
        result = await mcp_client.call_tool("get_service_logs", arguments={"service_name": "sshd.service", "lines": 5})
        result_lines = [line for line in result.content[0].text.split("\n") if line and not line.startswith("=")]

        assert len(result_lines) < 6, "Got more lines than expected"

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
    async def test_list_services_remote(self, mocker, mcp_client):
        """Test listing services on a remote host."""
        mock_output = "UNIT                     LOAD   ACTIVE SUB     DESCRIPTION\nnginx.service           loaded active running Nginx server\n"
        mock_exec = mocker.patch(
            "linux_mcp_server.tools.services.execute_command", return_value=(0, mock_output, ""), autospec=True
        )

        result = await mcp_client.call_tool("list_services", arguments={"host": "remote.example.com"})
        result_text = result.content[0].text.casefold()

        assert "nginx.service" in result_text
        assert "system services" in result_text
        assert mock_exec.call_count > 0

    async def test_get_service_status_remote(self, mocker, mcp_client):
        """Test getting service status on a remote host."""
        mock_output = "● nginx.service - Nginx HTTP Server\n   Loaded: loaded\n   Active: active (running)"
        mock_exec = mocker.patch(
            "linux_mcp_server.tools.services.execute_command", return_value=(0, mock_output, ""), autospec=True
        )

        result = await mcp_client.call_tool(
            "get_service_status", arguments={"service_name": "nginx", "host": "remote.example.com"}
        )
        result_text = result.content[0].text.casefold()

        assert "nginx.service" in result_text
        assert "active" in result_text
        assert mock_exec.call_count > 0

    async def test_get_service_logs_remote(self, mocker, mcp_client):
        """Test getting service logs on a remote host."""
        mock_output = "Jan 01 12:00:00 host nginx[1234]: Starting Nginx\nJan 01 12:00:01 host nginx[1234]: Started"
        mock_exec = mocker.patch(
            "linux_mcp_server.tools.services.execute_command", return_value=(0, mock_output, ""), autospec=True
        )

        result = await mcp_client.call_tool(
            "get_service_logs", arguments={"service_name": "nginx", "host": "remote.example.com", "lines": 50}
        )
        result_text = result.content[0].text.casefold()

        assert "nginx" in result_text
        assert "starting" in result_text
        assert mock_exec.call_count > 0
