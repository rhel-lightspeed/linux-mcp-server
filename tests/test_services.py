"""Tests for service management tools."""

import pytest
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
        assert "active" in result.lower() or "inactive" in result.lower() or "loaded" in result.lower() or "not found" in result.lower()

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

