"""Tests for decorator utilities."""

import pytest

from mcp.server.fastmcp.exceptions import ToolError

from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers


class TestDisallowLocalExecutionInContainers:
    """Test disallow_local_execution_in_containers decorator."""

    async def test_allows_execution_when_conditions_met(self, monkeypatch):
        """Test that execution is allowed when host is provided or not in a container."""

        @disallow_local_execution_in_containers
        async def test_func(host=None, username=None):
            return "success"

        # Test 1: Execution allowed when host is provided
        result = await test_func(host="remote.example.com", username="user")
        assert result == "success"

        # Test 2: Local execution allowed when not running in a container
        monkeypatch.delenv("container", raising=False)
        result = await test_func(host=None, username="user")
        assert result == "success"

        # Empty value for 'container' env var does not trigger the check
        monkeypatch.setenv("container", "")
        result = await test_func(host=None, username="user")
        assert result == "success"

    @pytest.mark.parametrize(
        "container_value",
        ["openvz", "lxc", "lxc-libvirt", "systemd-nspawn", "docker", "podman", "rkt", "wsl", "proot", "pouch"],
    )
    async def test_raises_error_for_local_execution_in_container(self, monkeypatch, container_value):
        """Test that ToolError is raised when attempting local execution in a container."""

        @disallow_local_execution_in_containers
        async def test_func(host=None, username=None):
            return "success"

        # Simulate running in a container
        monkeypatch.setenv("container", container_value)
        with pytest.raises(ToolError) as exc_info:
            await test_func(host=None, username="user")

        assert "Local execution is not allowed" in str(exc_info.value)
        assert "container" in str(exc_info.value)
        assert "SSH" in str(exc_info.value)

        # Verify the function works when host is provided (covers function body)
        result = await test_func(host="remote.example.com", username="user")
        assert result == "success"
