"""Integration-style tests for ``run_script`` MCP tools via ``mcp_client``.

Patches apply to ``linux_mcp_server.tools.run_script`` (the module object). The in-process
server is built with ``LINUX_MCP_TOOLSET=both`` (see ``tests/conftest.py``).
"""

import shlex

from importlib import import_module
from types import SimpleNamespace
from typing import Any

import pytest

from fastmcp.exceptions import ToolError

from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.gatekeeper import GatekeeperResult
from linux_mcp_server.gatekeeper import GatekeeperStatus
from linux_mcp_server.tools.run_script import _wrap_script
from linux_mcp_server.tools.run_script import BASH_STRICT_PREAMBLE
from linux_mcp_server.tools.run_script import SCRIPT_TYPE_BASH
from linux_mcp_server.tools.run_script import SCRIPT_TYPE_PYTHON
from linux_mcp_server.tools.run_script import ScriptDetails
from linux_mcp_server.tools.run_script import ScriptStore


run_script_mod = import_module("linux_mcp_server.tools.run_script")


def _tool_text(result: Any) -> str:
    """``run_script`` family tools return the string body in ``structured_content['result']``."""
    return str(result.structured_content["result"])


@pytest.fixture
def script_store_fresh(monkeypatch: pytest.MonkeyPatch) -> ScriptStore:
    """Isolate ``script_store`` so tests do not share global script IDs."""
    store = ScriptStore()
    monkeypatch.setattr(run_script_mod, "script_store", store)
    return store


@pytest.fixture
def patch_execute_command(mocker) -> Any:
    """Mock ``execute_command`` in the run_script module (async SSH/local runner)."""
    return mocker.patch.object(
        run_script_mod,
        "execute_command",
        new=mocker.AsyncMock(spec=execute_command),
    )


@pytest.fixture
def patch_check_run_script(mocker) -> Any:
    """Mock the LLM gatekeeper so tests do not call litellm."""
    return mocker.patch.object(run_script_mod, "check_run_script", autospec=True)


def _stub_secrets_token(monkeypatch: pytest.MonkeyPatch, token: str) -> None:
    """Patch ``secrets.token_urlsafe`` as seen by ``run_script`` (package name ``run_script`` is also a tool)."""
    monkeypatch.setattr(run_script_mod, "secrets", SimpleNamespace(token_urlsafe=lambda _n: token))


def _ok() -> GatekeeperResult:
    """Gatekeeper result used when policy allows the script."""
    return GatekeeperResult(status=GatekeeperStatus.OK, detail="")


class TestScriptStore:
    """``ScriptStore`` holds pending script metadata for the MCP app approval flow."""

    def test_add_get_and_state(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Adding a script stores metadata, returns an ID, and state can be updated."""
        _stub_secrets_token(monkeypatch, "fixed-token-id")
        store = ScriptStore()
        sid = store.add_script("desc", "print(1)", SCRIPT_TYPE_PYTHON, None, True)
        assert sid == "fixed-token-id"
        d = store.get_script_details(sid)
        assert d.state == "waiting-approval"
        assert d.description == "desc"
        assert d.script == "print(1)"
        assert d.script_type == SCRIPT_TYPE_PYTHON
        assert d.readonly is True
        store.set_script_state(sid, "executing")
        assert store.get_script_details(sid).state == "executing"

    def test_get_missing_raises(self) -> None:
        """Unknown IDs raise ``KeyError`` from ``get_script_details``."""
        store = ScriptStore()
        with pytest.raises(KeyError):
            store.get_script_details("nope")

    def test_set_state_missing_raises(self) -> None:
        """Unknown IDs raise ``KeyError`` from ``set_script_state``."""
        store = ScriptStore()
        with pytest.raises(KeyError):
            store.set_script_state("nope", "success")


class TestWrapScript:
    """``_wrap_script`` builds a ``bash -c`` wrapper that may use systemd-run when present."""

    def test_python_wraps_script_in_bash_c(self) -> None:
        """Python scripts are embedded in the wrapper with shell-safe quoting."""
        cmd = _wrap_script(SCRIPT_TYPE_PYTHON, "print('hi')")
        assert cmd[0] == "bash"
        assert cmd[1] == "-c"
        assert "python -c" in cmd[2]
        assert shlex.quote("print('hi')") in cmd[2]

    def test_bash_includes_strict_preamble_in_quoted_payload(self) -> None:
        """Bash snippets include the strict-mode preamble inside the quoted payload."""
        cmd = _wrap_script(SCRIPT_TYPE_BASH, "true")
        inner = cmd[2]
        assert BASH_STRICT_PREAMBLE in inner
        assert "true" in inner


class TestValidateScriptMCP:
    """``validate_script`` through ``mcp_client.call_tool``."""

    async def test_ok(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_check_run_script: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Approval stores the script; structured content has ``token`` and ``needs_confirmation``."""
        _stub_secrets_token(monkeypatch, "val-id")
        patch_check_run_script.return_value = _ok()
        result = await mcp_client.call_tool(
            "validate_script",
            {
                "description": "d",
                "script_type": SCRIPT_TYPE_PYTHON,
                "script": "print(1)",
                "readonly": True,
            },
        )
        assert "val-id" in result.content[0].text
        assert result.structured_content["token"] == "val-id"
        assert (
            result.structured_content["needs_confirmation"]
            == script_store_fresh.get_script_details("val-id").needs_confirmation
        )
        assert script_store_fresh.get_script_details("val-id").state == "waiting-approval"

    async def test_gatekeeper_fail_raises_and_marks_rejected(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_check_run_script: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Failure raises ``ToolError`` and marks the stored entry rejected."""
        _stub_secrets_token(monkeypatch, "val-id-2")
        patch_check_run_script.return_value = GatekeeperResult(status=GatekeeperStatus.POLICY, detail="bad")
        with pytest.raises(ToolError, match="Policy violation"):
            await mcp_client.call_tool(
                "validate_script",
                {
                    "description": "d",
                    "script_type": SCRIPT_TYPE_PYTHON,
                    "script": "print(1)",
                    "readonly": True,
                },
            )
        assert script_store_fresh.get_script_details("val-id-2").state == "rejected-gatekeeper"

    async def test_bash_passes_strict_script_to_gatekeeper(
        self,
        mcp_client: Any,
        patch_check_run_script: Any,
        patch_execute_command: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Bash scripts are checked with the same strict preamble the runner will use."""
        _stub_secrets_token(monkeypatch, "bash-val")
        patch_check_run_script.return_value = _ok()
        await mcp_client.call_tool(
            "validate_script",
            {
                "description": "d",
                "script_type": SCRIPT_TYPE_BASH,
                "script": "true",
                "readonly": True,
            },
        )
        patch_check_run_script.assert_called_once()
        (desc, st, script), kwargs = patch_check_run_script.call_args
        assert desc == "d"
        assert st == SCRIPT_TYPE_BASH
        assert kwargs == {"readonly": True}
        assert script.startswith(BASH_STRICT_PREAMBLE)
        patch_execute_command.assert_not_awaited()


class TestRunScriptMCP:
    """``run_script`` (token only) via ``mcp_client``."""

    async def test_success_string_stdout(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
    ) -> None:
        """On success with str stdout, return the stdout text unchanged."""
        script_store_fresh._scripts["tok"] = ScriptDetails(
            state="waiting-approval",
            description="d",
            script="print(1)",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=True,
        )
        patch_execute_command.return_value = (0, "output", "")
        result = await mcp_client.call_tool("run_script", {"token": "tok"})
        assert _tool_text(result) == "output"
        patch_execute_command.assert_awaited_once()
        assert script_store_fresh.get_script_details("tok").state == "success"

    async def test_success_bytes_stdout(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
    ) -> None:
        """Bytes stdout from SSH is decoded as UTF-8 for the tool return value."""
        script_store_fresh._scripts["tokb"] = ScriptDetails(
            state="waiting-approval",
            description="d",
            script="x",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=True,
        )
        patch_execute_command.return_value = (0, b"byte-out", "")
        result = await mcp_client.call_tool("run_script", {"token": "tokb"})
        assert _tool_text(result) == "byte-out"

    async def test_nonzero_return(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
    ) -> None:
        """Non-zero exit surfaces as an error string including code and stderr."""
        script_store_fresh._scripts["toknz"] = ScriptDetails(
            state="waiting-approval",
            description="d",
            script="x",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=True,
        )
        patch_execute_command.return_value = (1, "", "err")
        out = _tool_text(await mcp_client.call_tool("run_script", {"token": "toknz"}))
        assert "return code 1" in out
        assert "err" in out
        assert script_store_fresh.get_script_details("toknz").state == "failure"

    async def test_execute_exception_sets_failure(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
    ) -> None:
        """Exceptions from ``execute_command`` become ``ToolError`` after state is set to failure."""
        script_store_fresh._scripts["tokex"] = ScriptDetails(
            state="waiting-approval",
            description="d",
            script="x",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=True,
        )
        patch_execute_command.side_effect = ValueError("nope")
        with pytest.raises(ToolError, match="nope"):
            await mcp_client.call_tool("run_script", {"token": "tokex"})
        assert script_store_fresh.get_script_details("tokex").state == "failure"

    async def test_wrong_tool_when_confirmation_required(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
    ) -> None:
        """Scripts that need confirmation must use ``run_script_with_confirmation``."""
        script_store_fresh._scripts["mod"] = ScriptDetails(
            state="waiting-approval",
            description="d",
            script="rm -rf /",
            script_type=SCRIPT_TYPE_BASH,
            host=None,
            readonly=False,
        )
        with pytest.raises(ToolError, match="run_script_with_confirmation"):
            await mcp_client.call_tool("run_script", {"token": "mod"})
        patch_execute_command.assert_not_awaited()


class TestRunScriptWithConfirmationMCP:
    """``run_script_with_confirmation`` via ``mcp_client``."""

    async def test_success_matching_params(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Matching parameters skip a second gatekeeper call."""
        script_store_fresh._scripts["t1"] = ScriptDetails(
            state="waiting-approval",
            description="same",
            script="print(3)",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=False,
        )
        patch_execute_command.return_value = (0, "ran", "")
        out = _tool_text(
            await mcp_client.call_tool(
                "run_script_with_confirmation",
                {
                    "description": "same",
                    "script_type": SCRIPT_TYPE_PYTHON,
                    "script": "print(3)",
                    "readonly": False,
                    "token": "t1",
                },
            )
        )
        assert out == "ran"
        patch_check_run_script.assert_not_called()
        assert script_store_fresh.get_script_details("t1").state == "success"

    async def test_mismatch_revalidates_and_executes(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Changed script body triggers gatekeeper again; on OK the stored script runs."""
        script_store_fresh._scripts["t2"] = ScriptDetails(
            state="waiting-approval",
            description="same",
            script="print(3)",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=False,
        )
        patch_check_run_script.return_value = _ok()
        patch_execute_command.return_value = (0, "out", "")
        out = _tool_text(
            await mcp_client.call_tool(
                "run_script_with_confirmation",
                {
                    "description": "same",
                    "script_type": SCRIPT_TYPE_PYTHON,
                    "script": "print(99)",
                    "readonly": False,
                    "token": "t2",
                },
            )
        )
        assert out == "out"
        patch_check_run_script.assert_called_once()

    async def test_mismatch_gatekeeper_fails(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Revalidation failure raises ``ToolError`` and does not execute."""
        script_store_fresh._scripts["t3"] = ScriptDetails(
            state="waiting-approval",
            description="same",
            script="print(3)",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=False,
        )
        patch_check_run_script.return_value = GatekeeperResult(status=GatekeeperStatus.MALICIOUS, detail="x")
        with pytest.raises(ToolError):
            await mcp_client.call_tool(
                "run_script_with_confirmation",
                {
                    "description": "same",
                    "script_type": SCRIPT_TYPE_PYTHON,
                    "script": "print(99)",
                    "readonly": False,
                    "token": "t3",
                },
            )
        assert script_store_fresh.get_script_details("t3").state == "rejected-gatekeeper"
        patch_execute_command.assert_not_awaited()

    async def test_nonzero_return(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Non-zero exit returns a formatted error string."""
        script_store_fresh._scripts["t4"] = ScriptDetails(
            state="waiting-approval",
            description="same",
            script="print(1)",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=False,
        )
        patch_execute_command.return_value = (3, "", "stderr-here")
        out = _tool_text(
            await mcp_client.call_tool(
                "run_script_with_confirmation",
                {
                    "description": "same",
                    "script_type": SCRIPT_TYPE_PYTHON,
                    "script": "print(1)",
                    "readonly": False,
                    "token": "t4",
                },
            )
        )
        assert "return code 3" in out
        assert "stderr-here" in out

    async def test_wrong_tool_when_no_confirmation_needed(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Read-only scripts without forced confirmation should use ``run_script``."""
        script_store_fresh._scripts["ro"] = ScriptDetails(
            state="waiting-approval",
            description="d",
            script="true",
            script_type=SCRIPT_TYPE_BASH,
            host=None,
            readonly=True,
        )
        with pytest.raises(ToolError, match="run_script instead"):
            await mcp_client.call_tool(
                "run_script_with_confirmation",
                {
                    "description": "d",
                    "script_type": SCRIPT_TYPE_BASH,
                    "script": "true",
                    "readonly": True,
                    "token": "ro",
                },
            )
        patch_check_run_script.assert_not_called()
        patch_execute_command.assert_not_awaited()

    async def test_bytes_stdout(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Invalid UTF-8 in stdout is decoded with replacement."""
        script_store_fresh._scripts["t6"] = ScriptDetails(
            state="waiting-approval",
            description="same",
            script="print(1)",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=False,
        )
        raw = b"\xff\xfe"
        patch_execute_command.return_value = (0, raw, "")
        out = _tool_text(
            await mcp_client.call_tool(
                "run_script_with_confirmation",
                {
                    "description": "same",
                    "script_type": SCRIPT_TYPE_PYTHON,
                    "script": "print(1)",
                    "readonly": False,
                    "token": "t6",
                },
            )
        )
        assert out == raw.decode("utf-8", errors="replace")


class TestRunScriptInteractiveMCP:
    """``run_script_interactive`` via ``mcp_client``."""

    async def test_ok_matching_returns_same_token(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_check_run_script: Any,
    ) -> None:
        """When params match the stored script, return the same ID and OK structured content."""
        script_store_fresh._scripts["id-a"] = ScriptDetails(
            state="waiting-approval",
            description="d",
            script="print(1)",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=False,
        )
        result = await mcp_client.call_tool(
            "run_script_interactive",
            {
                "description": "d",
                "script_type": SCRIPT_TYPE_PYTHON,
                "script": "print(1)",
                "readonly": False,
                "token": "id-a",
            },
        )
        assert result.structured_content["id"] == "id-a"
        assert result.structured_content["status"] == GatekeeperStatus.OK.value
        assert result.content is not None

    async def test_mismatch_revalidates_new_id(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_check_run_script: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Drifted params run gatekeeper and register a new store entry as the result ID."""
        script_store_fresh._scripts["id-b"] = ScriptDetails(
            state="waiting-approval",
            description="d",
            script="print(1)",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=False,
        )
        patch_check_run_script.return_value = _ok()
        _stub_secrets_token(monkeypatch, "new-id")
        result = await mcp_client.call_tool(
            "run_script_interactive",
            {
                "description": "d",
                "script_type": SCRIPT_TYPE_PYTHON,
                "script": "print(2)",
                "readonly": False,
                "token": "id-b",
            },
        )
        assert result.structured_content["id"] == "new-id"
        patch_check_run_script.assert_called_once()
        assert script_store_fresh.get_script_details("new-id").state == "waiting-approval"

    async def test_mismatch_gatekeeper_fails(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_check_run_script: Any,
    ) -> None:
        """Failed revalidation marks the original token rejected."""
        script_store_fresh._scripts["id-c"] = ScriptDetails(
            state="waiting-approval",
            description="d",
            script="print(1)",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=False,
        )
        patch_check_run_script.return_value = GatekeeperResult(status=GatekeeperStatus.DANGEROUS, detail="no")
        with pytest.raises(ToolError, match="Dangerous"):
            await mcp_client.call_tool(
                "run_script_interactive",
                {
                    "description": "d",
                    "script_type": SCRIPT_TYPE_PYTHON,
                    "script": "print(9)",
                    "readonly": False,
                    "token": "id-c",
                },
            )
        assert script_store_fresh.get_script_details("id-c").state == "rejected-gatekeeper"

    async def test_wrong_tool_when_no_confirmation_needed(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_check_run_script: Any,
    ) -> None:
        """``run_script_interactive`` is only for scripts that require confirmation."""
        script_store_fresh._scripts["ro"] = ScriptDetails(
            state="waiting-approval",
            description="d",
            script="true",
            script_type=SCRIPT_TYPE_BASH,
            host=None,
            readonly=True,
        )
        with pytest.raises(ToolError, match="run_script instead"):
            await mcp_client.call_tool(
                "run_script_interactive",
                {
                    "description": "d",
                    "script_type": SCRIPT_TYPE_BASH,
                    "script": "true",
                    "readonly": True,
                    "token": "ro",
                },
            )
        patch_check_run_script.assert_not_called()


class TestExecuteScriptMCP:
    """``execute_script`` via ``mcp_client``."""

    async def test_success(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
    ) -> None:
        """Exit zero updates state to success and returns structured output for the app."""
        script_store_fresh._scripts["tok"] = ScriptDetails(
            state="waiting-approval",
            description="d",
            script="print(1)",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=False,
        )
        patch_execute_command.return_value = (0, "out", "")
        result = await mcp_client.call_tool("execute_script", {"id": "tok"})
        assert result.structured_content == {"state": "success", "output": "out"}
        assert script_store_fresh.get_script_details("tok").state == "success"

    async def test_failure_return_code(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
    ) -> None:
        """Non-zero exit marks failure and puts the error text in structured content."""
        script_store_fresh._scripts["tok2"] = ScriptDetails(
            state="waiting-approval",
            description="d",
            script="print(1)",
            script_type=SCRIPT_TYPE_PYTHON,
            host="h",
            readonly=False,
        )
        patch_execute_command.return_value = (2, "", "stderr-msg")
        result = await mcp_client.call_tool("execute_script", {"id": "tok2"})
        assert result.structured_content["state"] == "failure"
        assert "return code 2" in result.structured_content["output"]

    async def test_execute_exception_sets_failure(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
    ) -> None:
        """Command exceptions surface as ``ToolError`` after state is set to failure."""
        script_store_fresh._scripts["tok3"] = ScriptDetails(
            state="waiting-approval",
            description="d",
            script="print(1)",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=False,
        )
        patch_execute_command.side_effect = OSError("boom")
        with pytest.raises(ToolError, match="boom"):
            await mcp_client.call_tool("execute_script", {"id": "tok3"})
        assert script_store_fresh.get_script_details("tok3").state == "failure"


class TestRejectAndGetExecutionStateMCP:
    """``reject_script`` and ``get_execution_state`` via ``mcp_client``."""

    async def test_reject_script(
        self,
        mcp_client: Any,
        script_store_fresh: ScriptStore,
    ) -> None:
        """``reject_script`` moves the stored entry to ``rejected-user``."""
        script_store_fresh._scripts["r"] = ScriptDetails(
            state="waiting-approval",
            description="d",
            script="x",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=True,
        )
        await mcp_client.call_tool("reject_script", {"id": "r"})
        assert script_store_fresh.get_script_details("r").state == "rejected-user"

    async def test_get_execution_state(self, mcp_client: Any, script_store_fresh: ScriptStore) -> None:
        """Expose the current lifecycle state string for UI polling."""
        script_store_fresh._scripts["g"] = ScriptDetails(
            state="executing",
            description="d",
            script="x",
            script_type=SCRIPT_TYPE_BASH,
            host="host",
            readonly=True,
        )
        result = await mcp_client.call_tool("get_execution_state", {"id": "g"})
        assert result.structured_content == {"state": "executing"}
