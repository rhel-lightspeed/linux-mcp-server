"""Fixtures for SSH connection tests."""

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def reset_ssh_singletons() -> Iterator[None]:
    """Reset all SSH-related singletons before each test.

    This prevents test pollution when tests run in different orders
    (e.g., with pytest-randomly). The singletons that need resetting are:
    - _connection_manager in ssh.py (facade-level manager)
    - SSHSubprocessManager._instance (subprocess backend singleton)
    - SSHAsyncSSHManager._instance (asyncssh backend singleton)
    """
    import linux_mcp_server.connection.ssh as ssh_module

    ssh_module._connection_manager = None

    from linux_mcp_server.connection.subprocess_ssh import SSHSubprocessManager

    SSHSubprocessManager._instance = None

    from linux_mcp_server.connection.asyncssh_backend import SSHAsyncSSHManager

    SSHAsyncSSHManager._instance = None

    yield

    ssh_module._connection_manager = None
    SSHSubprocessManager._instance = None
    SSHAsyncSSHManager._instance = None
