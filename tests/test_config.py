"""Unit tests for linux_mcp_server.config module"""

from pathlib import Path

from pydantic import SecretStr

from linux_mcp_server.config import Config


class TestConfig:
    """Test cases for Config class"""

    def test_custom_values(self, mocker):
        """Test that Config accepts custom values"""
        mocker.patch("getpass.getuser", return_value="testuser")

        config = Config(
            user="customuser",
            log_dir=Path("/var/log/custom"),
            log_level="DEBUG",
            log_retention_days=30,
            allowed_log_paths="/var/log:/tmp",
            ssh_key_path=Path("/home/user/.ssh/id_rsa"),
            key_passphrase=SecretStr("secret"),
            search_for_ssh_key=True,
        )

        assert config.user == "customuser"
        assert config.log_dir == Path("/var/log/custom")
        assert config.log_level == "DEBUG"
        assert config.log_retention_days == 30
        assert config.allowed_log_paths == "/var/log:/tmp"
        assert config.ssh_key_path == Path("/home/user/.ssh/id_rsa")
        assert config.key_passphrase.get_secret_value() == "secret"
        assert config.search_for_ssh_key is True

    def test_env_var_override_log_level(self, mocker, monkeypatch):
        """Test that LINUX_MCP_LOG_LEVEL environment variable overrides default"""
        mocker.patch("getpass.getuser", return_value="testuser")
        monkeypatch.setenv("LINUX_MCP_LOG_LEVEL", "WARNING")

        config = Config()

        assert config.log_level == "WARNING"

    def test_env_var_override_log_dir(self, mocker, monkeypatch):
        """Test that LINUX_MCP_LOG_DIR environment variable works"""
        mocker.patch("getpass.getuser", return_value="testuser")
        monkeypatch.setenv("LINUX_MCP_LOG_DIR", "/custom/log/dir")

        config = Config()

        assert config.log_dir == Path("/custom/log/dir")

    def test_env_var_override_log_retention_days(self, mocker, monkeypatch):
        """Test that LINUX_MCP_LOG_RETENTION_DAYS environment variable works"""
        mocker.patch("getpass.getuser", return_value="testuser")
        monkeypatch.setenv("LINUX_MCP_LOG_RETENTION_DAYS", "45")

        config = Config()

        assert config.log_retention_days == 45

    def test_env_var_override_user(self, mocker, monkeypatch):
        """Test that LINUX_MCP_USER environment variable overrides getpass.getuser()"""
        mocker.patch("getpass.getuser", return_value="testuser")
        monkeypatch.setenv("LINUX_MCP_USER", "envuser")

        config = Config()

        assert config.user == "envuser"

    def test_env_var_override_ssh_key_path(self, mocker, monkeypatch):
        """Test that LINUX_MCP_SSH_KEY_PATH environment variable works"""
        mocker.patch("getpass.getuser", return_value="testuser")
        monkeypatch.setenv("LINUX_MCP_SSH_KEY_PATH", "/home/user/.ssh/custom_key")

        config = Config()

        assert config.ssh_key_path == Path("/home/user/.ssh/custom_key")

    def test_env_var_override_key_passphrase(self, mocker, monkeypatch):
        """Test that LINUX_MCP_KEY_PASSPHRASE environment variable works"""
        mocker.patch("getpass.getuser", return_value="testuser")
        monkeypatch.setenv("LINUX_MCP_KEY_PASSPHRASE", "my_secret_passphrase")

        config = Config()

        assert config.key_passphrase.get_secret_value() == "my_secret_passphrase"

    def test_env_var_override_search_for_ssh_key(self, mocker, monkeypatch):
        """Test that LINUX_MCP_SEARCH_FOR_SSH_KEY environment variable works"""
        mocker.patch("getpass.getuser", return_value="testuser")
        monkeypatch.setenv("LINUX_MCP_SEARCH_FOR_SSH_KEY", "true")

        config = Config()

        assert config.search_for_ssh_key is True

    def test_env_var_override_allowed_log_paths(self, mocker, monkeypatch):
        """Test that LINUX_MCP_ALLOWED_LOG_PATHS environment variable works"""
        mocker.patch("getpass.getuser", return_value="testuser")
        monkeypatch.setenv("LINUX_MCP_ALLOWED_LOG_PATHS", "/var/log:/tmp:/home/logs")

        config = Config()

        assert config.allowed_log_paths == "/var/log:/tmp:/home/logs"

    def test_env_ignore_empty(self, mocker, monkeypatch):
        """Test that empty environment variables are ignored"""
        mocker.patch("getpass.getuser", return_value="testuser")
        monkeypatch.setenv("LINUX_MCP_LOG_LEVEL", "")

        config = Config()

        # Should use default value, not empty string
        assert config.log_level == "INFO"

    def test_normalize_log_level_lowercase(self, mocker):
        """Test that log_level validator converts lowercase to uppercase"""
        mocker.patch("getpass.getuser", return_value="testuser")

        config = Config(log_level="debug")

        assert config.log_level == "DEBUG"

    def test_normalize_log_level_uppercase(self, mocker):
        """Test that log_level validator keeps uppercase as is"""
        mocker.patch("getpass.getuser", return_value="testuser")

        config = Config(log_level="ERROR")

        assert config.log_level == "ERROR"

    def test_normalize_log_level_mixed_case(self, mocker):
        """Test that log_level validator converts mixed case to uppercase"""
        mocker.patch("getpass.getuser", return_value="testuser")

        config = Config(log_level="WaRnInG")

        assert config.log_level == "WARNING"

    def test_path_conversion_log_dir(self, mocker):
        """Test that log_dir is properly converted to Path object"""
        mocker.patch("getpass.getuser", return_value="testuser")

        config = Config(log_dir=Path("/var/log/test"))

        assert isinstance(config.log_dir, Path)
        assert str(config.log_dir) == "/var/log/test"

    def test_path_conversion_ssh_key_path(self, mocker):
        """Test that ssh_key_path is properly converted to Path object"""
        mocker.patch("getpass.getuser", return_value="testuser")

        config = Config(ssh_key_path=Path("~/.ssh/id_rsa"))

        assert isinstance(config.ssh_key_path, Path)
        assert str(config.ssh_key_path) == "~/.ssh/id_rsa"

    def test_log_retention_days_type(self, mocker):
        """Test that log_retention_days accepts integer"""
        mocker.patch("getpass.getuser", return_value="testuser")

        config = Config(log_retention_days=15)

        assert isinstance(config.log_retention_days, int)
        assert config.log_retention_days == 15

    def test_search_for_ssh_key_type(self, mocker):
        """Test that search_for_ssh_key accepts boolean"""
        mocker.patch("getpass.getuser", return_value="testuser")

        config = Config(search_for_ssh_key=True)

        assert isinstance(config.search_for_ssh_key, bool)
        assert config.search_for_ssh_key is True


class TestEffectiveKnownHostsPath:
    """Test cases for the effective_known_hosts_path property."""

    def test_returns_custom_path_when_set(self, mocker):
        """Test that effective_known_hosts_path returns the custom path when configured."""
        custom_path = Path("/custom/known_hosts")

        config = Config(known_hosts_path=custom_path)

        assert config.effective_known_hosts_path == custom_path

    def test_returns_default_when_not_set(self, mocker):
        """Test that effective_known_hosts_path returns ~/.ssh/known_hosts when not configured."""
        mocker.patch("pathlib.Path.home", return_value=Path("/home/testuser"))

        config = Config(user="testuser")

        assert config.effective_known_hosts_path == Path("/home/testuser/.ssh/known_hosts")


class TestConfigEdgeCases:
    """Test edge cases and error conditions"""

    def test_none_values_for_optional_fields(self, mocker):
        """Test that optional fields can be None"""
        mocker.patch("getpass.getuser", return_value="testuser")

        config = Config(
            allowed_log_paths=None,
            ssh_key_path=None,
        )

        assert config.allowed_log_paths is None
        assert config.ssh_key_path is None

    def test_empty_string_log_level_validation(self, mocker):
        """Test log_level validator with empty string"""
        mocker.patch("getpass.getuser", return_value="testuser")

        config = Config(log_level="")

        assert config.log_level == ""

    def test_special_characters_in_paths(self, mocker):
        """Test that paths with special characters are handled"""
        mocker.patch("getpass.getuser", return_value="testuser")

        config = Config(
            log_dir=Path("/var/log/my-app/2024"),
            ssh_key_path=Path("/home/user/.ssh/id_rsa_2024-key"),
        )

        assert str(config.log_dir) == "/var/log/my-app/2024"
        assert str(config.ssh_key_path) == "/home/user/.ssh/id_rsa_2024-key"

    def test_multiple_env_vars_together(self, mocker, monkeypatch):
        """Test multiple environment variables set at once"""
        mocker.patch("getpass.getuser", return_value="testuser")
        monkeypatch.setenv("LINUX_MCP_LOG_LEVEL", "ERROR")
        monkeypatch.setenv("LINUX_MCP_LOG_RETENTION_DAYS", "60")
        monkeypatch.setenv("LINUX_MCP_SEARCH_FOR_SSH_KEY", "1")

        config = Config()

        assert config.log_level == "ERROR"
        assert config.log_retention_days == 60
        assert config.search_for_ssh_key is True

    def test_model_config_settings(self, mocker):
        """Test that model_config is properly set"""
        mocker.patch("getpass.getuser", return_value="testuser")

        config = Config()

        assert hasattr(config, "model_config")
        # Enforce that we have the prefix to maintain compatibility.
        # Ignoring the error here is fine, as this will always exist for the config class.
        assert config.model_config["env_prefix"] == "LINUX_MCP_"  # pyright: ignore[reportTypedDictNotRequiredAccess]
