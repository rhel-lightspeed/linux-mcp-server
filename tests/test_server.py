"""tests for the server module, including middleware"""

import logging

from typing import Any
from typing import Literal
from typing import Protocol

import pytest

from fastmcp import Client
from fastmcp.client import FastMCPTransport
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken
from mcp.types import Implementation

from linux_mcp_server.auth_policy import AuthPolicy
from linux_mcp_server.auth_policy import PolicyAction
from linux_mcp_server.auth_policy import PolicyRule
from linux_mcp_server.auth_policy import SSHKeyConfig
from linux_mcp_server.config import Toolset


FIXED_TOOLS = set(
    [
        "get_cpu_information",
        "get_disk_usage",
        "get_hardware_information",
        "get_journal_logs",
        "get_listening_ports",
        "get_memory_information",
        "get_network_connections",
        "get_network_interfaces",
        "get_network_routes",
        "get_process_info",
        "get_service_logs",
        "get_service_status",
        "get_system_information",
        "list_block_devices",
        "list_directories",
        "list_files",
        "list_processes",
        "list_services",
        "read_file",
        "read_log_file",
    ]
)

RUN_SCRIPT_TOOLS = set(["run_script", "run_script_with_confirmation", "validate_script"])
RUN_SCRIPT_APP_TOOLS = set(
    [
        "execute_script",
        "get_execution_details",
        "reject_script",
        "run_script_interactive",
        "run_script",
        "validate_script",
    ]
)


@pytest.mark.parametrize(
    "toolset,mcp_apps,expected",
    [
        (Toolset.FIXED, False, FIXED_TOOLS),
        (Toolset.FIXED, True, FIXED_TOOLS),
        (Toolset.RUN_SCRIPT, False, RUN_SCRIPT_TOOLS),
        (Toolset.RUN_SCRIPT, True, RUN_SCRIPT_APP_TOOLS),
        (Toolset.BOTH, False, FIXED_TOOLS | RUN_SCRIPT_TOOLS),
        (Toolset.BOTH, True, FIXED_TOOLS | RUN_SCRIPT_APP_TOOLS),
    ],
)
async def test_list_tools(toolset: Toolset, mcp_apps: bool, expected: set[str], setup_client):
    client = await setup_client(toolset=toolset, mcp_apps=mcp_apps)
    tools = await client.list_tools()
    tool_names = set(tool.name for tool in tools)
    assert tool_names == expected


async def test_list_tools_with_use_mcp_apps_override(setup_client, mocker):
    """Test that LINUX_MCP_USE_MCP_APPS turns off detected mcp-apps"""
    mocker.patch("linux_mcp_server.server.CONFIG.use_mcp_apps", False)
    client = await setup_client(toolset=Toolset.RUN_SCRIPT, mcp_apps=True)
    tools = await client.list_tools()
    tool_names = set(tool.name for tool in tools)
    assert tool_names == RUN_SCRIPT_TOOLS


@pytest.mark.parametrize("version,list_app_only_tools", [("1.23.1", False), ("1.29", True), ("2beta", True)])
async def test_list_tools_with_old_goose(setup_client, version: str, list_app_only_tools: bool):
    """Test that visibility=["app"] tools are hidden from old versions of Goose"""
    client_info = Implementation(name="goose-deskktop", version=version)
    client = await setup_client(toolset=Toolset.RUN_SCRIPT, mcp_apps=True, client_info=client_info)
    tools = await client.list_tools()
    tool_names = set(tool.name for tool in tools)
    if list_app_only_tools:
        assert tool_names == RUN_SCRIPT_APP_TOOLS
    else:
        assert tool_names == {"run_script_interactive", "run_script", "validate_script"}


@pytest.mark.parametrize(
    "toolset,mcp_apps,expected",
    [
        (Toolset.FIXED, True, set()),
        (Toolset.RUN_SCRIPT, False, set()),
        (Toolset.RUN_SCRIPT, True, {"ui://run_script_readonly_with_mcp_app/run-script-app.html"}),
    ],
)
async def test_list_resources(toolset: Toolset, mcp_apps: bool, expected: set[str], setup_client):
    client: Client = await setup_client(toolset=toolset, mcp_apps=mcp_apps)
    resources = await client.list_resources()
    tool_names = set(str(resource.uri) for resource in resources)
    assert tool_names == expected


@pytest.mark.parametrize(
    "toolset,mcp_apps,expected_substrings",
    [
        (Toolset.FIXED, False, ["You have access to predefined commands"]),
        (
            Toolset.RUN_SCRIPT,
            False,
            [
                "You have access to tools that validate and execute",
                "**run_script_with_confirmation:** Run a validated script",
            ],
        ),
        (
            Toolset.RUN_SCRIPT,
            True,
            [
                "You have access to tools that validate and execute",
                "**run_script_interactive:** Run a validated script",
            ],
        ),
        (
            Toolset.BOTH,
            False,
            [
                "You have access to two kinds of tools",
                "**run_script_with_confirmation:** Run a validated script",
            ],
        ),
        (
            Toolset.BOTH,
            True,
            ["You have access to two kinds of tools", "**run_script_interactive:** Run a validated script"],
        ),
    ],
)
async def test_instructions(toolset: Toolset, mcp_apps: bool, expected_substrings: list[str], setup_client):
    client = await setup_client(toolset=toolset, mcp_apps=mcp_apps, auto_initialize=False)
    result = await client.initialize()
    for substring in expected_substrings:
        assert substring in result.instructions


async def test_read_mcp_app_resource(mcp_client):
    """Test that we can read the mcp-app resource"""
    result = await mcp_client.read_resource("ui://run_script_readonly_with_mcp_app/run-script-app.html")

    assert len(result) == 1
    assert "<title>Run Script</title>" in result[0].text


FREE_OUTPUT = """\
               total        used        free      shared  buff/cache   available
Mem:        32490308    14925036     2497076     2138132    15082720    17565272
Swap:        8388604     3555312     4833292
"""


class TestAuthorizationMiddleware:
    @pytest.fixture(autouse=True)
    def setup(self, mocker, mcp_client: Client[FastMCPTransport]):
        """A callable fixture to encapsulate the mocks we need for these tests"""

        # Mock out a single tool to use in the tests
        mock_command = mocker.Mock()
        mock_command.run = mocker.AsyncMock(return_value=(0, FREE_OUTPUT, ""))
        mocker.patch("linux_mcp_server.tools.system_info.get_command", return_value=mock_command)

        def setup_fn(
            transport: Literal["stdio", "http"] = "stdio",
            policy: AuthPolicy | None = None,
            claims: dict[str, Any] | None = None,
        ):
            mocker.patch("linux_mcp_server.server.CONFIG.transport", transport)

            if policy:
                policy_path = "/etc/linux-mcp-server/auth_policy.json"
            else:
                policy_path = None
                policy = AuthPolicy(rules=[])
            mocker.patch("linux_mcp_server.server.CONFIG.policy_path", policy_path)
            mocker.patch("linux_mcp_server.auth_policy.get_policy", return_value=policy)

            if claims is not None:
                access_token = mocker.Mock(spec=AccessToken)
                access_token.claims = claims
                mocker.patch("linux_mcp_server.server.get_access_token", return_value=access_token)

            return mcp_client

        yield setup_fn

    # pyright struggles to infer the type of the fixture, so add an explicit type
    class SetupFn(Protocol):
        def __call__(
            self,
            transport: Literal["stdio", "http"] = "stdio",
            policy: AuthPolicy | None = None,
            claims: dict[str, Any] | None = None,
        ) -> Client[FastMCPTransport]: ...

    async def test_unknown_tool_raises(self, setup: SetupFn):
        client = setup(transport="stdio")
        with pytest.raises(ToolError, match=r"Unknown tool: 'not_a_tool'"):
            await client.call_tool("not_a_tool")

    async def test_disabled_tool_raises(self, setup: SetupFn):
        client = setup(transport="stdio")
        with pytest.raises(ToolError, match=r"Unknown tool: 'validate_script'"):
            await client.call_tool("validate_script")

    async def test_stdio_no_policy_allows(self, setup: SetupFn):
        client = setup(transport="stdio")
        result = await client.call_tool("get_memory_information")
        assert result.structured_content and result.structured_content["ram"]["free"] == 2497076

    async def test_http_no_policy_rejects(self, setup: SetupFn):
        client = setup(transport="http")
        with pytest.raises(ToolError, match=r"Authorization denied: tool 'get_memory_information'"):
            await client.call_tool("get_memory_information")

    async def test_http_policy_all_users_allows(self, setup: SetupFn):
        client = setup(
            transport="http",
            policy=AuthPolicy(
                rules=[PolicyRule(host="localhost", tools=["@fixed"], all_users=True, action=PolicyAction.LOCAL)]
            ),
        )

        result = await client.call_tool("get_memory_information")
        assert result.structured_content and result.structured_content["ram"]["free"] == 2497076

    @pytest.mark.parametrize("email,allowed", [("user1@example.com", True), ("user2@example.com", False)])
    async def test_http_policy_one_user(self, email: str, allowed: bool, setup: SetupFn):
        client = setup(
            transport="http",
            policy=AuthPolicy(
                rules=[
                    PolicyRule(
                        host="localhost",
                        tools=["@fixed"],
                        claims={"email": "user1@example.com"},
                        action=PolicyAction.LOCAL,
                    )
                ]
            ),
            claims={"email": email},
        )

        if allowed:
            result = await client.call_tool("get_memory_information")
            assert result.structured_content and result.structured_content["ram"]["free"] == 2497076
        else:
            with pytest.raises(ToolError, match=r"Authorization denied: tool 'get_memory_information'"):
                await client.call_tool("get_memory_information")

    async def test_ssh_key_with_config_allows(self, setup: SetupFn, caplog):
        """SSH_KEY action with config, should allow and log"""
        caplog.set_level(logging.DEBUG)

        client = setup(
            transport="http",
            policy=AuthPolicy(
                rules=[
                    PolicyRule(
                        host="server1.example.com",
                        tools=["@fixed"],
                        all_users=True,
                        action=PolicyAction.SSH_KEY,
                        ssh_key=SSHKeyConfig(path="/keys/server1.key", user="serviceaccount"),
                    )
                ]
            ),
        )

        result = await client.call_tool("get_memory_information", {"host": "server1.example.com"})
        assert result.structured_content and result.structured_content["ram"]["free"] == 2497076

        assert "SSH key override: path=/keys/server1.key, user=serviceaccount" in caplog.text

    # Various scenarios for bad returns from evaluate_policy that should be prevented
    # by policy validation. We mock the evaluate_policy() return directly

    async def test_local_action_with_host_raises(self, setup: SetupFn, mocker):
        """LOCAL action but host is specified"""
        client = setup(transport="http")

        mocker.patch(
            "linux_mcp_server.server.evaluate_policy",
            return_value=(PolicyAction.LOCAL, None),
        )

        with pytest.raises(
            ToolError, match=r"Policy validation error: Cannot use local action for remote host 'server1.example.com'"
        ):
            await client.call_tool("get_memory_information", {"host": "server1.example.com"})

    async def test_ssh_default_with_no_host_raises(self, setup: SetupFn, mocker):
        """SSH_DEFAULT action but no host in arguments"""
        client = setup(transport="http")

        mocker.patch(
            "linux_mcp_server.server.evaluate_policy",
            return_value=(PolicyAction.SSH_DEFAULT, None),
        )

        with pytest.raises(
            ToolError, match=r"Policy validation error: Cannot use SSH action \('ssh_default'\) for local execution."
        ):
            await client.call_tool("get_memory_information")

    async def test_ssh_key_with_no_config_raises(self, setup: SetupFn, mocker):
        """SSH_KEY action but no ssk_key configuration"""
        client = setup(transport="http")

        mocker.patch(
            "linux_mcp_server.server.evaluate_policy",
            return_value=(PolicyAction.SSH_KEY, None),
        )

        with pytest.raises(ToolError, match=r"Policy validation error: SSH_KEY action requires ssh_key configuration."):
            await client.call_tool("get_memory_information", {"host": "server1.example.com"})


class CaptureContext:
    def __init__(self):
        self._context = None

    async def _execute_with_fallback(self, *_args, **_kwargs):
        from linux_mcp_server.execution_context import get_execution_context

        self._context = get_execution_context()
        return (0, FREE_OUTPUT, "")

    def get_context(self):
        return self._context


class TestExecutionContextMiddlewareIntegration:
    @pytest.fixture
    def capture_context(self, mocker):
        capture = CaptureContext()
        mocker.patch("linux_mcp_server.commands.execute_with_fallback", side_effect=capture._execute_with_fallback)
        return capture

    async def test_stdio_without_policy_allows_all(self, mcp_client, mocker, capture_context):
        """Verify stdio without policy sets ExecutionContext with allow_local=True, allow_ssh_default=True."""
        mocker.patch("linux_mcp_server.server.CONFIG.transport", "stdio")
        mocker.patch("linux_mcp_server.server.CONFIG.policy_path", None)

        await mcp_client.call_tool("get_memory_information")

        captured_context = capture_context.get_context()
        assert captured_context is not None
        assert captured_context.allow_local is True
        assert captured_context.allow_ssh_default is True

    async def test_local_policy_sets_local_context(self, mcp_client, mocker, capture_context):
        """Verify LOCAL policy action sets ExecutionContext with allow_local=True only."""
        mocker.patch("linux_mcp_server.server.CONFIG.transport", "streamable-http")
        mocker.patch("linux_mcp_server.server.CONFIG.policy_path", "/etc/policy.json")
        mocker.patch(
            "linux_mcp_server.auth_policy.get_policy",
            return_value=AuthPolicy(
                rules=[PolicyRule(host="localhost", tools=["@fixed"], all_users=True, action=PolicyAction.LOCAL)]
            ),
        )

        await mcp_client.call_tool("get_memory_information")

        captured_context = capture_context.get_context()
        assert captured_context is not None
        assert captured_context.allow_local is True
        assert captured_context.allow_ssh_default is False
        assert captured_context.ssh_key_path is None

    async def test_ssh_default_policy_sets_ssh_context(self, mcp_client, mocker, capture_context):
        """Verify SSH_DEFAULT policy action sets ExecutionContext with allow_ssh_default=True."""
        mocker.patch("linux_mcp_server.server.CONFIG.transport", "streamable-http")
        mocker.patch("linux_mcp_server.server.CONFIG.policy_path", "/etc/policy.json")
        mocker.patch(
            "linux_mcp_server.auth_policy.get_policy",
            return_value=AuthPolicy(
                rules=[
                    PolicyRule(
                        host="server1.example.com",
                        tools=["@fixed"],
                        all_users=True,
                        action=PolicyAction.SSH_DEFAULT,
                    )
                ]
            ),
        )

        await mcp_client.call_tool("get_memory_information", {"host": "server1.example.com"})

        captured_context = capture_context.get_context()
        assert captured_context is not None
        assert captured_context.allow_local is False
        assert captured_context.allow_ssh_default is True
        assert captured_context.ssh_key_path is None

    async def test_ssh_key_policy_sets_key_context(self, mcp_client, mocker, capture_context):
        """Verify SSH_KEY policy action sets ExecutionContext with ssh_key_path and ssh_key_user."""
        from pathlib import Path

        mocker.patch("linux_mcp_server.server.CONFIG.transport", "streamable-http")
        mocker.patch("linux_mcp_server.server.CONFIG.policy_path", "/etc/policy.json")
        mocker.patch(
            "linux_mcp_server.auth_policy.get_policy",
            return_value=AuthPolicy(
                rules=[
                    PolicyRule(
                        host="server1.example.com",
                        tools=["@fixed"],
                        all_users=True,
                        action=PolicyAction.SSH_KEY,
                        ssh_key=SSHKeyConfig(path="/keys/server1.key", user="serviceaccount"),
                    )
                ]
            ),
        )

        await mcp_client.call_tool("get_memory_information", {"host": "server1.example.com"})

        captured_context = capture_context.get_context()
        assert captured_context is not None
        assert captured_context.allow_local is False
        assert captured_context.allow_ssh_default is False
        assert captured_context.ssh_key_path == Path("/keys/server1.key")
        assert captured_context.ssh_key_user == "serviceaccount"
