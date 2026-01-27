"""Tests for the CLI argument parsing and transport configuration."""

import pytest

from linux_mcp_server.__main__ import cli


class TestCLITransports:
    """Test CLI transport options."""

    def test_cli_default_stdio_transport(self, mocker):
        """Test that cli() with no args uses stdio transport by default."""
        mock_main = mocker.patch("linux_mcp_server.__main__.main")
        mock_setup_logging = mocker.patch("linux_mcp_server.__main__.setup_logging")
        mocker.patch("sys.argv", ["linux-mcp-server"])

        cli()

        mock_setup_logging.assert_called_once()
        mock_main.assert_called_once_with(
            transport="stdio",
            show_banner=False,
        )

    def test_cli_stdio_transport_explicit(self, mocker):
        """Test cli with explicit stdio transport."""
        mock_main = mocker.patch("linux_mcp_server.__main__.main")
        mocker.patch("linux_mcp_server.__main__.setup_logging")
        mocker.patch("sys.argv", ["linux-mcp-server", "--transport", "stdio"])

        cli()

        mock_main.assert_called_once_with(
            transport="stdio",
            show_banner=False,
        )

    def test_cli_sse_transport(self, mocker):
        """Test cli with SSE transport."""
        mock_main = mocker.patch("linux_mcp_server.__main__.main")
        mocker.patch("linux_mcp_server.__main__.setup_logging")
        mocker.patch("sys.argv", ["linux-mcp-server", "--transport", "sse"])

        cli()

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
        mocker.patch("sys.argv", ["linux-mcp-server", "--transport", "http"])

        cli()

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
        mocker.patch(
            "sys.argv",
            ["linux-mcp-server", "--transport", "streamable-http"],
        )

        cli()

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
        mocker.patch(
            "sys.argv",
            ["linux-mcp-server", "--transport", "sse", "--host", "0.0.0.0"],
        )

        cli()

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
        mocker.patch(
            "sys.argv",
            ["linux-mcp-server", "--transport", "http", "--port", "3000"],
        )

        cli()

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
        mocker.patch(
            "sys.argv",
            ["linux-mcp-server", "--transport", "sse", "--path", "/api/mcp"],
        )

        cli()

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
        mocker.patch(
            "sys.argv",
            ["linux-mcp-server", "--transport", "http", "--log-level", "debug"],
        )

        cli()

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
        mocker.patch(
            "sys.argv",
            [
                "linux-mcp-server",
                "--transport", "streamable-http",
                "--host", "0.0.0.0",
                "--port", "9000",
                "--path", "/mcp",
                "--log-level", "debug",
            ],
        )

        cli()

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
        mocker.patch("sys.argv", ["linux-mcp-server", "--show-banner"])

        cli()

        mock_main.assert_called_once_with(
            transport="stdio",
            show_banner=True,
        )

    def test_cli_http_options_not_passed_to_stdio(self, mocker):
        """Test that HTTP-specific options are not passed to stdio transport."""
        mock_main = mocker.patch("linux_mcp_server.__main__.main")
        mocker.patch("linux_mcp_server.__main__.setup_logging")
        mocker.patch(
            "sys.argv",
            [
                "linux-mcp-server",
                "--transport", "stdio",
                "--host", "0.0.0.0",  # Should be ignored
                "--port", "9000",     # Should be ignored
                "--path", "/test",    # Should be ignored
                "--log-level", "debug",  # Should be ignored
            ],
        )

        cli()

        # stdio transport should not receive HTTP-specific kwargs
        mock_main.assert_called_once_with(
            transport="stdio",
            show_banner=False,
        )


class TestCLIArgumentValidation:
    """Test CLI argument validation and error handling."""

    def test_cli_version(self, mocker, capsys):
        """Test cli with --version flag."""
        mocker.patch("sys.argv", ["linux-mcp-server", "--version"])

        with pytest.raises(SystemExit) as exc_info:
            cli()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "linux-mcp-server" in captured.out

    def test_cli_help(self, mocker, capsys):
        """Test cli with --help flag."""
        mocker.patch("sys.argv", ["linux-mcp-server", "--help"])

        with pytest.raises(SystemExit) as exc_info:
            cli()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Linux MCP Server" in captured.out
        assert "transport" in captured.out

    def test_cli_invalid_transport(self, mocker, capsys):
        """Test cli with invalid transport value."""
        mocker.patch("sys.argv", ["linux-mcp-server", "--transport", "invalid"])

        with pytest.raises(SystemExit) as exc_info:
            cli()

        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert "invalid choice" in captured.err

    def test_cli_invalid_log_level(self, mocker, capsys):
        """Test cli with invalid log level value."""
        mocker.patch(
            "sys.argv",
            ["linux-mcp-server", "--transport", "sse", "--log-level", "invalid"],
        )

        with pytest.raises(SystemExit) as exc_info:
            cli()

        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert "invalid choice" in captured.err


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def test_cli_keyboard_interrupt(self, mocker):
        """Test that KeyboardInterrupt exits gracefully with code 0."""
        mocker.patch("linux_mcp_server.__main__.setup_logging")
        mocker.patch("linux_mcp_server.__main__.main", side_effect=KeyboardInterrupt)
        mocker.patch("sys.argv", ["linux-mcp-server"])

        with pytest.raises(SystemExit) as exc_info:
            cli()

        assert exc_info.value.code == 0

    def test_cli_exception_handling(self, mocker):
        """Test that exceptions are logged and exit with code 1."""
        mocker.patch("linux_mcp_server.__main__.setup_logging")
        mocker.patch(
            "linux_mcp_server.__main__.main",
            side_effect=RuntimeError("Test error"),
        )
        mocker.patch("sys.argv", ["linux-mcp-server"])

        with pytest.raises(SystemExit) as exc_info:
            cli()

        assert exc_info.value.code == 1

    def test_cli_value_error_handling(self, mocker):
        """Test that ValueError is caught and exits with code 1."""
        mocker.patch("linux_mcp_server.__main__.setup_logging")
        mocker.patch(
            "linux_mcp_server.__main__.main",
            side_effect=ValueError("Invalid configuration"),
        )
        mocker.patch("sys.argv", ["linux-mcp-server"])

        with pytest.raises(SystemExit) as exc_info:
            cli()

        assert exc_info.value.code == 1
