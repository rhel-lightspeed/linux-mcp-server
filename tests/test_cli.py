"""Tests for the CLI argument parsing and transport configuration."""

import pytest

from typer.testing import CliRunner

from linux_mcp_server.__main__ import app


runner = CliRunner()


class TestCLITransports:
    """Test CLI transport options."""

    def test_cli_default_stdio_transport(self, mocker):
        """Test that cli() with no args uses stdio transport by default."""
        mock_main = mocker.patch("linux_mcp_server.__main__.main")
        mock_setup_logging = mocker.patch("linux_mcp_server.__main__.setup_logging")

        result = runner.invoke(app, [])

        assert result.exit_code == 0
        mock_setup_logging.assert_called_once()
        mock_main.assert_called_once_with(
            transport="stdio",
            show_banner=False,
        )

    def test_cli_stdio_transport_explicit(self, mocker):
        """Test cli with explicit stdio transport."""
        mock_main = mocker.patch("linux_mcp_server.__main__.main")
        mocker.patch("linux_mcp_server.__main__.setup_logging")

        result = runner.invoke(app, ["--transport", "stdio"])

        assert result.exit_code == 0
        mock_main.assert_called_once_with(
            transport="stdio",
            show_banner=False,
        )

    def test_cli_sse_transport(self, mocker):
        """Test cli with SSE transport."""
        mock_main = mocker.patch("linux_mcp_server.__main__.main")
        mocker.patch("linux_mcp_server.__main__.setup_logging")

        result = runner.invoke(app, ["--transport", "sse"])

        assert result.exit_code == 0
        mock_main.assert_called_once_with(
            transport="sse",
            show_banner=False,
            host="127.0.0.1",
            port=8000,
        )

    def test_cli_http_transport(self, mocker):
        """Test cli with HTTP transport."""
        mock_main = mocker.patch("linux_mcp_server.__main__.main")
        mocker.patch("linux_mcp_server.__main__.setup_logging")

        result = runner.invoke(app, ["--transport", "http"])

        assert result.exit_code == 0
        mock_main.assert_called_once_with(
            transport="http",
            show_banner=False,
            host="127.0.0.1",
            port=8000,
        )

    def test_cli_streamable_http_transport(self, mocker):
        """Test cli with streamable-http transport."""
        mock_main = mocker.patch("linux_mcp_server.__main__.main")
        mocker.patch("linux_mcp_server.__main__.setup_logging")

        result = runner.invoke(app, ["--transport", "streamable-http"])

        assert result.exit_code == 0
        mock_main.assert_called_once_with(
            transport="streamable-http",
            show_banner=False,
            host="127.0.0.1",
            port=8000,
        )


class TestCLIOptions:
    """Test CLI options for HTTP/SSE transports."""

    def test_cli_custom_host(self, mocker):
        """Test cli with custom host."""
        mock_main = mocker.patch("linux_mcp_server.__main__.main")
        mocker.patch("linux_mcp_server.__main__.setup_logging")

        result = runner.invoke(app, ["--transport", "sse", "--host", "0.0.0.0"])

        assert result.exit_code == 0
        mock_main.assert_called_once_with(
            transport="sse",
            show_banner=False,
            host="0.0.0.0",
            port=8000,
        )

    def test_cli_custom_port(self, mocker):
        """Test cli with custom port."""
        mock_main = mocker.patch("linux_mcp_server.__main__.main")
        mocker.patch("linux_mcp_server.__main__.setup_logging")

        result = runner.invoke(app, ["--transport", "http", "--port", "3000"])

        assert result.exit_code == 0
        mock_main.assert_called_once_with(
            transport="http",
            show_banner=False,
            host="127.0.0.1",
            port=3000,
        )

    def test_cli_custom_path(self, mocker):
        """Test cli with custom endpoint path."""
        mock_main = mocker.patch("linux_mcp_server.__main__.main")
        mocker.patch("linux_mcp_server.__main__.setup_logging")

        result = runner.invoke(app, ["--transport", "sse", "--path", "/api/mcp"])

        assert result.exit_code == 0
        mock_main.assert_called_once_with(
            transport="sse",
            show_banner=False,
            host="127.0.0.1",
            port=8000,
            path="/api/mcp",
        )

    def test_cli_custom_log_level(self, mocker):
        """Test cli with custom log level."""
        mock_main = mocker.patch("linux_mcp_server.__main__.main")
        mocker.patch("linux_mcp_server.__main__.setup_logging")

        result = runner.invoke(app, ["--transport", "http", "--log-level", "debug"])

        assert result.exit_code == 0
        mock_main.assert_called_once_with(
            transport="http",
            show_banner=False,
            host="127.0.0.1",
            port=8000,
            log_level="debug",
        )

    def test_cli_all_http_options(self, mocker):
        """Test cli with all HTTP transport options."""
        mock_main = mocker.patch("linux_mcp_server.__main__.main")
        mocker.patch("linux_mcp_server.__main__.setup_logging")

        result = runner.invoke(
            app,
            [
                "--transport",
                "streamable-http",
                "--host",
                "0.0.0.0",
                "--port",
                "9000",
                "--path",
                "/mcp",
                "--log-level",
                "debug",
            ],
        )

        assert result.exit_code == 0
        mock_main.assert_called_once_with(
            transport="streamable-http",
            show_banner=False,
            host="0.0.0.0",
            port=9000,
            path="/mcp",
            log_level="debug",
        )

    def test_cli_show_banner(self, mocker):
        """Test cli with --show-banner flag."""
        mock_main = mocker.patch("linux_mcp_server.__main__.main")
        mocker.patch("linux_mcp_server.__main__.setup_logging")

        result = runner.invoke(app, ["--show-banner"])

        assert result.exit_code == 0
        mock_main.assert_called_once_with(
            transport="stdio",
            show_banner=True,
        )

    def test_cli_http_options_not_passed_to_stdio(self, mocker):
        """Test that HTTP-specific options are not passed to stdio transport."""
        mock_main = mocker.patch("linux_mcp_server.__main__.main")
        mocker.patch("linux_mcp_server.__main__.setup_logging")

        result = runner.invoke(
            app,
            [
                "--transport",
                "stdio",
                "--host",
                "0.0.0.0",  # Should be ignored
                "--port",
                "9000",  # Should be ignored
                "--path",
                "/test",  # Should be ignored
                "--log-level",
                "debug",  # Should be ignored
            ],
        )

        assert result.exit_code == 0
        # stdio transport should not receive HTTP-specific kwargs
        mock_main.assert_called_once_with(
            transport="stdio",
            show_banner=False,
        )


class TestCLIArgumentValidation:
    """Test CLI argument validation and error handling."""

    def test_cli_version(self):
        """Test cli with --version flag."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "linux-mcp-server" in result.stdout

    def test_cli_help(self):
        """Test cli with --help flag."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "Linux MCP Server" in result.stdout
        assert "transport" in result.stdout

    def test_cli_invalid_transport(self):
        """Test cli with invalid transport value."""
        result = runner.invoke(app, ["--transport", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output

    def test_cli_invalid_log_level(self):
        """Test cli with invalid log level value."""
        result = runner.invoke(app, ["--transport", "sse", "--log-level", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def test_cli_keyboard_interrupt(self, mocker):
        """Test that KeyboardInterrupt exits gracefully with code 0."""
        mocker.patch("linux_mcp_server.__main__.setup_logging")
        mocker.patch("linux_mcp_server.__main__.main", side_effect=KeyboardInterrupt)

        result = runner.invoke(app, [])

        assert result.exit_code == 0

    def test_cli_exception_handling(self, mocker):
        """Test that exceptions are logged and exit with code 1."""
        mocker.patch("linux_mcp_server.__main__.setup_logging")
        mocker.patch(
            "linux_mcp_server.__main__.main",
            side_effect=RuntimeError("Test error"),
        )

        result = runner.invoke(app, [])

        assert result.exit_code == 1

    def test_cli_value_error_handling(self, mocker):
        """Test that ValueError is caught and exits with code 1."""
        mocker.patch("linux_mcp_server.__main__.setup_logging")
        mocker.patch(
            "linux_mcp_server.__main__.main",
            side_effect=ValueError("Invalid configuration"),
        )

        result = runner.invoke(app, [])

        assert result.exit_code == 1
