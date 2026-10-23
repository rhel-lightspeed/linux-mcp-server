"""Tests that Ruff stops a tool module registering straight onto the FastMCP instance.

Redaction lives in the ``@tool`` decorator, so a tool registered with ``mcp.tool``
would return output nothing had scanned. These run Ruff itself rather than searching
for the text ``@mcp.tool``, so aliases and indirect references are covered too.
"""

import subprocess
import sys

import pytest


RULE = "TID251"

TOOL_MODULE = "src/linux_mcp_server/tools/example.py"

BODY = """

@{decorator}
async def probe() -> str:
    return "output"
"""


def check(source: str, filename: str = TOOL_MODULE) -> str:
    """Run Ruff over `source` as though it were saved at `filename`.

    Using the real path means the project's own configuration applies, including the
    per-file exemptions, without writing anything into the tree.
    """
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--no-cache", "--stdin-filename", filename, "-"],
        input=source,
        capture_output=True,
        text=True,
    )
    return result.stdout


@pytest.mark.parametrize(
    ("source", "description"),
    [
        pytest.param(
            "from linux_mcp_server.server import mcp" + BODY.format(decorator='mcp.tool(tags={"fixed"})'),
            "direct registration",
            id="direct",
        ),
        pytest.param(
            "from linux_mcp_server.server import mcp as m" + BODY.format(decorator='m.tool(tags={"fixed"})'),
            "symbol imported under another name",
            id="aliased-symbol",
        ),
        pytest.param(
            "import linux_mcp_server.server" + BODY.format(decorator="linux_mcp_server.server.mcp.tool()"),
            "reached through the module path",
            id="module-path",
        ),
        pytest.param(
            "import linux_mcp_server.server as srv" + BODY.format(decorator="srv.mcp.tool()"),
            "module imported under another name",
            id="aliased-module",
        ),
        pytest.param(
            "from linux_mcp_server import server" + BODY.format(decorator="server.mcp.tool()"),
            "module imported from the package",
            id="from-package",
        ),
        pytest.param(
            "from linux_mcp_server.server import mcp\n\nregister = mcp.tool"
            + BODY.format(decorator='register(tags={"x"})'),
            "method stashed in a local name",
            id="indirect-reference",
        ),
    ],
)
def test_bypassing_the_decorator_is_rejected(source: str, description: str) -> None:
    assert RULE in check(source), f"Ruff allowed {description}"


def test_the_project_decorator_is_accepted() -> None:
    source = "from linux_mcp_server.server import tool" + BODY.format(decorator='tool(tags={"fixed"})')

    assert RULE not in check(source)


def test_importing_the_server_module_for_other_reasons_is_accepted() -> None:
    """Only the FastMCP instance is banned, not everything the module exports."""
    source = "from linux_mcp_server.server import tool\nfrom linux_mcp_server.server import REDACTION_FAILURE_MESSAGE\n"

    assert RULE not in check(source)


@pytest.mark.parametrize(
    "filename",
    [
        pytest.param("src/linux_mcp_server/server.py", id="server-module"),
        pytest.param("tests/test_server.py", id="test-suite"),
        pytest.param("tests/conftest.py", id="conftest"),
        pytest.param("scripts/generate_tool_docs.py", id="doc-generation"),
    ],
)
def test_places_that_legitimately_use_the_instance_still_work(filename: str) -> None:
    """These drive an already-built server rather than registering tools on it."""
    source = "from linux_mcp_server.server import mcp\n\nvalue = mcp\n"

    assert RULE not in check(source, filename=filename)


def test_the_real_tool_modules_pass() -> None:
    """The shipped tools must satisfy the rule they exist to protect."""
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--no-cache", "--select", RULE, "src/linux_mcp_server/tools"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout
