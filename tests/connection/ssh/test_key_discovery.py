from linux_mcp_server.connection.ssh import discover_ssh_key


def test_discover_ssh_key_env_var_not_exists(mocker, tmp_path):
    """Test SSH key discovery with non-existent env var path."""
    key_path = tmp_path / "nonexistent_key"

    mocker.patch("linux_mcp_server.connection.ssh.CONFIG.ssh_key_path", key_path)

    result = discover_ssh_key()
    assert result is None


def test_discover_ssh_key_default_locations(tmp_path, mocker):
    """Test SSH key discovery falls back to default locations."""
    # Mock home directory
    fake_ssh_dir = tmp_path / ".ssh"
    fake_ssh_dir.mkdir()

    # Create a default key
    id_ed25519 = fake_ssh_dir / "id_ed25519"
    id_ed25519.touch()

    # Use mocker.patch with proper attribute configuration
    # Configure mock to return None for ssh_key_path (not a MagicMock)
    mocker.patch("pathlib.Path.home", return_value=tmp_path)
    mocker.patch("linux_mcp_server.connection.ssh.CONFIG.ssh_key_path", None)
    mocker.patch("linux_mcp_server.connection.ssh.CONFIG.search_for_ssh_key", True)

    result = discover_ssh_key()

    assert result == str(id_ed25519)


def test_discover_ssh_key_prefers_ed25519(tmp_path, mocker):
    """Test SSH key discovery prefers ed25519 over rsa."""
    fake_ssh_dir = tmp_path / ".ssh"
    fake_ssh_dir.mkdir()

    # Create both keys
    id_rsa = fake_ssh_dir / "id_rsa"
    id_ed25519 = fake_ssh_dir / "id_ed25519"
    id_rsa.touch()
    id_ed25519.touch()

    # Use mocker.patch with proper attribute configuration
    mocker.patch("pathlib.Path.home", return_value=tmp_path)
    mocker.patch("linux_mcp_server.connection.ssh.CONFIG.ssh_key_path", None)
    mocker.patch("linux_mcp_server.connection.ssh.CONFIG.search_for_ssh_key", True)

    result = discover_ssh_key()

    # Should prefer ed25519
    assert result == str(id_ed25519)


def test_discover_ssh_key_no_keys_found(tmp_path, mocker):
    """Test SSH key discovery when no keys exist."""
    fake_ssh_dir = tmp_path / ".ssh"
    fake_ssh_dir.mkdir()

    mocker.patch("linux_mcp_server.connection.ssh.CONFIG.search_for_ssh_key", "yes")
    mocker.patch("pathlib.Path.home", return_value=tmp_path)

    result = discover_ssh_key()

    assert result is None
