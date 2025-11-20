"""Tests for decorator utilities."""

import os

import pytest

from mcp.server.fastmcp.exceptions import ToolError

from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers


@pytest.fixture
def basic_test_func():
    """Fixture for basic test function with host and username parameters."""

    @disallow_local_execution_in_containers
    async def test_func(host=None, username=None):
        return "success"

    return test_func


@pytest.fixture
def parametric_test_func():
    """Fixture for test function that returns formatted parameters."""

    @disallow_local_execution_in_containers
    async def test_func(host=None, username=None):
        return f"host={host}, user={username}"

    return test_func


@pytest.fixture
def host_only_test_func():
    """Fixture for test function with only host parameter."""

    @disallow_local_execution_in_containers
    async def test_func(host=None):
        return "success"

    return test_func


class TestDisallowLocalExecutionInContainers:
    """Test disallow_local_execution_in_containers decorator."""

    async def test_allows_execution_when_host_provided(self, basic_test_func):
        """Test that execution is allowed when host parameter is provided."""
        # Should not raise when host is provided
        result = await basic_test_func(host="remote.example.com", username="user")
        assert result == "success"

    async def test_allows_execution_when_not_in_container(self, basic_test_func, mocker):
        """Test that local execution is allowed when not running in a container."""
        # Ensure we're not in container environment
        mocker.patch.dict(os.environ, {}, clear=False)
        if "container" in os.environ:
            del os.environ["container"]
        result = await basic_test_func(host=None, username="user")
        assert result == "success"

    async def test_raises_error_when_local_in_container(self, basic_test_func, mocker):
        """Test that ToolError is raised when attempting local execution in a container."""
        # Simulate running in a container
        mocker.patch.dict(os.environ, {"container": "docker"})
        with pytest.raises(ToolError) as exc_info:
            await basic_test_func(host=None, username="user")

        assert "Local execution is not allowed" in str(exc_info.value)
        assert "container" in str(exc_info.value)
        assert "SSH" in str(exc_info.value)

    async def test_works_with_positional_arguments(self, parametric_test_func):
        """Test that decorator works when host is passed as positional argument."""
        # Test with positional arguments
        result = await parametric_test_func("remote.example.com", "user")
        assert "host=remote.example.com" in result

    async def test_works_with_keyword_arguments(self, parametric_test_func):
        """Test that decorator works when arguments are passed as keywords."""
        # Test with keyword arguments
        result = await parametric_test_func(username="user", host="remote.example.com")
        assert "host=remote.example.com" in result

    async def test_works_with_mixed_arguments(self):
        """Test that decorator works with mixed positional and keyword arguments."""

        @disallow_local_execution_in_containers
        async def test_func(command, host=None, username=None):
            return f"cmd={command}, host={host}, user={username}"

        # Test with mixed arguments
        result = await test_func("ls", host="remote.example.com", username="user")
        assert "cmd=ls" in result
        assert "host=remote.example.com" in result

    async def test_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring."""

        @disallow_local_execution_in_containers
        async def my_special_function(host=None):
            """This is a test function."""
            return "test"

        assert my_special_function.__name__ == "my_special_function"
        assert my_special_function.__doc__ == "This is a test function."

    async def test_raises_with_none_host_in_container(self, basic_test_func, mocker):
        """Test that explicitly passing host=None raises error in container."""
        # Simulate running in a container with explicit host=None
        mocker.patch.dict(os.environ, {"container": "podman"})
        with pytest.raises(ToolError) as exc_info:
            await basic_test_func(host=None)
            assert "Local execution is not allowed" in str(exc_info.value)

    @pytest.mark.parametrize("container_value", ["docker", "podman", "true", "1", "yes"])
    async def test_works_with_different_container_values(self, host_only_test_func, mocker, container_value):
        """Test that any truthy value for 'container' env var triggers the check."""
        mocker.patch.dict(os.environ, {"container": container_value})
        with pytest.raises(ToolError):
            await host_only_test_func(host=None)

    async def test_raises_error_with_empty_container_value(self, host_only_test_func, mocker):
        """Test that empty string for 'container' env var raises error."""
        # Presence of 'container' env var with empty value raises error
        mocker.patch.dict(os.environ, {"container": ""})
        with pytest.raises(ToolError):
            await host_only_test_func(host=None)

    async def test_works_with_functions_without_username_param(self):
        """Test that decorator works with functions that only have host parameter."""

        @disallow_local_execution_in_containers
        async def test_func(command, host=None):
            return f"cmd={command}, host={host}"

        result = await test_func("test", host="remote.example.com")
        assert "cmd=test" in result
        assert "host=remote.example.com" in result

    async def test_function_can_receive_additional_kwargs(self):
        """Test that decorated function can receive additional keyword arguments."""

        @disallow_local_execution_in_containers
        async def test_func(host=None, **kwargs):
            return kwargs

        result = await test_func(host="remote.example.com", extra="value", other="data")
        assert result["extra"] == "value"
        assert result["other"] == "data"

    async def test_original_function_exceptions_pass_through(self):
        """Test that exceptions from the decorated function pass through."""

        @disallow_local_execution_in_containers
        async def test_func(host=None):
            raise ValueError("Original error")

        with pytest.raises(ValueError) as exc_info:
            await test_func(host="remote.example.com")

        assert "Original error" in str(exc_info.value)

    async def test_with_default_host_value_in_container(self, mocker):
        """Test behavior when function has host with default value in container."""

        @disallow_local_execution_in_containers
        async def test_func(command, host=None, timeout=30):
            return f"cmd={command}, host={host}, timeout={timeout}"

        # Should raise in container with default host=None
        mocker.patch.dict(os.environ, {"container": "docker"})
        with pytest.raises(ToolError):
            await test_func("ls")

        # Should work when host is provided
        result = await test_func("ls", host="server")
        assert "host=server" in result
