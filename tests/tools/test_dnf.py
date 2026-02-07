"""Tests for dnf package manager tools."""

import pytest

from linux_mcp_server.utils.validation import validate_dnf_group_name
from linux_mcp_server.utils.validation import validate_dnf_module_name
from linux_mcp_server.utils.validation import validate_dnf_package_name
from linux_mcp_server.utils.validation import validate_dnf_provides_query
from linux_mcp_server.utils.validation import validate_dnf_repo_id
from linux_mcp_server.utils.validation import validate_optional_dnf_module_name


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

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("baseos", "baseos"),
            ("appstream", "appstream"),
            ("custom-repo", "custom-repo"),
            ("repo:1", "repo:1"),
        ],
    )
    def test_validate_dnf_repo_id_valid(self, value, expected):
        assert validate_dnf_repo_id(value) == expected

    @pytest.mark.parametrize(
        "value",
        [
            "",
            " ",
            "bad repo",
            "bad\trepo",
            "bad\nrepo",
            "-bad",
            "bad/repo",
            "bad*repo",
        ],
    )
    def test_validate_dnf_repo_id_invalid(self, value):
        with pytest.raises(ValueError):
            validate_dnf_repo_id(value)

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("Development Tools", "Development Tools"),
            ("Server with GUI", "Server with GUI"),
            ("Container Management", "Container Management"),
            ("Workstation & GUI", "Workstation & GUI"),
        ],
    )
    def test_validate_dnf_group_name_valid(self, value, expected):
        assert validate_dnf_group_name(value) == expected

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "\t",
            "bad\tname",
            "bad\nname",
            "-bad",
            "bad/name",
            "bad*name",
        ],
    )
    def test_validate_dnf_group_name_invalid(self, value):
        with pytest.raises(ValueError):
            validate_dnf_group_name(value)

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("nodejs", "nodejs"),
            ("python39", "python39"),
            ("nodejs:18", "nodejs:18"),
        ],
    )
    def test_validate_dnf_module_name_valid(self, value, expected):
        assert validate_dnf_module_name(value) == expected

    @pytest.mark.parametrize(
        "value",
        [
            "",
            " ",
            "bad name",
            "-bad",
            "bad/name",
            "bad*name",
        ],
    )
    def test_validate_dnf_module_name_invalid(self, value):
        with pytest.raises(ValueError):
            validate_dnf_module_name(value)

    def test_validate_optional_dnf_module_name_none(self):
        assert validate_optional_dnf_module_name(None) is None

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("/usr/bin/python3", "/usr/bin/python3"),
            ("libssl.so.3", "libssl.so.3"),
            ("*/libssl.so.*", "*/libssl.so.*"),
            ("usr/lib64/libcrypto.so.3", "usr/lib64/libcrypto.so.3"),
        ],
    )
    def test_validate_dnf_provides_query_valid(self, value, expected):
        assert validate_dnf_provides_query(value) == expected

    @pytest.mark.parametrize(
        "value",
        [
            "",
            " ",
            "bad name",
            "bad\tname",
            "bad\nname",
            "-bad",
            "../usr/bin/bash",
            "bad|name",
        ],
    )
    def test_validate_dnf_provides_query_invalid(self, value):
        with pytest.raises(ValueError):
            validate_dnf_provides_query(value)


class TestDnfToolsRemote:
    @pytest.mark.parametrize(
        "tool_name",
        [
            "list_dnf_installed_packages",
            "list_dnf_available_packages",
            "list_dnf_repositories",
            "list_dnf_groups",
            "get_dnf_group_summary",
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

    async def test_dnf_provides_success(self, mcp_client, mock_execute_with_fallback):
        mock_execute_with_fallback.return_value = (0, "file provided by", "")

        result = await mcp_client.call_tool(
            "dnf_provides",
            arguments={"query": "/usr/bin/python3", "host": "remote.example.com"},
        )
        result_text = result.content[0].text

        assert "file provided by" in result_text

    async def test_dnf_provides_not_found(self, mcp_client, mock_execute_with_fallback):
        mock_execute_with_fallback.return_value = (1, "", "No matches found")

        result = await mcp_client.call_tool(
            "dnf_provides",
            arguments={"query": "/missing/file", "host": "remote.example.com"},
        )
        result_text = result.content[0].text.casefold()

        assert "no packages provide" in result_text

    async def test_dnf_provides_invalid_query(self, mcp_client, mock_execute_with_fallback):
        with pytest.raises(Exception) as exc_info:
            await mcp_client.call_tool(
                "dnf_provides",
                arguments={"query": "bad name", "host": "remote.example.com"},
            )

        assert "validation" in str(exc_info.value).casefold() or "invalid" in str(exc_info.value).casefold()
        mock_execute_with_fallback.assert_not_called()

    async def test_get_dnf_repo_info_success(self, mcp_client, mock_execute_with_fallback):
        mock_execute_with_fallback.return_value = (0, "Repo-id : baseos", "")

        result = await mcp_client.call_tool(
            "get_dnf_repo_info",
            arguments={"repo_id": "baseos", "host": "remote.example.com"},
        )
        result_text = result.content[0].text

        assert "Repo-id" in result_text

    async def test_get_dnf_repo_info_not_found(self, mcp_client, mock_execute_with_fallback):
        mock_execute_with_fallback.return_value = (1, "", "No matching repo to modify: missing")

        result = await mcp_client.call_tool(
            "get_dnf_repo_info",
            arguments={"repo_id": "missing", "host": "remote.example.com"},
        )
        result_text = result.content[0].text.casefold()

        assert "not found" in result_text

    async def test_get_dnf_repo_info_invalid_repo_id(self, mcp_client, mock_execute_with_fallback):
        with pytest.raises(Exception) as exc_info:
            await mcp_client.call_tool(
                "get_dnf_repo_info",
                arguments={"repo_id": "bad repo", "host": "remote.example.com"},
            )

        assert "validation" in str(exc_info.value).casefold() or "invalid" in str(exc_info.value).casefold()
        mock_execute_with_fallback.assert_not_called()

    async def test_get_dnf_group_info_success(self, mcp_client, mock_execute_with_fallback):
        mock_execute_with_fallback.return_value = (0, "Group: Development Tools", "")

        result = await mcp_client.call_tool(
            "get_dnf_group_info",
            arguments={"group": "Development Tools", "host": "remote.example.com"},
        )
        result_text = result.content[0].text

        assert "Development Tools" in result_text

    async def test_get_dnf_group_info_not_found(self, mcp_client, mock_execute_with_fallback):
        mock_execute_with_fallback.return_value = (1, "", "No groups matched: Missing Group")

        result = await mcp_client.call_tool(
            "get_dnf_group_info",
            arguments={"group": "Missing Group", "host": "remote.example.com"},
        )
        result_text = result.content[0].text.casefold()

        assert "not found" in result_text

    async def test_get_dnf_group_info_invalid_name(self, mcp_client, mock_execute_with_fallback):
        with pytest.raises(Exception) as exc_info:
            await mcp_client.call_tool(
                "get_dnf_group_info",
                arguments={"group": "bad/name", "host": "remote.example.com"},
            )

        assert "validation" in str(exc_info.value).casefold() or "invalid" in str(exc_info.value).casefold()
        mock_execute_with_fallback.assert_not_called()

    async def test_list_dnf_modules_success(self, mcp_client, mock_execute_with_fallback):
        mock_execute_with_fallback.return_value = (0, "Name Stream Profiles", "")

        result = await mcp_client.call_tool(
            "list_dnf_modules",
            arguments={"host": "remote.example.com"},
        )
        result_text = result.content[0].text

        assert "Name Stream Profiles" in result_text

    async def test_list_dnf_modules_filtered_not_found(self, mcp_client, mock_execute_with_fallback):
        mock_execute_with_fallback.return_value = (0, "No matching modules to list", "")

        result = await mcp_client.call_tool(
            "list_dnf_modules",
            arguments={"module": "missing", "host": "remote.example.com"},
        )
        result_text = result.content[0].text.casefold()

        assert "no modules matched" in result_text

    async def test_list_dnf_modules_invalid_name(self, mcp_client, mock_execute_with_fallback):
        with pytest.raises(Exception) as exc_info:
            await mcp_client.call_tool(
                "list_dnf_modules",
                arguments={"module": "bad name", "host": "remote.example.com"},
            )

        assert "validation" in str(exc_info.value).casefold() or "invalid" in str(exc_info.value).casefold()
        mock_execute_with_fallback.assert_not_called()

    async def test_dnf_module_provides_success(self, mcp_client, mock_execute_with_fallback):
        mock_execute_with_fallback.return_value = (0, "module provides package", "")

        result = await mcp_client.call_tool(
            "dnf_module_provides",
            arguments={"package": "python3", "host": "remote.example.com"},
        )
        result_text = result.content[0].text

        assert "module provides package" in result_text

    async def test_dnf_module_provides_not_found(self, mcp_client, mock_execute_with_fallback):
        mock_execute_with_fallback.return_value = (1, "", "No matching modules")

        result = await mcp_client.call_tool(
            "dnf_module_provides",
            arguments={"package": "missing", "host": "remote.example.com"},
        )
        result_text = result.content[0].text.casefold()

        assert "no modules provide" in result_text

    async def test_dnf_module_provides_invalid_package(self, mcp_client, mock_execute_with_fallback):
        with pytest.raises(Exception) as exc_info:
            await mcp_client.call_tool(
                "dnf_module_provides",
                arguments={"package": "bad name", "host": "remote.example.com"},
            )

        assert "validation" in str(exc_info.value).casefold() or "invalid" in str(exc_info.value).casefold()
        mock_execute_with_fallback.assert_not_called()

    @pytest.mark.parametrize(
        ("tool_name", "arguments"),
        [
            ("dnf_provides", {"query": "/usr/bin/python3", "host": "remote.example.com"}),
            ("get_dnf_repo_info", {"repo_id": "baseos", "host": "remote.example.com"}),
            ("get_dnf_group_info", {"group": "Development Tools", "host": "remote.example.com"}),
            ("list_dnf_modules", {"module": "nodejs", "host": "remote.example.com"}),
            ("dnf_module_provides", {"package": "python3", "host": "remote.example.com"}),
        ],
    )
    async def test_dnf_new_tools_error(self, mcp_client, mock_execute_with_fallback, tool_name, arguments):
        mock_execute_with_fallback.return_value = (1, "", "dnf error")

        result = await mcp_client.call_tool(tool_name, arguments=arguments)
        result_text = result.content[0].text.casefold()

        assert "error running dnf" in result_text

    @pytest.mark.parametrize(
        ("tool_name", "arguments"),
        [
            ("dnf_provides", {"query": "/usr/bin/python3", "host": "remote.example.com"}),
            ("get_dnf_repo_info", {"repo_id": "baseos", "host": "remote.example.com"}),
            ("get_dnf_group_info", {"group": "Development Tools", "host": "remote.example.com"}),
            ("list_dnf_modules", {"module": "nodejs", "host": "remote.example.com"}),
            ("dnf_module_provides", {"package": "python3", "host": "remote.example.com"}),
        ],
    )
    async def test_dnf_new_tools_empty_output(self, mcp_client, mock_execute_with_fallback, tool_name, arguments):
        mock_execute_with_fallback.return_value = (0, "   ", "")

        result = await mcp_client.call_tool(tool_name, arguments=arguments)
        result_text = result.content[0].text.casefold()

        assert "no output returned" in result_text
