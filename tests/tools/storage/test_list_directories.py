import os
import sys

import pytest

from fastmcp.exceptions import ToolError

from linux_mcp_server.tools.storage import OrderBy


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
async def test_list_directories(setup_test_paths, mcp_client, tmp_path):
    dir_specs = [
        ("alpha", 100, 1000.0),
        ("beta", 200, 2000.0),
        ("gamma", 300, 3000.0),
    ]
    expected_names = setup_test_paths(dir_specs)

    result = await mcp_client.call_tool("list_directories", arguments={"path": str(tmp_path), "order_by": "name"})
    content = result.structured_content
    names = [dir["name"] for dir in content["nodes"]]
    positions = {dir["name"]: id for id, dir in enumerate(content["nodes"])}

    assert names == expected_names, "Did not find all expected names"

    alpha_pos = positions["alpha"]
    beta_pos = positions["beta"]
    gamma_pos = positions["gamma"]
    assert alpha_pos < beta_pos < gamma_pos


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
async def test_list_directories_by_size(setup_test_paths, mcp_client, tmp_path):
    dir_specs = [
        ("small", 100, 1000.0),
        ("large", 300, 3000.0),
        ("medium", 200, 2000.0),
    ]
    setup_test_paths(dir_specs)

    result = await mcp_client.call_tool("list_directories", arguments={"path": str(tmp_path), "order_by": "size"})
    content = result.structured_content
    names = [dir["name"] for dir in content["nodes"]]

    assert content["total"] == len(dir_specs)
    assert names == ["small", "medium", "large"]


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
@pytest.mark.parametrize(
    ("dir_specs", "order_by", "expected_order"),
    [
        pytest.param(
            [("alpha", 100, 1000.0), ("beta", 200, 2000.0), ("gamma", 300, 3000.0)],
            OrderBy.NAME,
            ["gamma", "beta", "alpha"],
            id="name_descending",
        ),
        pytest.param(
            [("small", 100, 1000.0), ("medium", 200, 2000.0), ("large", 300, 3000.0)],
            OrderBy.SIZE,
            ["large", "medium", "small"],
            id="size_descending",
        ),
        pytest.param(
            [("oldest", 100, 1000.0), ("middle", 200, 2000.0), ("newest", 300, 3000.0)],
            OrderBy.MODIFIED,
            ["newest", "middle", "oldest"],
            id="modified_descending",
        ),
    ],
)
async def test_list_directories_descending(setup_test_paths, dir_specs, order_by, expected_order, mcp_client, tmp_path):
    setup_test_paths(dir_specs)

    result = await mcp_client.call_tool(
        "list_directories", arguments={"path": str(tmp_path), "order_by": order_by, "sort": "descending"}
    )
    content = result.structured_content
    names = [dir["name"] for dir in content["nodes"]]
    positions = {dir["name"]: id for id, dir in enumerate(content["nodes"])}

    assert names == expected_order
    assert positions[expected_order[0]] < positions[expected_order[1]] < positions[expected_order[2]]


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
@pytest.mark.parametrize("order", ("size", "modified", "name"))
async def test_list_directories_with_top_n(setup_test_paths, mcp_client, order, tmp_path):
    dir_specs = [
        ("alpha", 100, 1000.0),
        ("beta", 200, 2000.0),
        ("gamma", 300, 3000.0),
    ]
    setup_test_paths(dir_specs)

    result = await mcp_client.call_tool(
        "list_directories", arguments={"path": str(tmp_path), "order_by": order, "top_n": 2}
    )

    assert result.structured_content["total"] == 2


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
async def test_list_directories_nonexistent_path(tmp_path, mcp_client):
    nonexistent = tmp_path / "nonexistent"

    with pytest.raises(ToolError, match="Error running command: command failed with return code 1"):
        await mcp_client.call_tool("list_directories", arguments={"path": str(nonexistent)})


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
@pytest.mark.skipif(os.geteuid() == 0, reason="root can access restricted paths")
async def test_list_directories_restricted_path(restricted_path, mcp_client):
    with pytest.raises(ToolError) as exc_info:
        await mcp_client.call_tool("list_directories", arguments={"path": str(restricted_path)})

    assert "Error running command: command failed with return code 1" in str(exc_info.value)


async def test_list_directories_remote(mock_execute_with_fallback, mcp_client):
    mock_execute_with_fallback.return_value = (0, "alpha\nbeta\ngamma", "")

    result = await mcp_client.call_tool("list_directories", arguments={"path": "/remote/path", "host": "remote.host"})
    result_text = result.content[0].text

    assert "alpha" in result_text
    assert "beta" in result_text
    assert "gamma" in result_text

    mock_execute_with_fallback.assert_called_once()
    call_kwargs = mock_execute_with_fallback.call_args[1]
    assert call_kwargs["host"] == "remote.host"
