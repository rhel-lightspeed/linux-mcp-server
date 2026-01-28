"""Tests for the CLI argument parsing and configuration."""

import subprocess
import sys

from linux_mcp_server.config import Config


class TestConfigurationViaEnvironmentVariables:
    """Test configuration via environment variables."""

    def test_default_configuration(self, monkeypatch):
        """Test that default configuration is set correctly."""
        monkeypatch.setattr(sys, "argv", ["prog"])
        config = Config()

        assert config.transport.value == "stdio"
        assert config.host is None
        assert config.port is None
        assert config.path is None

    def test_env_transport(self, monkeypatch):
        """Test transport configuration via environment variable."""
        monkeypatch.setenv("LINUX_MCP_TRANSPORT", "http")
        monkeypatch.setattr(sys, "argv", ["prog"])
        config = Config()

        assert config.transport.value == "http"

    def test_env_host(self, monkeypatch):
        """Test host configuration via environment variable."""
        monkeypatch.setenv("LINUX_MCP_HOST", "0.0.0.0")
        monkeypatch.setattr(sys, "argv", ["prog"])
        config = Config()

        assert config.host == "0.0.0.0"

    def test_env_port(self, monkeypatch):
        """Test port configuration via environment variable."""
        monkeypatch.setenv("LINUX_MCP_PORT", "9000")
        monkeypatch.setattr(sys, "argv", ["prog"])
        config = Config()

        assert config.port == 9000

    def test_env_path(self, monkeypatch):
        """Test path configuration via environment variable."""
        monkeypatch.setenv("LINUX_MCP_PATH", "/api/mcp")
        monkeypatch.setattr(sys, "argv", ["prog"])
        config = Config()

        assert config.path == "/api/mcp"


    def test_env_all_options(self, monkeypatch):
        """Test all configuration options via environment variables."""
        monkeypatch.setenv("LINUX_MCP_TRANSPORT", "http")
        monkeypatch.setenv("LINUX_MCP_HOST", "0.0.0.0")
        monkeypatch.setenv("LINUX_MCP_PORT", "9000")
        monkeypatch.setenv("LINUX_MCP_PATH", "/mcp")
        monkeypatch.setenv("LINUX_MCP_LOG_LEVEL", "DEBUG")
        monkeypatch.setattr(sys, "argv", ["prog"])
        config = Config()

        assert config.transport.value == "http"
        assert config.host == "0.0.0.0"
        assert config.port == 9000
        assert config.path == "/mcp"
        assert config.log_level == "DEBUG"

    def test_transport_kwargs_stdio(self, monkeypatch):
        """Test transport_kwargs for stdio transport."""
        monkeypatch.setattr(sys, "argv", ["prog"])
        config = Config()

        kwargs = config.transport_kwargs
        assert kwargs == {}

    def test_transport_kwargs_http(self, monkeypatch):
        """Test transport_kwargs for HTTP transport."""
        monkeypatch.setenv("LINUX_MCP_TRANSPORT", "http")
        monkeypatch.setenv("LINUX_MCP_HOST", "127.0.0.1")
        monkeypatch.setenv("LINUX_MCP_PORT", "8000")
        monkeypatch.setenv("LINUX_MCP_PATH", "/api")
        monkeypatch.setenv("LINUX_MCP_LOG_LEVEL", "INFO")
        monkeypatch.setattr(sys, "argv", ["prog"])
        config = Config()

        kwargs = config.transport_kwargs
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] == 8000
        assert kwargs["path"] == "/api"
        assert kwargs["log_level"] == "INFO"


class TestCLIHelp:
    """Test CLI help functionality."""

    def test_cli_help_works(self):
        """Test that --help flag works."""
        result = subprocess.run(
            ["uv", "run", "linux-mcp-server", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "--transport" in result.stdout
        assert "--host" in result.stdout
        assert "--port" in result.stdout


class TestMainEntryPoint:
    """Test the main entry point."""

    def test_main_runs_with_config(self, mocker):
        """Test that main() uses CONFIG."""
        mock_run = mocker.patch("linux_mcp_server.server.mcp.run")

        from linux_mcp_server.server import main

        main()

        # Verify mcp.run was called
        assert mock_run.called

    def test_keyboard_interrupt_handling(self, mocker):
        """Test that KeyboardInterrupt exits gracefully."""
        mocker.patch("linux_mcp_server.server.mcp.run", side_effect=KeyboardInterrupt)
        mocker.patch("linux_mcp_server.logging_config.setup_logging")
        mock_exit = mocker.patch("sys.exit")

        from linux_mcp_server.__main__ import cli

        cli()

        mock_exit.assert_called_once_with(0)

    def test_exception_handling(self, mocker):
        """Test that exceptions are logged and exit with code 1."""
        mocker.patch(
            "linux_mcp_server.server.mcp.run",
            side_effect=RuntimeError("Test error"),
        )
        mocker.patch("linux_mcp_server.logging_config.setup_logging")
        mock_exit = mocker.patch("sys.exit")

        from linux_mcp_server.__main__ import cli

        cli()

        mock_exit.assert_called_once_with(1)
