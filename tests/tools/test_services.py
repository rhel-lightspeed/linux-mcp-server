"""Tests for service management tools."""

import sys

import pytest


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

    @pytest.mark.parametrize(
        "service_name, lines, expected",
        (
            ("sshd.service", 5, None),  # Just check line count
            ("nonexistent-service-xyz123", 10, ("not found", "no entries", "error")),
        ),
    )
    async def test_get_service_logs(self, mcp_client, service_name, lines, expected):
        result = await mcp_client.call_tool(
            "get_service_logs", arguments={"service_name": service_name, "lines": lines}
        )
        result_text = result.content[0].text

        if expected is None:
            # Filter out header lines (starting with "=") and boot markers (starting with "--")
            result_lines = [
                line
                for line in result_text.split("\n")
                if line and not line.startswith("=") and not line.startswith("--")
            ]
            assert 1 <= len(result_lines) <= lines, f"Expected 1-{lines} log lines, got {len(result_lines)}"
        else:
            # For invalid services, check error messages
            assert any(n in result_text.casefold() for n in expected), "Did not find any expected values"


class TestRemoteServices:
    @pytest.mark.parametrize(
        ("tool_name", "arguments", "mock_output", "expected_content"),
        [
            pytest.param(
                "list_services",
                {"host": "remote.example.com"},
                "UNIT                     LOAD   ACTIVE SUB     DESCRIPTION\nnginx.service           loaded active running Nginx server\n",
                ["nginx.service", "system services"],
                id="list-services",
            ),
            pytest.param(
                "get_service_status",
                {"service_name": "nginx", "host": "remote.example.com"},
                "● nginx.service - Nginx HTTP Server\n   Loaded: loaded\n   Active: active (running)",
                ["nginx.service", "active"],
                id="get-status",
            ),
            pytest.param(
                "get_service_logs",
                {"service_name": "nginx", "host": "remote.example.com", "lines": 50},
                "Jan 01 12:00:00 host nginx[1234]: Starting Nginx\nJan 01 12:00:01 host nginx[1234]: Started",
                ["nginx", "starting"],
                id="get-logs",
            ),
        ],
    )
    async def test_remote_service_operations(
        self, mock_execute_with_fallback, mcp_client, tool_name, arguments, mock_output, expected_content
    ):
        """Test remote service operations."""
        mock_execute_with_fallback.return_value = (0, mock_output, "")

        result = await mcp_client.call_tool(tool_name, arguments=arguments)
        result_text = result.content[0].text.casefold()

        for content in expected_content:
            assert content in result_text
        mock_execute_with_fallback.assert_called()
