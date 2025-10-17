"""Tests for service management tools."""

import pytest
from unittest.mock import patch, AsyncMock
from linux_mcp_server.tools import services


class TestServices:
    """Test service management tools."""

    @pytest.mark.asyncio
    async def test_list_services_returns_string(self):
        """Test that list_services returns a string."""
        result = await services.list_services()
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_list_services_contains_service_info(self):
        """Test that list_services contains service information."""
        result = await services.list_services()

        # Should contain service-related keywords
        assert "service" in result.lower() or "unit" in result.lower()
        # Should show status information
        assert "active" in result.lower() or "inactive" in result.lower() or "running" in result.lower()

    @pytest.mark.asyncio
    async def test_get_service_status_with_common_service(self):
        """Test getting status of a common service."""
        # Test with a service that should exist on most systems
        result = await services.get_service_status("sshd.service")
        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain status information
        assert (
            "active" in result.lower()
            or "inactive" in result.lower()
            or "loaded" in result.lower()
            or "not found" in result.lower()
        )

    @pytest.mark.asyncio
    async def test_get_service_status_with_nonexistent_service(self):
        """Test getting status of a non-existent service."""
        result = await services.get_service_status("nonexistent-service-xyz123")
        assert isinstance(result, str)
        assert len(result) > 0
        # Should handle gracefully
        assert "not found" in result.lower() or "could not" in result.lower() or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_get_service_logs_returns_string(self):
        """Test that get_service_logs returns a string."""
        result = await services.get_service_logs("sshd.service", lines=10)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_service_logs_respects_line_limit(self):
        """Test that get_service_logs respects the lines parameter."""
        # This is a basic test - we just verify it runs without error
        result = await services.get_service_logs("sshd.service", lines=5)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_get_service_logs_with_nonexistent_service(self):
        """Test getting logs of a non-existent service."""
        result = await services.get_service_logs("nonexistent-service-xyz123", lines=10)
        assert isinstance(result, str)
        assert len(result) > 0
        # Should handle gracefully
        assert "not found" in result.lower() or "no entries" in result.lower() or "error" in result.lower()


class TestRemoteServices:
    """Test remote service management."""

    @pytest.mark.asyncio
    async def test_list_services_remote(self):
        """Test listing services on a remote host."""
        mock_output = "UNIT                     LOAD   ACTIVE SUB     DESCRIPTION\nnginx.service           loaded active running Nginx server\n"

        with patch("linux_mcp_server.tools.services.execute_command") as mock_exec:
            mock_exec.return_value = (0, mock_output, "")

            result = await services.list_services(host="remote.example.com", username="admin")

            assert "nginx.service" in result
            assert "System Services" in result
            mock_exec.assert_called()

    @pytest.mark.asyncio
    async def test_get_service_status_remote(self):
        """Test getting service status on a remote host."""
        mock_output = "● nginx.service - Nginx HTTP Server\n   Loaded: loaded\n   Active: active (running)"

        with patch("linux_mcp_server.tools.services.execute_command") as mock_exec:
            mock_exec.return_value = (0, mock_output, "")

            result = await services.get_service_status("nginx", host="remote.example.com", username="admin")

            assert "nginx.service" in result
            assert "active" in result.lower()
            mock_exec.assert_called()

    @pytest.mark.asyncio
    async def test_get_service_logs_remote(self):
        """Test getting service logs on a remote host."""
        mock_output = "Jan 01 12:00:00 host nginx[1234]: Starting Nginx\nJan 01 12:00:01 host nginx[1234]: Started"

        with patch("linux_mcp_server.tools.services.execute_command") as mock_exec:
            mock_exec.return_value = (0, mock_output, "")

            result = await services.get_service_logs("nginx", lines=50, host="remote.example.com", username="admin")

            assert "nginx" in result.lower()
            assert "Starting" in result
            mock_exec.assert_called()
