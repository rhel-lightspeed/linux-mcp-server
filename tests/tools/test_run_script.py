"""Unit tests for ``run_script`` MCP tools and helpers.

Tests call underlying implementations via ``.fn`` because ``@mcp.tool`` wraps
handlers in ``FunctionTool``; SSH and gatekeeper are mocked.
"""

import shlex

from typing import Any

import pytest

from fastmcp import Context
from fastmcp.exceptions import ToolError

from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.gatekeeper import GatekeeperResult
from linux_mcp_server.gatekeeper import GatekeeperStatus
from linux_mcp_server.tools import run_script as run_script_mod
from linux_mcp_server.tools.run_script import _wrap_script
from linux_mcp_server.tools.run_script import BASH_STRICT_PREAMBLE
from linux_mcp_server.tools.run_script import SCRIPT_TYPE_BASH
from linux_mcp_server.tools.run_script import SCRIPT_TYPE_PYTHON
from linux_mcp_server.tools.run_script import ScriptDetails
from linux_mcp_server.tools.run_script import ScriptStore


# Underlying callables (@mcp.tool wraps them in FunctionTool)
execute_script = run_script_mod.execute_script.fn
get_execution_state = run_script_mod.get_execution_state.fn
reject_script = run_script_mod.reject_script.fn
run_script = run_script_mod.run_script.fn
run_script_modify = run_script_mod.run_script_modify.fn
run_script_modify_interactive = run_script_mod.run_script_modify_interactive.fn
run_script_readonly = run_script_mod.run_script_readonly.fn
validate_script = run_script_mod.validate_script.fn


@pytest.fixture
def mock_ctx(mocker) -> Any:
    """Unused ``Context`` placeholder required by tool signatures."""
    return mocker.Mock(spec=Context)


@pytest.fixture
def script_store_fresh(monkeypatch: pytest.MonkeyPatch) -> ScriptStore:
    """Isolate ``script_store`` so tests do not share global script IDs."""
    store = ScriptStore()
    monkeypatch.setattr(run_script_mod, "script_store", store)
    return store


@pytest.fixture
def patch_execute_command(mocker) -> Any:
    """Mock ``execute_command`` in the run_script module (async SSH/local runner)."""
    return mocker.patch(
        "linux_mcp_server.tools.run_script.execute_command",
        new=mocker.AsyncMock(spec=execute_command),
    )


@pytest.fixture
def patch_check_run_script(mocker) -> Any:
    """Mock the LLM gatekeeper so tests do not call litellm."""
    return mocker.patch("linux_mcp_server.tools.run_script.check_run_script", autospec=True)


def _ok() -> GatekeeperResult:
    """Gatekeeper result used when policy allows the script."""
    return GatekeeperResult(status=GatekeeperStatus.OK, detail="")


class TestScriptStore:
    """``ScriptStore`` holds pending script metadata for the MCP app approval flow."""

    def test_add_get_and_state(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Adding a script stores metadata, returns an ID, and state can be updated."""
        monkeypatch.setattr("linux_mcp_server.tools.run_script.secrets.token_urlsafe", lambda _n: "fixed-token-id")
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


class TestRunScriptReadonly:
    """``run_script_readonly``: gatekeeper OK, then run wrapped command and return stdout."""

    async def test_success_string_stdout(
        self,
        mock_ctx: Any,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """On success with str stdout, return the stdout text unchanged."""
        patch_check_run_script.return_value = _ok()
        patch_execute_command.return_value = (0, "output", "")
        out = await run_script_readonly(mock_ctx, "d", SCRIPT_TYPE_PYTHON, "print(1)", None)
        assert out == "output"
        patch_execute_command.assert_awaited_once()

    async def test_success_bytes_stdout(
        self,
        mock_ctx: Any,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Bytes stdout from SSH is decoded as UTF-8 for the tool return value."""
        patch_check_run_script.return_value = _ok()
        patch_execute_command.return_value = (0, b"byte-out", "")
        out = await run_script_readonly(mock_ctx, "d", SCRIPT_TYPE_PYTHON, "print(1)", None)
        assert out == "byte-out"

    async def test_nonzero_return(
        self,
        mock_ctx: Any,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Non-zero exit surfaces as an error string including code and stderr."""
        patch_check_run_script.return_value = _ok()
        patch_execute_command.return_value = (1, "", "err")
        out = await run_script_readonly(mock_ctx, "d", SCRIPT_TYPE_PYTHON, "print(1)", None)
        assert "return code 1" in out
        assert "err" in out

    async def test_gatekeeper_tool_error(
        self,
        mock_ctx: Any,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Gatekeeper rejection raises ``ToolError`` and never runs the command."""
        patch_check_run_script.return_value = GatekeeperResult(
            status=GatekeeperStatus.POLICY,
            detail="nope",
        )
        with pytest.raises(ToolError, match="Policy violation"):
            await run_script_readonly(mock_ctx, "d", SCRIPT_TYPE_PYTHON, "print(1)", None)
        patch_execute_command.assert_not_awaited()

    async def test_gatekeeper_modifies_system_runtime_error(
        self,
        mock_ctx: Any,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """``MODIFIES_SYSTEM`` on a read-only tool is treated as an internal error."""
        patch_check_run_script.return_value = GatekeeperResult(
            status=GatekeeperStatus.MODIFIES_SYSTEM,
            detail="x",
        )
        with pytest.raises(RuntimeError, match="MODIFIES_SYSTEM"):
            await run_script_readonly(mock_ctx, "d", SCRIPT_TYPE_PYTHON, "print(1)", None)
        patch_execute_command.assert_not_awaited()

    async def test_bash_passes_strict_script_to_gatekeeper(
        self,
        mock_ctx: Any,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Bash scripts are checked with the same strict preamble the runner will use."""
        patch_check_run_script.return_value = _ok()
        patch_execute_command.return_value = (0, "ok", "")
        await run_script_readonly(mock_ctx, "d", SCRIPT_TYPE_BASH, "true", None)
        patch_check_run_script.assert_called_once()
        (desc, st, script), kwargs = patch_check_run_script.call_args
        assert desc == "d"
        assert st == SCRIPT_TYPE_BASH
        assert kwargs == {"readonly": True}
        assert script.startswith(BASH_STRICT_PREAMBLE)


class TestRunScriptModify:
    """``run_script_modify``: destructive path that runs immediately after gatekeeper OK."""

    async def test_success(
        self,
        mock_ctx: Any,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Return stdout when the wrapped command exits zero."""
        patch_check_run_script.return_value = _ok()
        patch_execute_command.return_value = (0, "done", "")
        out = await run_script_modify(mock_ctx, "d", SCRIPT_TYPE_PYTHON, "print(1)", None)
        assert out == "done"

    async def test_gatekeeper_blocks(
        self,
        mock_ctx: Any,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Non-OK gatekeeper status becomes ``ToolError``; command is not run."""
        patch_check_run_script.return_value = GatekeeperResult(status=GatekeeperStatus.UNCLEAR, detail="bad")
        with pytest.raises(ToolError, match="Unclear"):
            await run_script_modify(mock_ctx, "d", SCRIPT_TYPE_PYTHON, "print(1)", None)
        patch_execute_command.assert_not_awaited()

    async def test_nonzero_return(
        self,
        mock_ctx: Any,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Non-zero exit returns a formatted error string (same shape as read-only)."""
        patch_check_run_script.return_value = _ok()
        patch_execute_command.return_value = (3, "", "stderr-here")
        out = await run_script_modify(mock_ctx, "d", SCRIPT_TYPE_PYTHON, "print(1)", None)
        assert "return code 3" in out
        assert "stderr-here" in out


class TestRunScriptModifyInteractive:
    """``run_script_modify_interactive``: app-facing proposal; stores script for later execution."""

    async def test_ok_adds_script_and_returns_tool_result(
        self,
        mock_ctx: Any,
        script_store_fresh: ScriptStore,
        patch_check_run_script: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When gatekeeper approves, persist script under a new ID and return structured metadata."""
        monkeypatch.setattr("linux_mcp_server.tools.run_script.secrets.token_urlsafe", lambda _n: "id-a")
        patch_check_run_script.return_value = _ok()
        result = await run_script_modify_interactive(mock_ctx, "d", SCRIPT_TYPE_PYTHON, "print(1)", None)
        assert result.structured_content["id"] == "id-a"
        assert result.structured_content["status"] == GatekeeperStatus.OK.value
        assert script_store_fresh.get_script_details("id-a").state == "waiting-approval"
        assert result.content is not None

    async def test_rejected_sets_state(
        self,
        mock_ctx: Any,
        script_store_fresh: ScriptStore,
        patch_check_run_script: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rejected scripts are still recorded so the UI can show ``rejected-gatekeeper``."""
        monkeypatch.setattr("linux_mcp_server.tools.run_script.secrets.token_urlsafe", lambda _n: "id-b")
        patch_check_run_script.return_value = GatekeeperResult(status=GatekeeperStatus.DANGEROUS, detail="no")
        result = await run_script_modify_interactive(mock_ctx, "d", SCRIPT_TYPE_PYTHON, "print(1)", None)
        assert result.structured_content["status"] == GatekeeperStatus.DANGEROUS.value
        assert script_store_fresh.get_script_details("id-b").state == "rejected-gatekeeper"


class TestExecuteScript:
    """``execute_script``: MCP app runs a previously stored script by ID."""

    async def test_success(
        self,
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
        tr = await execute_script("tok")
        assert tr.structured_content == {"state": "success", "output": "out"}
        assert script_store_fresh.get_script_details("tok").state == "success"

    async def test_failure_return_code(
        self,
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
        tr = await execute_script("tok2")
        assert tr.structured_content["state"] == "failure"
        assert "return code 2" in tr.structured_content["output"]

    async def test_execute_exception_sets_failure(
        self,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
    ) -> None:
        """Exceptions from ``execute_command`` propagate after state is set to failure."""
        script_store_fresh._scripts["tok3"] = ScriptDetails(
            state="waiting-approval",
            description="d",
            script="print(1)",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=False,
        )
        patch_execute_command.side_effect = OSError("boom")
        with pytest.raises(OSError, match="boom"):
            await execute_script("tok3")
        assert script_store_fresh.get_script_details("tok3").state == "failure"


class TestRejectAndGetExecutionState:
    """Thin tools used by the MCP app to reject or poll script state."""

    async def test_reject_script(
        self,
        script_store_fresh: ScriptStore,
    ) -> None:
        """``reject_script`` only moves the stored entry to ``rejected-user``."""
        script_store_fresh._scripts["r"] = ScriptDetails(
            state="waiting-approval",
            description="d",
            script="x",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=True,
        )
        await reject_script("r")
        assert script_store_fresh.get_script_details("r").state == "rejected-user"

    async def test_get_execution_state(self, script_store_fresh: ScriptStore) -> None:
        """Expose the current lifecycle state string for UI polling."""
        script_store_fresh._scripts["g"] = ScriptDetails(
            state="executing",
            description="d",
            script="x",
            script_type=SCRIPT_TYPE_BASH,
            host="host",
            readonly=True,
        )
        assert await get_execution_state("g") == {"state": "executing"}


class TestValidateScript:
    """``validate_script``: gatekeeper + store token for a later ``run_script`` call."""

    async def test_ok(
        self,
        mock_ctx: Any,
        script_store_fresh: ScriptStore,
        patch_check_run_script: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Approval stores the script as waiting and echoes the ID in the tool response."""
        monkeypatch.setattr("linux_mcp_server.tools.run_script.secrets.token_urlsafe", lambda _n: "val-id")
        patch_check_run_script.return_value = _ok()
        tr = await validate_script(mock_ctx, "d", SCRIPT_TYPE_PYTHON, "print(1)", None, True)
        assert "val-id" in tr.content[0].text
        assert tr.structured_content["id"] == "val-id"
        assert script_store_fresh.get_script_details("val-id").state == "waiting-approval"

    async def test_gatekeeper_fail_raises_and_marks_rejected(
        self,
        mock_ctx: Any,
        script_store_fresh: ScriptStore,
        patch_check_run_script: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Failure raises ``ToolError`` and marks the stored entry rejected for observability."""
        monkeypatch.setattr("linux_mcp_server.tools.run_script.secrets.token_urlsafe", lambda _n: "val-id-2")
        patch_check_run_script.return_value = GatekeeperResult(status=GatekeeperStatus.POLICY, detail="bad")
        with pytest.raises(ToolError, match="Policy violation"):
            await validate_script(mock_ctx, "d", SCRIPT_TYPE_PYTHON, "print(1)", None, True)
        assert script_store_fresh.get_script_details("val-id-2").state == "rejected-gatekeeper"


class TestRunScriptWithToken:
    """``run_script`` (token): run validated script; may re-check gatekeeper if args drift."""

    async def test_matching_details_skips_revalidation(
        self,
        mock_ctx: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Identical description/script/host/readonly skips a second gatekeeper call."""
        script_store_fresh._scripts["t1"] = ScriptDetails(
            state="waiting-approval",
            description="same",
            script="print(3)",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=True,
        )
        patch_execute_command.return_value = (0, "ran", "")
        out = await run_script(
            mock_ctx,
            "same",
            SCRIPT_TYPE_PYTHON,
            "print(3)",
            None,
            True,
            "t1",
        )
        assert out == "ran"
        patch_check_run_script.assert_not_called()
        assert script_store_fresh.get_script_details("t1").state == "success"

    async def test_mismatch_revalidates_and_executes(
        self,
        mock_ctx: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Changed script body triggers gatekeeper again; on OK the new script runs."""
        script_store_fresh._scripts["t2"] = ScriptDetails(
            state="waiting-approval",
            description="same",
            script="print(3)",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=True,
        )
        patch_check_run_script.return_value = _ok()
        patch_execute_command.return_value = (0, "out", "")
        out = await run_script(
            mock_ctx,
            "same",
            SCRIPT_TYPE_PYTHON,
            "print(99)",
            None,
            True,
            "t2",
        )
        assert out == "out"
        patch_check_run_script.assert_called_once()

    async def test_mismatch_gatekeeper_fails(
        self,
        mock_ctx: Any,
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
            readonly=True,
        )
        patch_check_run_script.return_value = GatekeeperResult(status=GatekeeperStatus.MALICIOUS, detail="x")
        with pytest.raises(ToolError):
            await run_script(
                mock_ctx,
                "same",
                SCRIPT_TYPE_PYTHON,
                "print(99)",
                None,
                True,
                "t3",
            )
        assert script_store_fresh.get_script_details("t3").state == "rejected-gatekeeper"
        patch_execute_command.assert_not_awaited()

    async def test_execute_failure_nonzero(
        self,
        mock_ctx: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Non-zero exit returns an error string and records ``failure`` state."""
        script_store_fresh._scripts["t4"] = ScriptDetails(
            state="waiting-approval",
            description="same",
            script="print(1)",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=True,
        )
        patch_execute_command.return_value = (1, "", "e")
        out = await run_script(mock_ctx, "same", SCRIPT_TYPE_PYTHON, "print(1)", None, True, "t4")
        assert "return code 1" in out
        assert script_store_fresh.get_script_details("t4").state == "failure"

    async def test_execute_exception(
        self,
        mock_ctx: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Exceptions bubble up after marking the script as failed."""
        script_store_fresh._scripts["t5"] = ScriptDetails(
            state="waiting-approval",
            description="same",
            script="print(1)",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=True,
        )
        patch_execute_command.side_effect = ValueError("nope")
        with pytest.raises(ValueError, match="nope"):
            await run_script(mock_ctx, "same", SCRIPT_TYPE_PYTHON, "print(1)", None, True, "t5")
        assert script_store_fresh.get_script_details("t5").state == "failure"

    async def test_bytes_stdout(
        self,
        mock_ctx: Any,
        script_store_fresh: ScriptStore,
        patch_execute_command: Any,
        patch_check_run_script: Any,
    ) -> None:
        """Invalid UTF-8 in stdout is decoded with replacement, matching production behavior."""
        script_store_fresh._scripts["t6"] = ScriptDetails(
            state="waiting-approval",
            description="same",
            script="print(1)",
            script_type=SCRIPT_TYPE_PYTHON,
            host=None,
            readonly=True,
        )
        raw = b"\xff\xfe"
        patch_execute_command.return_value = (0, raw, "")
        out = await run_script(mock_ctx, "same", SCRIPT_TYPE_PYTHON, "print(1)", None, True, "t6")
        assert out == raw.decode("utf-8", errors="replace")
