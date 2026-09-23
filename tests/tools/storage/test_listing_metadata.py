"""Regression coverage for listing metadata and the MCP output contract."""

import json
import os
import sys

from datetime import datetime
from pathlib import Path

import pytest

from fastmcp.client import Client
from jsonschema import Draft202012Validator
from mcp.types import TextContent
from pytest_mock import MockerFixture


@pytest.mark.parametrize("tool_name", ["list_files", "list_directories"])
@pytest.mark.parametrize(
    ("order_by", "stdout", "expected"),
    [
        ("name", "alpha\n", {"name": "alpha"}),
        ("size", "0\t/remote/alpha\n0\t/remote\n", {"name": "alpha", "size": 0}),
        ("modified", "0.0:+0000\talpha\n", {"name": "alpha", "modified": "1970-01-01T00:00:00Z"}),
        (
            "modified",
            "1700000000.75:+0545\talpha\n",
            {"name": "alpha", "modified": "2023-11-15T03:58:21+05:45"},
        ),
    ],
)
async def test_listing_metadata(
    tool_name: str,
    order_by: str,
    stdout: str,
    expected: dict[str, object],
    mcp_client: Client,
    mocker: MockerFixture,
) -> None:
    if order_by == "size" and tool_name == "list_files":
        stdout = "0\talpha\n"
    execute = mocker.patch(
        "linux_mcp_server.commands.execute_with_fallback", autospec=True, return_value=(0, stdout, "")
    )
    result = await mcp_client.call_tool(tool_name, {"host": "remote.host", "path": "/remote", "order_by": order_by})
    expected_content = {"nodes": [expected], "total": 1}
    assert result.structured_content is not None
    assert result.structured_content == expected_content
    assert isinstance(result.content[0], TextContent)
    assert json.loads(result.content[0].text) == expected_content
    tool = next(tool for tool in await mcp_client.list_tools() if tool.name == tool_name)
    assert tool.outputSchema is not None
    Draft202012Validator(tool.outputSchema).validate(result.structured_content)
    assert execute.call_args.kwargs["host"] == "remote.host"
    if order_by == "modified":
        modified = result.structured_content["nodes"][0]["modified"]
        timestamp = datetime.fromisoformat(modified.replace("Z", "+00:00"))
        assert timestamp.utcoffset() is not None
        assert timestamp.microsecond == 0
        assert execute.call_args.args[0][-1] == "%T@:%Tz\\t%f\\n"


@pytest.mark.parametrize("tool_name", ["list_files", "list_directories"])
@pytest.mark.parametrize("sort", ["ascending", "descending"])
async def test_listing_chronological_order(
    tool_name: str,
    sort: str,
    mcp_client: Client,
    mocker: MockerFixture,
) -> None:
    # The clock goes backward at the DST transition. The latest two timestamps
    # round to the same second but must still sort by their original instants.
    stdout = "1699164000.4:-0500\tlatest\n1699163999.6:-0400\tmiddle\n1699163999.1:-0400\tearliest\n"
    mocker.patch("linux_mcp_server.commands.execute_with_fallback", autospec=True, return_value=(0, stdout, ""))
    result = await mcp_client.call_tool(
        tool_name, {"host": "remote.host", "path": "/remote", "order_by": "modified", "sort": sort, "top_n": 2}
    )
    assert result.structured_content is not None
    expected = ["earliest", "middle"] if sort == "ascending" else ["latest", "middle"]
    assert [node["name"] for node in result.structured_content["nodes"]] == expected
    assert result.structured_content["total"] == 2


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU find")
@pytest.mark.parametrize("tool_name", ["list_files", "list_directories"])
async def test_listing_target_timezone(
    tool_name: str,
    mcp_client: Client,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Only the child command reads TZ; no tzset() changes the server's timezone.
    monkeypatch.setenv("TZ", "Asia/Kathmandu")
    node = tmp_path / "alpha"
    if tool_name == "list_files":
        node.touch()
    else:
        node.mkdir()
    os.utime(node, (1700000000.75, 1700000000.75))
    result = await mcp_client.call_tool(tool_name, {"host": "localhost", "path": str(tmp_path), "order_by": "modified"})
    assert result.structured_content is not None
    modified = result.structured_content["nodes"][0]["modified"]
    assert modified == "2023-11-15T03:58:21+05:45"
    assert datetime.fromisoformat(modified).timestamp() == 1700000001
