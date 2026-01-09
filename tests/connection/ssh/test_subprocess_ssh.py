"""Tests for the subprocess SSH backend."""

import asyncio
import tempfile

from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest

from linux_mcp_server.connection.subprocess_ssh import _create_control_dir
from linux_mcp_server.connection.subprocess_ssh import _create_control_path
from linux_mcp_server.connection.subprocess_ssh import _find_ssh_binary
from linux_mcp_server.connection.subprocess_ssh import SSH_CONNECTION_ERROR_CODE
from linux_mcp_server.connection.subprocess_ssh import SSHSubprocessConnection
from linux_mcp_server.connection.subprocess_ssh import SSHSubprocessManager


class TestControlPathGeneration:
    def test_control_path_under_108_chars(self):
        """Ensure control path stays under the 108-char Unix socket limit."""
        long_hostname = "a" * 200 + ".example.com"
        control_path = _create_control_path(long_hostname)

        assert len(str(control_path)) < 108

    def test_control_path_unique_per_host(self):
        """Different hosts should produce different control paths."""
        path1 = _create_control_path("host1.example.com")
        path2 = _create_control_path("host2.example.com")

        assert path1 != path2

    def test_control_path_consistent_for_same_host(self):
        """Same host should always produce the same control path."""
        path1 = _create_control_path("consistent.example.com")
        path2 = _create_control_path("consistent.example.com")

        assert path1 == path2

    def test_control_dir_created_with_correct_permissions(self, mocker):
        """Control directory should be created with 700 permissions."""
        mock_mkdir = mocker.patch.object(Path, "mkdir")
        mocker.patch("linux_mcp_server.connection.subprocess_ssh.getpass.getuser", return_value="testuser")

        _create_control_dir()

        mock_mkdir.assert_called_once_with(mode=0o700, exist_ok=True)


class TestFindSSHBinary:
    def test_find_ssh_binary_success(self, mocker):
        """Test finding ssh binary when it exists."""
        mocker.patch("shutil.which", return_value="/usr/bin/ssh")

        result = _find_ssh_binary()

        assert result == "/usr/bin/ssh"

    def test_find_ssh_binary_not_found(self, mocker):
        """Test error when ssh binary is not in PATH."""
        mocker.patch("shutil.which", return_value=None)

        with pytest.raises(FileNotFoundError, match="ssh command not found"):
            _find_ssh_binary()


class TestSSHSubprocessConnection:
    @pytest.fixture
    def connection(self, mocker):
        """Provide a subprocess connection with mocked ssh binary."""
        mocker.patch(
            "linux_mcp_server.connection.subprocess_ssh._find_ssh_binary",
            return_value="/usr/bin/ssh",
        )
        return SSHSubprocessConnection("test.example.com", control_persist=300)

    def test_build_ssh_command_includes_required_options(self, connection):
        """Verify SSH command includes all required security and connection options."""
        cmd = connection._build_ssh_command("ls -la", timeout=30)

        assert "-o" in cmd
        assert "BatchMode=yes" in cmd
        assert "ControlMaster=auto" in cmd
        assert "StrictHostKeyChecking=no" in cmd
        assert any("ConnectTimeout=" in opt for opt in cmd)
        assert "test.example.com" in cmd
        assert "ls -la" in cmd

    def test_build_ssh_command_with_user(self, connection, mocker):
        """Verify SSH command includes user when configured."""
        mocker.patch("linux_mcp_server.connection.subprocess_ssh.CONFIG.user", "admin")

        cmd = connection._build_ssh_command("ls", timeout=10)

        assert "-l" in cmd
        assert "admin" in cmd

    def test_build_ssh_command_with_host_key_verification(self, connection, mocker):
        """Verify StrictHostKeyChecking is set based on verify_host_keys config."""
        mocker.patch("linux_mcp_server.connection.subprocess_ssh.CONFIG.verify_host_keys", True)

        cmd = connection._build_ssh_command("ls", timeout=10)

        assert "StrictHostKeyChecking=yes" in cmd

    def test_build_ssh_command_with_ssh_key_path(self, connection, mocker):
        """Verify SSH command includes identity file when ssh_key_path is configured."""
        mocker.patch(
            "linux_mcp_server.connection.subprocess_ssh.CONFIG.ssh_key_path",
            Path("/home/user/.ssh/custom_key"),
        )

        cmd = connection._build_ssh_command("ls", timeout=10)

        assert "-i" in cmd
        assert "/home/user/.ssh/custom_key" in cmd

    async def test_run_success(self, connection, mocker):
        """Test successful command execution."""
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"file1\nfile2\n", b"")
        mock_proc.returncode = 0

        mocker.patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        )

        returncode, stdout, stderr = await connection.run("ls", timeout=10)

        assert returncode == 0
        assert stdout == "file1\nfile2\n"
        assert stderr == ""

    async def test_run_returns_bytes_when_encoding_none(self, connection, mocker):
        """Test that raw bytes are returned when encoding is None."""
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"\x00\x01\x02", b"")
        mock_proc.returncode = 0

        mocker.patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        )

        returncode, stdout, stderr = await connection.run("cat binary", timeout=10, encoding=None)

        assert returncode == 0
        assert stdout == b"\x00\x01\x02"
        assert stderr == b""

    async def test_run_timeout(self, connection, mocker):
        """Test command timeout handling."""
        mock_proc = AsyncMock()
        mock_proc.communicate.side_effect = asyncio.TimeoutError()
        mock_proc.kill = Mock()
        mock_proc.wait = AsyncMock()

        mocker.patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        )

        with pytest.raises(ConnectionError, match="timed out"):
            await connection.run("sleep 1000", timeout=1)

        mock_proc.kill.assert_called_once()

    async def test_run_ssh_connection_error(self, connection, mocker):
        """Test SSH-level error detection (exit code 255)."""
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"Connection refused")
        mock_proc.returncode = SSH_CONNECTION_ERROR_CODE

        mocker.patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        )

        with pytest.raises(ConnectionError, match="SSH connection failed"):
            await connection.run("ls", timeout=10)

    async def test_run_command_error_not_connection_error(self, connection, mocker):
        """Test that non-255 exit codes are returned, not raised."""
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"command not found")
        mock_proc.returncode = 127

        mocker.patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        )

        returncode, stdout, stderr = await connection.run("nonexistent", timeout=10)

        assert returncode == 127
        assert "command not found" in stderr

    def test_is_connected_false_initially(self, connection):
        """Connection should not be marked connected before any commands run."""
        assert not connection.is_connected()

    async def test_close_removes_socket(self, connection, mocker):
        """Test that close properly terminates ControlMaster and removes socket."""
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock()

        mocker.patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        )

        connection._control_path = Path(tempfile.gettempdir()) / "test.sock"
        connection._control_path.touch()

        await connection.close()

        assert not connection._control_path.exists()
        assert not connection.is_connected()

    async def test_close_when_socket_not_exists(self, connection, mocker):
        """Test that close handles non-existent socket gracefully."""
        connection._control_path = Path(tempfile.gettempdir()) / "nonexistent_socket.sock"
        connection._connected = True

        await connection.close()

        assert not connection.is_connected()

    async def test_close_handles_timeout_error(self, connection, mocker):
        """Test that close handles timeout when terminating ControlMaster."""
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(side_effect=asyncio.TimeoutError())

        mocker.patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        )

        connection._control_path = Path(tempfile.gettempdir()) / "test_timeout.sock"
        connection._control_path.touch()

        await connection.close()

        assert not connection._control_path.exists()
        assert not connection.is_connected()

    async def test_close_handles_oserror_on_subprocess(self, connection, mocker):
        """Test that close handles OSError when creating subprocess."""
        mocker.patch(
            "asyncio.create_subprocess_exec",
            side_effect=OSError("Cannot create process"),
        )

        connection._control_path = Path(tempfile.gettempdir()) / "test_oserror.sock"
        connection._control_path.touch()

        await connection.close()

        assert not connection._control_path.exists()
        assert not connection.is_connected()

    async def test_close_handles_oserror_on_unlink(self, connection, mocker):
        """Test that close handles OSError when unlinking socket file."""
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock()

        mocker.patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        )

        connection._control_path = Path(tempfile.gettempdir()) / "nonexistent.sock"
        mock_unlink = mocker.patch.object(Path, "unlink", side_effect=OSError("Permission denied"))
        mocker.patch.object(Path, "exists", return_value=True)

        await connection.close()

        mock_unlink.assert_called_once()
        assert not connection.is_connected()

    async def test_run_file_not_found_error(self, connection, mocker):
        """Test that run raises ConnectionError when ssh binary is missing."""
        mocker.patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("No such file"),
        )

        with pytest.raises(ConnectionError, match="SSH binary not found"):
            await connection.run("ls", timeout=10)

    async def test_run_oserror(self, connection, mocker):
        """Test that run raises ConnectionError on OSError."""
        mocker.patch(
            "asyncio.create_subprocess_exec",
            side_effect=OSError("Cannot execute"),
        )

        with pytest.raises(ConnectionError, match="Failed to execute SSH"):
            await connection.run("ls", timeout=10)


class TestSSHSubprocessManager:
    @pytest.fixture
    def manager(self, mocker):
        """Provide a clean manager instance for each test."""
        mocker.patch(
            "linux_mcp_server.connection.subprocess_ssh._find_ssh_binary",
            return_value="/usr/bin/ssh",
        )
        manager = SSHSubprocessManager()
        manager._connections.clear()
        return manager

    def test_singleton_pattern(self, manager):
        """Verify manager follows singleton pattern."""
        manager2 = SSHSubprocessManager()

        assert manager is manager2

    async def test_execute_remote_creates_connection(self, manager, mocker):
        """Test that execute_remote lazily creates connections."""
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"/usr/bin/ls\n", b"")
        mock_proc.returncode = 0

        mocker.patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        )

        await manager.execute_remote(["/usr/bin/ls", "-la"], "host1.example.com", timeout=30)

        assert "host1.example.com" in manager._connections

    async def test_connection_reuse(self, manager, mocker):
        """Test that connections are reused for the same host."""
        mock_conn = AsyncMock(spec=SSHSubprocessConnection)
        mock_conn.run.return_value = (0, "output", "")
        mock_conn.is_connected.return_value = True

        manager._connections["host1.example.com"] = mock_conn

        await manager.execute_remote(["/bin/ls"], "host1.example.com", timeout=30)
        await manager.execute_remote(["/bin/pwd"], "host1.example.com", timeout=30)

        assert mock_conn.run.call_count == 2

    async def test_close_all(self, manager, mocker):
        """Test cleanup of all connections."""
        mock_conn1 = AsyncMock(spec=SSHSubprocessConnection)
        mock_conn2 = AsyncMock(spec=SSHSubprocessConnection)

        manager._connections["host1"] = mock_conn1
        manager._connections["host2"] = mock_conn2

        await manager.close_all()

        mock_conn1.close.assert_called_once()
        mock_conn2.close.assert_called_once()
        assert len(manager._connections) == 0

    async def test_execute_remote_resolves_command_path(self, manager, mocker):
        """Test that non-absolute command paths are resolved."""
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"/usr/bin/ls\n", b"")
        mock_proc.returncode = 0

        mocker.patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        )

        await manager.execute_remote(["ls", "-la"], "host1", timeout=30)

        assert "host1" in manager._connections

    async def test_get_connection_removes_stale_connection(self, manager, mocker):
        """Test that stale connections are removed and new ones created."""
        mock_stale_conn = AsyncMock(spec=SSHSubprocessConnection)
        mock_stale_conn.is_connected.return_value = False

        manager._connections["stale.example.com"] = mock_stale_conn

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"output", b"")
        mock_proc.returncode = 0

        mocker.patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        )

        await manager.execute_remote(["/bin/ls"], "stale.example.com", timeout=30)

        assert manager._connections["stale.example.com"] is not mock_stale_conn

    async def test_execute_remote_cleans_up_on_connection_error(self, manager, mocker):
        """Test that connections are cleaned up when ConnectionError occurs."""
        mock_conn = AsyncMock(spec=SSHSubprocessConnection)
        mock_conn.run.side_effect = ConnectionError("Connection failed")
        mock_conn.is_connected.return_value = True

        manager._connections["failing.example.com"] = mock_conn

        with pytest.raises(ConnectionError):
            await manager.execute_remote(["/bin/ls"], "failing.example.com", timeout=30)

        assert "failing.example.com" not in manager._connections
        mock_conn.close.assert_called_once()

    async def test_execute_remote_connection_error_host_already_removed(self, manager, mocker):
        """Test ConnectionError handling when host was already removed from pool."""
        mock_conn = AsyncMock(spec=SSHSubprocessConnection)

        def remove_and_raise(*args, **kwargs):
            del manager._connections["vanishing.example.com"]
            raise ConnectionError("Connection failed")

        mock_conn.run.side_effect = remove_and_raise
        mock_conn.is_connected.return_value = True

        manager._connections["vanishing.example.com"] = mock_conn

        with pytest.raises(ConnectionError):
            await manager.execute_remote(["/bin/ls"], "vanishing.example.com", timeout=30)

        assert "vanishing.example.com" not in manager._connections

    async def test_close_all_handles_exception(self, manager, mocker):
        """Test that close_all continues despite exceptions from individual connections."""
        mock_conn1 = AsyncMock(spec=SSHSubprocessConnection)
        mock_conn1.close.side_effect = Exception("Close failed")
        mock_conn2 = AsyncMock(spec=SSHSubprocessConnection)

        manager._connections["host1"] = mock_conn1
        manager._connections["host2"] = mock_conn2

        await manager.close_all()

        mock_conn1.close.assert_called_once()
        mock_conn2.close.assert_called_once()
        assert len(manager._connections) == 0

    def test_cleanup_sync(self, manager, mocker):
        """Test synchronous cleanup removes socket files and directory."""
        mock_control_dir = mocker.MagicMock(spec=Path)
        mock_socket1 = mocker.MagicMock(spec=Path)
        mock_socket2 = mocker.MagicMock(spec=Path)
        mock_control_dir.exists.return_value = True
        mock_control_dir.glob.return_value = [mock_socket1, mock_socket2]

        mocker.patch(
            "linux_mcp_server.connection.subprocess_ssh._create_control_dir",
            return_value=mock_control_dir,
        )

        manager._cleanup_sync()

        mock_socket1.unlink.assert_called_once()
        mock_socket2.unlink.assert_called_once()
        mock_control_dir.rmdir.assert_called_once()

    def test_cleanup_sync_handles_unlink_oserror(self, manager, mocker):
        """Test that cleanup_sync continues when unlink fails."""
        mock_control_dir = mocker.MagicMock(spec=Path)
        mock_socket = mocker.MagicMock(spec=Path)
        mock_socket.unlink.side_effect = OSError("Permission denied")
        mock_control_dir.exists.return_value = True
        mock_control_dir.glob.return_value = [mock_socket]

        mocker.patch(
            "linux_mcp_server.connection.subprocess_ssh._create_control_dir",
            return_value=mock_control_dir,
        )

        manager._cleanup_sync()

        mock_socket.unlink.assert_called_once()
        mock_control_dir.rmdir.assert_called_once()

    def test_cleanup_sync_handles_rmdir_oserror(self, manager, mocker):
        """Test that cleanup_sync handles rmdir failure gracefully."""
        mock_control_dir = mocker.MagicMock(spec=Path)
        mock_control_dir.exists.return_value = True
        mock_control_dir.glob.return_value = []
        mock_control_dir.rmdir.side_effect = OSError("Directory not empty")

        mocker.patch(
            "linux_mcp_server.connection.subprocess_ssh._create_control_dir",
            return_value=mock_control_dir,
        )

        manager._cleanup_sync()

        mock_control_dir.rmdir.assert_called_once()

    def test_cleanup_sync_noop_when_dir_not_exists(self, manager, mocker):
        """Test that cleanup_sync does nothing when control dir doesn't exist."""
        mock_control_dir = mocker.MagicMock(spec=Path)
        mock_control_dir.exists.return_value = False

        mocker.patch(
            "linux_mcp_server.connection.subprocess_ssh._create_control_dir",
            return_value=mock_control_dir,
        )

        manager._cleanup_sync()

        mock_control_dir.glob.assert_not_called()
        mock_control_dir.rmdir.assert_not_called()
