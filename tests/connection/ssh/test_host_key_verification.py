from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import Mock

import pytest

from linux_mcp_server.connection.ssh import SSHConnectionManager


@pytest.fixture
def ssh_manager():
    """Provide a clean SSH manager for each test."""
    manager = SSHConnectionManager()
    manager._connections.clear()
    return manager


@pytest.fixture
def mock_asyncssh_connect(mocker):
    """Provide a mock for asyncssh.connect that captures call arguments."""
    mock_conn = AsyncMock()
    mock_conn.is_closed = Mock(return_value=False)

    captured_kwargs = {}

    async def capture_connect(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return mock_conn

    mock_connect = MagicMock(side_effect=capture_connect)
    mocker.patch("asyncssh.connect", mock_connect)

    return captured_kwargs


@pytest.mark.parametrize(
    ("verify_host_keys", "use_custom_path", "expect_none", "expect_warning"),
    [
        (True, False, False, False),  # Default: uses ~/.ssh/known_hosts
        (True, True, False, False),  # Custom path used when verification enabled
        (False, False, True, True),  # Disabled: None + warning
        (False, True, True, True),  # Disabled overrides custom path
    ],
    ids=[
        "enabled_default_path",
        "enabled_custom_path",
        "disabled_logs_warning",
        "disabled_overrides_custom",
    ],
)
async def test_known_hosts_configuration(
    mocker,
    ssh_manager,
    mock_asyncssh_connect,
    tmp_path,
    caplog,
    verify_host_keys,
    use_custom_path,
    expect_none,
    expect_warning,
):
    """Test known_hosts is configured correctly based on verify_host_keys and path settings."""
    custom_path = tmp_path / "custom_known_hosts" if use_custom_path else None

    mocker.patch("linux_mcp_server.connection.asyncssh_backend.CONFIG.verify_host_keys", verify_host_keys)
    mocker.patch("linux_mcp_server.connection.asyncssh_backend.CONFIG.known_hosts_path", custom_path)
    mocker.patch("pathlib.Path.home", return_value=tmp_path)

    with caplog.at_level("WARNING"):
        await ssh_manager.get_connection("testhost")

    if expect_none:
        assert mock_asyncssh_connect["known_hosts"] is None
    elif use_custom_path:
        assert mock_asyncssh_connect["known_hosts"] == str(custom_path)
    else:
        assert mock_asyncssh_connect["known_hosts"] == str(tmp_path / ".ssh" / "known_hosts")

    if expect_warning:
        assert "host key verification disabled" in caplog.text.lower()
        assert "mitm" in caplog.text.lower()
    else:
        assert "mitm" not in caplog.text.lower()
