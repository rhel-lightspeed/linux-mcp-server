"""Tests for system information tools."""

import sys

from contextlib import nullcontext

import pytest

from fastmcp import exceptions


@pytest.fixture
def mock_execute(mock_execute_with_fallback_for):
    return mock_execute_with_fallback_for("linux_mcp_server.commands")


def create_mock_execute_side_effect(command_responses: dict[str, str | Exception]):
    """Create a mock execute side effect function based on command responses.

    command_responses: dict of command_name -> output_string or Exception
    """

    def mock_execute_side_effect(*args, **_kwargs):
        cmd = args[0]
        match cmd[0]:
            case cmd_name if cmd_name in command_responses:
                response = command_responses[cmd_name]
                if isinstance(response, Exception):
                    raise response
                else:
                    return (0, response, "")
            case _:
                raise AssertionError(f"Unexpected command in test mock: {cmd[0]}")

    return mock_execute_side_effect


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
    "tool, error_message",
    [
        ("get_memory_information", "Unable to retrieve memory information"),
        ("get_disk_usage", "Unable to retrieve disk usage information"),
    ],
)
async def test_system_info_tools_unsuccessful(tool, error_message, mcp_client, mock_execute):
    mock_execute.return_value = (0, "", "")

    # These tools now raise ToolError when output is unsuccessful
    # The MCP client's raise_on_error=True (default) causes it to raise an exception
    with pytest.raises(exceptions.ToolError, match=error_message):
        await mcp_client.call_tool(tool)


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


@pytest.mark.parametrize(
    "tool, failing_command",
    [
        ("get_system_information", "hostname"),
        ("get_cpu_information", "model"),
    ],
)
async def test_system_info_tools_exception(tool, failing_command, mcp_client, mock_execute):
    command_responses: dict[str, str | Exception] = {failing_command: Exception("Command failed")}
    mock_execute.side_effect = create_mock_execute_side_effect(command_responses)

    with pytest.raises(Exception) as exc_info:
        await mcp_client.call_tool(tool)

    assert "error" in str(exc_info.value).casefold()


async def test_get_memory_information_parse_error(mcp_client, mock_execute):
    """Test get_memory_information with malformed output that causes parsing to fail."""
    # Return output that will cause int() to fail in parse_free_output
    malformed_output = "Mem: invalid total used free"
    mock_execute.return_value = (0, malformed_output, "")

    with pytest.raises(exceptions.ToolError, match="Error gathering memory information"):
        await mcp_client.call_tool("get_memory_information")


async def test_get_disk_usage_parse_error(mcp_client, mock_execute):
    """Test get_disk_usage with unexpected exception during execution."""
    # Mock cmd.run to raise an unexpected exception
    mock_execute.side_effect = ValueError("Raised intentionally")

    with pytest.raises(exceptions.ToolError, match="Error gathering disk usage information"):
        await mcp_client.call_tool("get_disk_usage")


async def test_get_hardware_information_unexpected_exception(mcp_client, mock_execute):
    """Test get_hardware_information with unexpected exception from command execution."""
    # Mock cmd.run to raise an unexpected exception (not FileNotFoundError)
    mock_execute.side_effect = RuntimeError("Unexpected error")

    with pytest.raises(exceptions.ToolError, match="Error gathering hardware information"):
        await mcp_client.call_tool("get_hardware_information")


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

    command_responses: dict[str, str | Exception] = {
        "lscpu": lscpu_output,
        "lspci": lspci_output,
        "lsusb": lsusb_output,
    }

    mock_execute.side_effect = create_mock_execute_side_effect(command_responses)

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

    command_responses = {
        "lscpu": lscpu_output,
        "lspci": FileNotFoundError("lspci not found"),
        "lsusb": FileNotFoundError("lsusb not found"),
    }

    mock_execute.side_effect = create_mock_execute_side_effect(command_responses)

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

    result = await mcp_client.call_tool("get_hardware_information")

    assert result.structured_content is not None
    content = result.structured_content

    # Check that error messages are included for failed commands
    for cmd_name in ["lscpu", "lspci", "lsusb"]:
        assert cmd_name in content
        assert "Error retrieving" in content[cmd_name]


async def test_get_hardware_information_remote_execution(mcp_client, mock_execute):
    """Test get_hardware_information with remote host parameter."""
    mock_execute.return_value = (0, "Remote hardware output", "")

    result = await mcp_client.call_tool("get_hardware_information", {"host": "remote.host.com"})

    assert result.structured_content is not None

    # Verify execute was called with host parameter
    mock_execute.assert_called()
    call_kwargs = mock_execute.call_args[1]
    assert call_kwargs["host"] == "remote.host.com"


def test_mock_execute_unexpected_command():
    """Test that the mock execute raises AssertionError for unexpected commands."""
    lscpu_output = "Architecture: x86_64"
    lspci_output = "00:00.0 Host bridge"
    lsusb_output = "Bus 001 Device 001"

    command_responses: dict[str, str | Exception] = {
        "lscpu": lscpu_output,
        "lspci": lspci_output,
        "lsusb": lsusb_output,
    }

    mock_execute_side_effect = create_mock_execute_side_effect(command_responses)

    # This should raise AssertionError, covering the default case
    with pytest.raises(AssertionError, match="Unexpected command in test mock: unexpected"):
        mock_execute_side_effect(["unexpected"])
