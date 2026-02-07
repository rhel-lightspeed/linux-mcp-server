"""Tests for dnf package manager tools."""

import pytest

from linux_mcp_server.utils.validation import validate_dnf_package_name


class TestDnfValidation:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("bash", "bash"),
            ("openssl-libs", "openssl-libs"),
            ("python3.12", "python3.12"),
            ("glibc:2.28", "glibc:2.28"),
        ],
    )
    def test_validate_dnf_package_name_valid(self, value, expected):
        assert validate_dnf_package_name(value) == expected

    @pytest.mark.parametrize(
        "value",
        [
            "",
            " ",
            "bad name",
            "bad\tname",
            "bad\nname",
            "-bad",
            "bad/name",
            "bad*name",
            "bad?name",
        ],
    )
    def test_validate_dnf_package_name_invalid(self, value):
        with pytest.raises(ValueError):
            validate_dnf_package_name(value)


class TestDnfToolsRemote:
    @pytest.mark.parametrize(
        "tool_name",
        [
            "list_dnf_installed_packages",
            "list_dnf_available_packages",
            "list_dnf_repositories",
        ],
    )
    async def test_dnf_list_tools_success(self, mcp_client, mock_execute_with_fallback, tool_name):
        mock_execute_with_fallback.return_value = (0, "Some dnf output", "")

        result = await mcp_client.call_tool(
            tool_name,
            arguments={"host": "remote.example.com"},
        )
        result_text = result.content[0].text

        assert "Some dnf output" in result_text
        call_kwargs = mock_execute_with_fallback.call_args[1]
        assert call_kwargs["host"] == "remote.example.com"

    async def test_dnf_list_tools_empty_output(self, mcp_client, mock_execute_with_fallback):
        mock_execute_with_fallback.return_value = (0, "   ", "")

        result = await mcp_client.call_tool(
            "list_dnf_installed_packages",
            arguments={"host": "remote.example.com"},
        )
        result_text = result.content[0].text.casefold()

        assert "no output returned" in result_text

    async def test_dnf_list_tools_error(self, mcp_client, mock_execute_with_fallback):
        mock_execute_with_fallback.return_value = (1, "", "dnf error")

        result = await mcp_client.call_tool(
            "list_dnf_available_packages",
            arguments={"host": "remote.example.com"},
        )
        result_text = result.content[0].text.casefold()

        assert "error running dnf" in result_text
        assert "dnf error" in result_text

    async def test_get_dnf_package_info_success(self, mcp_client, mock_execute_with_fallback):
        mock_execute_with_fallback.return_value = (0, "Name : bash", "")

        result = await mcp_client.call_tool(
            "get_dnf_package_info",
            arguments={"package": "bash", "host": "remote.example.com"},
        )
        result_text = result.content[0].text

        assert "Name : bash" in result_text

    async def test_get_dnf_package_info_not_found(self, mcp_client, mock_execute_with_fallback):
        mock_execute_with_fallback.return_value = (1, "", "No match for argument: missing")

        result = await mcp_client.call_tool(
            "get_dnf_package_info",
            arguments={"package": "missing", "host": "remote.example.com"},
        )
        result_text = result.content[0].text.casefold()

        assert "not found" in result_text

    async def test_get_dnf_package_info_error(self, mcp_client, mock_execute_with_fallback):
        mock_execute_with_fallback.return_value = (1, "", "dnf error")

        result = await mcp_client.call_tool(
            "get_dnf_package_info",
            arguments={"package": "bash", "host": "remote.example.com"},
        )
        result_text = result.content[0].text.casefold()

        assert "error running dnf" in result_text

    async def test_get_dnf_package_info_empty_output(self, mcp_client, mock_execute_with_fallback):
        mock_execute_with_fallback.return_value = (0, " ", "")

        result = await mcp_client.call_tool(
            "get_dnf_package_info",
            arguments={"package": "bash", "host": "remote.example.com"},
        )
        result_text = result.content[0].text.casefold()

        assert "no output returned" in result_text

    async def test_get_dnf_package_info_invalid_package_name(self, mcp_client, mock_execute_with_fallback):
        with pytest.raises(Exception) as exc_info:
            await mcp_client.call_tool(
                "get_dnf_package_info",
                arguments={"package": "bad name", "host": "remote.example.com"},
            )

        assert "validation" in str(exc_info.value).casefold() or "invalid" in str(exc_info.value).casefold()
        mock_execute_with_fallback.assert_not_called()
