from linux_mcp_server.connection.test import discover_ssh_key


def test_discover_ssh_key_env_var_not_exists(mocker, tmp_path):
    """Test SSH key discovery with non-existent env var path."""
    key_path = tmp_path / "nonexistent_key"

    mocker.patch("linux_mcp_server.config.CONFIG.ssh_key_path", key_path)

    result = discover_ssh_key()
    assert result is None
