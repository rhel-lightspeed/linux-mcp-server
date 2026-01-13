"""Tests for system information tools."""

import sys

from contextlib import nullcontext

import pytest

from fastmcp.exceptions import ToolError


@pytest.fixture
def mock_execute(mock_execute_with_fallback_for):
    return mock_execute_with_fallback_for("linux_mcp_server.commands")


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux commands")
@pytest.mark.parametrize(
    "tool, expected",
    (
        (
            "get_system_information",
            (
                ("hostname",),
                ("kernel",),
                ("operating system", "os"),
                ("uptime",),
            ),
        ),
        (
            "get_cpu_information",
            (
                ("cpu", "processor"),
                ("load", "usage"),
            ),
        ),
        (
            "get_memory_information",
            (
                ("memory", "ram"),
                ("total",),
                ("used", "available"),
            ),
        ),
        (
            "get_disk_usage",
            (
                ("filesystem", "device", "mounted"),
                ("/",),
            ),
        ),
        (
            "get_hardware_information",
            [("hardware information", "cpu architecture")],
        ),
    ),
)
async def test_system_info_tools(tool, expected, mcp_client):
    result = await mcp_client.call_tool(tool)
    result_text = result.content[0].text.casefold()

    assert all(any(n in result_text for n in case) for case in expected), "Did not find all expected values"


@pytest.mark.parametrize(
    "tool, return_value, side_effect, expected, assertion",
    (
        (
            "get_memory_information",
            (0, "", ""),
            None,
            pytest.raises(ToolError, match="Unable to retrieve"),
            "result_text == ''",
        ),
        (
            "get_disk_usage",
            (0, "", ""),
            None,
            pytest.raises(ToolError, match="Unable to retrieve"),
            "result_text == ''",
        ),
        ("get_system_information", (0, "", ""), None, nullcontext(), "result_text == ''"),
        ("get_cpu_information", (0, "", ""), None, nullcontext(), "result_text == ''"),
        (
            "get_hardware_information",
            (1, "", ""),
            None,
            nullcontext(),
            "'no hardware information tools available' in result_text",
        ),
        (
            "get_hardware_information",
            (1, "", ""),
            FileNotFoundError,
            nullcontext(),
            "'command not available' in result_text",
        ),
    ),
)
async def test_system_info_tools_unsuccessful(
    tool, return_value, side_effect, expected, assertion, mcp_client, mock_execute
):
    mock_execute.return_value = return_value
    mock_execute.side_effect = side_effect

    # These tools now raise ToolError when output is unsuccessful
    # The MCP client's raise_on_error=True (default) causes it to raise an exception
    with pytest.raises(Exception) as exc_info:
        await mcp_client.call_tool(tool)

    # Verify the error message contains expected text
    assert "error" in str(exc_info.value).casefold()


@pytest.mark.parametrize(
    "tool",
    (
        "get_system_information",
        "get_cpu_information",
    ),
)
async def test_system_info_tools_unsuccessful_empty(tool, mcp_client, mock_execute):
    mock_execute.return_value = (0, "", "")

    result = await mcp_client.call_tool(tool)

    # These tools now return structured output (JSON), so check for structured content
    # When commands return empty output, the parsers return objects with default/empty values
    assert result.structured_content is not None


async def test_get_hardware_information_success(mcp_client, mock_execute):
    """Test get_hardware_information with successful command execution."""
    # Mock successful command outputs
    lscpu_output = """Architecture:        x86_64
CPU op-mode(s):      32-bit, 64-bit
Model name:          Intel(R) Core(TM) i7-8565U CPU @ 1.80GHz"""

    lspci_output = """00:00.0 Host bridge: Intel Corporation
00:02.0 VGA compatible controller: Intel Corporation
00:14.0 USB controller: Intel Corporation"""

    lsusb_output = """Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
Bus 002 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub"""

    # Mock execute to return different output based on command
    def mock_execute_side_effect(*args, **_kwargs):
        cmd = args[0]
        match cmd[0]:  # pragma: no branch
            case "lscpu":
                return (0, lscpu_output, "")
            case "lspci":
                return (0, lspci_output, "")
            case "lsusb":
                return (0, lsusb_output, "")
            case _:
                raise AssertionError(f"Unexpected command in test mock: {cmd[0]}")

    mock_execute.side_effect = mock_execute_side_effect

    result = await mcp_client.call_tool("get_hardware_information")

    # Verify structured content exists
    assert result.structured_content is not None
    content = result.structured_content

    # Check that all expected keys are present (lscpu, lspci, lsusb)
    assert "lscpu" in content
    assert "lspci" in content
    assert "lsusb" in content

    # lscpu should be a string
    assert isinstance(content["lscpu"], str)
    assert "Intel(R) Core(TM) i7-8565U" in content["lscpu"]

    # lspci and lsusb should be lists
    assert isinstance(content["lspci"], list)
    assert isinstance(content["lsusb"], list)

    # Check list contents
    assert any("Host bridge" in line for line in content["lspci"])
    assert any("Linux Foundation" in line for line in content["lsusb"])


async def test_get_hardware_information_command_not_found(mcp_client, mock_execute):
    """Test get_hardware_information when a command is not available."""
    lscpu_output = "Architecture:        x86_64"

    # Mock execute to simulate FileNotFoundError for some commands
    def mock_execute_side_effect(*args, **_kwargs):
        cmd = args[0]
        match cmd[0]:  # pragma: no branch
            case "lscpu":
                return (0, lscpu_output, "")
            case "lspci":
                raise FileNotFoundError("lspci not found")
            case "lsusb":
                raise FileNotFoundError("lsusb not found")
            case _:
                raise AssertionError(f"Unexpected command in test mock: {cmd[0]}")

    mock_execute.side_effect = mock_execute_side_effect

    result = await mcp_client.call_tool("get_hardware_information")

    assert result.structured_content is not None
    content = result.structured_content

    # lscpu should have output
    assert "Architecture" in content["lscpu"]

    # lspci and lsusb should have "command not available" messages
    assert "lspci command not available" in content["lspci"]
    assert "lsusb command not available" in content["lsusb"]


async def test_get_hardware_information_command_failure(mcp_client, mock_execute):
    """Test get_hardware_information when a command fails."""
    mock_execute.return_value = (1, "", "Permission denied")

    # The tool raises ToolError when a command fails
    with pytest.raises(Exception) as exc_info:
        await mcp_client.call_tool("get_hardware_information")

    assert "error" in str(exc_info.value).casefold()


async def test_get_hardware_information_remote_execution(mcp_client, mock_execute):
    """Test get_hardware_information with remote host parameter."""
    mock_execute.return_value = (0, "Remote hardware output", "")

    result = await mcp_client.call_tool("get_hardware_information", {"host": "remote.host.com"})

    assert result.structured_content is not None

    # Verify execute was called with host parameter
    mock_execute.assert_called()
    call_kwargs = mock_execute.call_args[1]
    assert call_kwargs["host"] == "remote.host.com"
