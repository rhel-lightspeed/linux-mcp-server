import pytest

from linux_mcp_server.connection.ssh import discover_ssh_key


@pytest.fixture
def ssh_dir(tmp_path):
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()

    return ssh_dir


@pytest.fixture
def ssh_rsa(ssh_dir):
    id_rsa = ssh_dir / "id_rsa"
    id_rsa.touch()

    return id_rsa


@pytest.fixture
def ssh_ed25519(ssh_dir):
    id_ed25519 = ssh_dir / "id_ed25519"
    id_ed25519.touch()

    return id_ed25519


@pytest.fixture
def config_search(tmp_path, mocker):
    mocker.patch("pathlib.Path.home", return_value=tmp_path)
    mocker.patch("linux_mcp_server.connection.ssh.CONFIG.ssh_key_path", None)
    mocker.patch("linux_mcp_server.connection.ssh.CONFIG.search_for_ssh_key", True)


@pytest.fixture
def config_specify_key(ssh_ed25519, mocker):
    mocker.patch("pathlib.Path.home", return_value=ssh_ed25519.parent)
    mocker.patch("linux_mcp_server.connection.ssh.CONFIG.ssh_key_path", ssh_ed25519)


def test_discover_ssh_key_env_var_not_exists(tmp_path, mocker):
    """Test SSH key discovery with non-existent env var path."""
    key_path = tmp_path / "nonexistent_key"

    mocker.patch("linux_mcp_server.connection.ssh.CONFIG.ssh_key_path", key_path)

    result = discover_ssh_key()

    assert result is None


def test_discover_ssh_key_prefers_ed25519(tmp_path, ssh_rsa, ssh_ed25519, config_search):
    """Test SSH key discovery prefers ed25519 over rsa when both keys exist."""
    result = discover_ssh_key()

    assert result == str(ssh_ed25519)


def test_discover_ssh_key_no_keys_found(tmp_path, ssh_dir, config_search):
    """Test SSH key discovery when no keys exist."""
    result = discover_ssh_key()

    assert result is None


def test_discover_ssh_specify_key_path(tmp_path, ssh_ed25519, config_specify_key):
    """Test SSH key discovery whene the path to the key is specified in config"""
    result = discover_ssh_key()

    assert result == str(ssh_ed25519)
