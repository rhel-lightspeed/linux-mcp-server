"""Tests for LINUX_MCP_HOST_MODE - restricting where tools may run."""

import sys

from pathlib import Path

import pytest

from fastmcp.exceptions import ToolError

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import Config
from linux_mcp_server.config import CONTAINER_ENV_VARS
from linux_mcp_server.config import default_host_mode
from linux_mcp_server.config import HostMode
from linux_mcp_server.config import Toolset
from linux_mcp_server.execution_context import ExecutionContext
from linux_mcp_server.server import mcp
from linux_mcp_server.target_host import adjust_tool
from linux_mcp_server.target_host import check_host_mode
from linux_mcp_server.target_host import restrict
from linux_mcp_server.utils.types import LOCALHOST


REMOTE = "web1.example.com"

FREE_OUTPUT = """\
               total        used        free      shared  buff/cache   available
Mem:        32490308    14925036     2497076     2138132    15082720    17565272
Swap:        8388604     3555312     4833292
"""


@pytest.fixture
def host_mode(mocker):
    """Set the configured host mode for the duration of a test."""

    def set_mode(mode: HostMode):
        mocker.patch.object(CONFIG, "host_mode", mode)

    return set_mode


class TestDefault:
    """Local execution is offered only where it would tell the user anything useful."""

    @pytest.fixture(autouse=True)
    def not_a_container(self, monkeypatch):
        monkeypatch.delenv("container", raising=False)
        monkeypatch.setattr(sys, "platform", "linux")

    def test_linux_outside_a_container(self):
        assert default_host_mode() == HostMode.ANY

    @pytest.mark.parametrize("container", CONTAINER_ENV_VARS)
    def test_container(self, monkeypatch, container):
        monkeypatch.setenv("container", container)
        assert default_host_mode() == HostMode.REMOTE_ONLY

    def test_empty_container_variable_is_not_a_container(self, monkeypatch):
        monkeypatch.setenv("container", "")
        assert default_host_mode() == HostMode.ANY

    @pytest.mark.parametrize("platform", ["darwin", "win32"])
    def test_other_platforms_cannot_run_locally(self, monkeypatch, platform):
        monkeypatch.setattr(sys, "platform", platform)
        assert default_host_mode() == HostMode.REMOTE_ONLY

    def test_env_var_overrides_the_default(self, monkeypatch):
        monkeypatch.setenv("LINUX_MCP_HOST_MODE", "remote-only")
        assert Config().host_mode == HostMode.REMOTE_ONLY


class TestCheckHostMode:
    @pytest.mark.parametrize(
        ("mode", "host"),
        [
            (HostMode.ANY, LOCALHOST),
            (HostMode.ANY, REMOTE),
            (HostMode.LOCAL_ONLY, LOCALHOST),
            (HostMode.REMOTE_ONLY, REMOTE),
        ],
    )
    def test_allowed(self, host_mode, mode, host):
        host_mode(mode)
        check_host_mode(host)

    def test_local_only_refuses_a_remote_host(self, host_mode):
        host_mode(HostMode.LOCAL_ONLY)
        with pytest.raises(ToolError, match=f"cannot connect to '{REMOTE}'"):
            check_host_mode(REMOTE)

    def test_remote_only_refuses_localhost(self, host_mode):
        host_mode(HostMode.REMOTE_ONLY)
        with pytest.raises(ToolError, match="only run tools on remote systems"):
            check_host_mode(LOCALHOST)


class TestRestrict:
    """The mode holds even if something reaches execution without being checked."""

    FULL = ExecutionContext(allow_local=True, allow_ssh_default=True, ssh_key_path=Path("/key"), ssh_key_user="user")

    def test_any_keeps_everything(self, host_mode):
        host_mode(HostMode.ANY)
        assert restrict(self.FULL) == self.FULL

    def test_local_only_takes_away_ssh(self, host_mode):
        host_mode(HostMode.LOCAL_ONLY)
        assert restrict(self.FULL) == ExecutionContext(allow_local=True)

    def test_remote_only_takes_away_local(self, host_mode):
        host_mode(HostMode.REMOTE_ONLY)
        assert restrict(self.FULL) == self.FULL.model_copy(update={"allow_local": False})


class TestToolSchema:
    """What the model is shown for 'host'."""

    async def parameters(self, tool_name: str = "get_memory_information") -> dict:
        tool = await mcp.get_tool(tool_name)
        assert tool
        return adjust_tool(tool).parameters

    async def description(self, tool_name: str = "get_memory_information") -> str:
        return (await self.parameters(tool_name))["properties"]["host"]["description"]

    async def test_any_describes_both(self, host_mode):
        host_mode(HostMode.ANY)
        assert "or a remote host to connect to via SSH" in await self.description()

    async def test_remote_only_describes_ssh(self, host_mode):
        host_mode(HostMode.REMOTE_ONLY)
        assert "cannot run anything on the system it runs on" in await self.description()

    async def test_local_only_drops_the_parameter(self, host_mode):
        """There is only one possible value, so don't make the model recite it."""
        host_mode(HostMode.LOCAL_ONLY)
        parameters = await self.parameters("get_process_info")

        assert "host" not in parameters["properties"]
        # The tool's other parameters are untouched.
        assert parameters["required"] == ["pid"]

    async def test_local_only_leaves_no_empty_required_list(self, host_mode):
        """A tool whose only parameter was 'host' now takes no arguments at all."""
        host_mode(HostMode.LOCAL_ONLY)
        parameters = await self.parameters()

        assert parameters["properties"] == {}
        assert "required" not in parameters

    async def test_a_tool_without_a_host_parameter_is_left_alone(self, host_mode):
        host_mode(HostMode.REMOTE_ONLY)
        tool = await mcp.get_tool("run_script")
        assert tool
        assert adjust_tool(tool) is tool

    async def test_the_registered_tool_is_not_modified(self, host_mode):
        host_mode(HostMode.LOCAL_ONLY)
        await self.parameters()

        host_mode(HostMode.ANY)
        assert "or a remote host to connect to via SSH" in await self.description()

    async def test_listed_tools_show_the_mode(self, host_mode, mcp_client):
        host_mode(HostMode.LOCAL_ONLY)
        tools = {tool.name: tool for tool in await mcp_client.list_tools()}

        assert "host" not in tools["get_memory_information"].inputSchema["properties"]


class TestInstructions:
    @pytest.mark.parametrize("toolset", [Toolset.FIXED, Toolset.RUN_SCRIPT, Toolset.BOTH])
    @pytest.mark.parametrize(
        ("mode", "expected"),
        [
            (HostMode.ANY, "`localhost` runs the work on the system the MCP server runs on"),
            (HostMode.LOCAL_ONLY, "take no `host` argument"),
            (HostMode.REMOTE_ONLY, "`localhost` is not available"),
        ],
    )
    async def test_instructions_describe_the_mode(self, host_mode, setup_client, toolset, mode, expected):
        host_mode(mode)
        client = await setup_client(toolset=toolset, auto_initialize=False)
        result = await client.initialize()

        assert expected in result.instructions
        assert "{target_host}" not in result.instructions


class TestCallTool:
    @pytest.fixture(autouse=True)
    def mock_command(self, mocker):
        command = mocker.Mock()
        command.run = mocker.AsyncMock(return_value=(0, FREE_OUTPUT, ""))
        mocker.patch("linux_mcp_server.tools.system_info.get_command", return_value=command)
        return command

    async def test_local_only_refuses_a_remote_host(self, host_mode, mcp_client):
        host_mode(HostMode.LOCAL_ONLY)
        with pytest.raises(ToolError, match=f"cannot connect to '{REMOTE}'"):
            await mcp_client.call_tool("get_memory_information", {"host": REMOTE})

    async def test_remote_only_refuses_localhost(self, host_mode, mcp_client):
        host_mode(HostMode.REMOTE_ONLY)
        with pytest.raises(ToolError, match="only run tools on remote systems"):
            await mcp_client.call_tool("get_memory_information", {"host": LOCALHOST})

    async def test_an_in_mode_host_still_runs(self, host_mode, mcp_client, mock_command):
        host_mode(HostMode.ANY)
        await mcp_client.call_tool("get_memory_information", {"host": LOCALHOST})

        mock_command.run.assert_awaited_once_with(host=LOCALHOST)

    async def test_local_only_fills_in_the_host(self, host_mode, mcp_client, mock_command):
        """The parameter isn't in the schema, but the tool still needs a value."""
        host_mode(HostMode.LOCAL_ONLY)
        await mcp_client.call_tool("get_memory_information")

        mock_command.run.assert_awaited_once_with(host=LOCALHOST)

    async def test_local_only_still_accepts_an_explicit_localhost(self, host_mode, mcp_client, mock_command):
        """A client working from an older schema keeps working."""
        host_mode(HostMode.LOCAL_ONLY)
        await mcp_client.call_tool("get_memory_information", {"host": LOCALHOST})

        mock_command.run.assert_awaited_once_with(host=LOCALHOST)

    async def test_remote_only_still_requires_a_host(self, host_mode, mcp_client):
        """Only local-only can fill the host in, so the advice has to differ."""
        host_mode(HostMode.REMOTE_ONLY)
        with pytest.raises(ToolError, match="must name the remote system to run on"):
            await mcp_client.call_tool("get_memory_information")

    async def test_local_only_rejects_a_host_that_is_not_a_name(self, host_mode, mcp_client):
        host_mode(HostMode.LOCAL_ONLY)
        with pytest.raises(ToolError, match="can be left out entirely"):
            await mcp_client.call_tool("get_memory_information", {"host": 42})
