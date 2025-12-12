"""Tests for Ansible executor."""

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from linux_mcp_server.connection.ansible import AnsibleExecutionError
from linux_mcp_server.connection.ansible import AnsibleExecutor
from linux_mcp_server.connection.ansible import execute_ansible_module
from linux_mcp_server.connection.ansible import get_ansible_executor


@pytest.fixture
def mock_ansible_runner():
    """Mock ansible_runner.run() with successful execution."""
    with patch("linux_mcp_server.connection.ansible.ansible_runner") as mock_runner_module:
        # Create successful runner response
        runner = MagicMock()
        runner.status = "successful"
        runner.stats = {"ok": {}, "failures": {}}
        runner.events = [
            {
                "event": "runner_on_ok",
                "event_data": {
                    "res": {
                        "ansible_facts": {
                            "ansible_devices": {
                                "sda": {
                                    "model": "SAMSUNG SSD",
                                    "size": "1.00 TB",
                                    "vendor": "ATA",
                                    "removable": "0",
                                    "partitions": {
                                        "sda1": {"size": "512.00 GB"},
                                        "sda2": {"size": "488.00 GB"},
                                    },
                                }
                            }
                        }
                    }
                },
            }
        ]
        mock_runner_module.run.return_value = runner
        yield mock_runner_module


@pytest.fixture
def reset_global_executor():
    """Reset the global executor between tests."""
    import linux_mcp_server.connection.ansible as ansible_module

    original = ansible_module._ansible_executor
    ansible_module._ansible_executor = None
    yield
    ansible_module._ansible_executor = original


class TestAnsibleExecutor:
    async def test_run_module_success(self, mock_ansible_runner):
        """Test successful module execution."""
        executor = AnsibleExecutor()

        result = await executor.run_module(
            module="setup",
            module_args={"gather_subset": ["devices"]},
            host="test.host.com",
            username="testuser",
        )

        assert "ansible_facts" in result
        assert "ansible_devices" in result["ansible_facts"]
        assert "sda" in result["ansible_facts"]["ansible_devices"]

        mock_ansible_runner.run.assert_called_once()
        call_kwargs = mock_ansible_runner.run.call_args[1]
        assert call_kwargs["module"] == "setup"
        assert call_kwargs["host_pattern"] == "test.host.com"

        executor.shutdown()

    async def test_run_module_failed(self, mock_ansible_runner):
        """Test module execution failure."""
        mock_ansible_runner.run.return_value.status = "failed"
        mock_ansible_runner.run.return_value.stats = {"failures": {"test.host.com": 1}}

        executor = AnsibleExecutor()

        with pytest.raises(AnsibleExecutionError, match="Ansible execution failed"):
            await executor.run_module(
                module="command",
                module_args="false",
                host="test.host.com",
            )

        executor.shutdown()

    async def test_run_module_unreachable(self, mock_ansible_runner):
        """Test unreachable host."""
        mock_ansible_runner.run.return_value.status = "unreachable"

        executor = AnsibleExecutor()

        with pytest.raises(AnsibleExecutionError, match="Host unreachable"):
            await executor.run_module(
                module="ping",
                host="unreachable.host.com",
            )

        executor.shutdown()

    async def test_run_module_no_result(self, mock_ansible_runner):
        """Test when no result is returned from events."""
        mock_ansible_runner.run.return_value.status = "successful"
        mock_ansible_runner.run.return_value.events = []

        executor = AnsibleExecutor()

        with pytest.raises(AnsibleExecutionError, match="No result returned"):
            await executor.run_module(
                module="setup",
                host="test.host.com",
            )

        executor.shutdown()

    async def test_run_module_timeout(self, mock_ansible_runner):
        """Test execution timeout."""

        def slow_run(*args, **kwargs):
            import time

            time.sleep(5)
            return mock_ansible_runner.run.return_value

        mock_ansible_runner.run.side_effect = slow_run

        executor = AnsibleExecutor()

        with pytest.raises(TimeoutError, match="timed out"):
            await executor.run_module(
                module="command",
                module_args="sleep 100",
                host="test.host.com",
                timeout=1,
            )

        executor.shutdown()

    async def test_run_module_with_ssh_key(self, mock_ansible_runner):
        """Test module execution with SSH key."""
        with patch("linux_mcp_server.connection.ansible.discover_ssh_key") as mock_discover:
            mock_discover.return_value = "/home/user/.ssh/id_ed25519"
            executor = AnsibleExecutor()

            await executor.run_module(
                module="setup",
                host="test.host.com",
            )

            call_kwargs = mock_ansible_runner.run.call_args[1]
            assert call_kwargs["extravars"]["ansible_ssh_private_key_file"] == "/home/user/.ssh/id_ed25519"

            executor.shutdown()

    async def test_run_module_localhost(self, mock_ansible_runner):
        """Test module execution on localhost."""
        executor = AnsibleExecutor()

        result = await executor.run_module(
            module="setup",
            host="localhost",
        )

        assert "ansible_facts" in result
        call_kwargs = mock_ansible_runner.run.call_args[1]
        assert call_kwargs["host_pattern"] == "localhost"

        executor.shutdown()


class TestExecuteAnsibleModule:
    async def test_execute_ansible_module_localhost(self, mock_ansible_runner, reset_global_executor):
        """Test module execution on localhost via helper function."""
        result = await execute_ansible_module(
            module="setup",
            module_args={"filter": "ansible_devices"},
        )

        assert "ansible_facts" in result
        mock_ansible_runner.run.assert_called_once()
        assert mock_ansible_runner.run.call_args[1]["host_pattern"] == "localhost"

    async def test_execute_ansible_module_remote(self, mock_ansible_runner, reset_global_executor):
        """Test module execution on remote host via helper function."""
        result = await execute_ansible_module(
            module="setup",
            host="remote.host.com",
            username="admin",
        )

        assert "ansible_facts" in result
        call_kwargs = mock_ansible_runner.run.call_args[1]
        assert call_kwargs["host_pattern"] == "remote.host.com"
        assert call_kwargs["extravars"]["ansible_user"] == "admin"

    async def test_get_ansible_executor_singleton(self, mock_ansible_runner, reset_global_executor):
        """Test that get_ansible_executor returns the same instance."""
        executor1 = get_ansible_executor()
        executor2 = get_ansible_executor()

        assert executor1 is executor2


class TestAnsibleExecutorShutdown:
    def test_shutdown_twice_is_noop(self, mock_ansible_runner):
        """Test that shutdown() can be called multiple times safely."""
        executor = AnsibleExecutor()

        # First shutdown should work
        executor.shutdown()
        assert executor._shutdown is True

        # Second shutdown should be a no-op (no exception)
        executor.shutdown()
        assert executor._shutdown is True

    async def test_run_module_reraises_ansible_execution_error(self, mock_ansible_runner):
        """Test that AnsibleExecutionError raised in _run_ansible_module is re-raised unchanged."""
        executor = AnsibleExecutor()

        # Simulate _run_ansible_module raising AnsibleExecutionError directly
        def raise_ansible_error(*args, **kwargs):
            raise AnsibleExecutionError("Original error message")

        mock_ansible_runner.run.side_effect = raise_ansible_error

        with pytest.raises(AnsibleExecutionError, match="Original error message"):
            await executor.run_module(
                module="test",
                host="test.host.com",
            )

        executor.shutdown()

    async def test_run_module_wraps_unexpected_exception(self, mock_ansible_runner):
        """Test that unexpected exceptions are wrapped in AnsibleExecutionError."""
        executor = AnsibleExecutor()

        def raise_unexpected_error(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        mock_ansible_runner.run.side_effect = raise_unexpected_error

        with pytest.raises(AnsibleExecutionError, match="Failed to execute Ansible module"):
            await executor.run_module(
                module="test",
                host="test.host.com",
            )

        executor.shutdown()
