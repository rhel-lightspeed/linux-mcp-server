import sys

import pytest

from fastmcp.exceptions import ToolError


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
async def test_list_files(setup_test_paths, mcp_client, tmp_path):
    file_specs = [
        ("file1.txt", 100, 1000.0),
        ("file2.txt", 200, 2000.0),
        ("file3.txt", 300, 3000.0),
    ]
    setup_test_paths(file_specs)

    result = await mcp_client.call_tool("list_files", arguments={"path": str(tmp_path), "order_by": "name"})
    content = result.structured_content
    names = [item["name"] for item in content["nodes"]]

    assert names == [item[0] for item in file_specs]


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
async def test_list_files_by_name(setup_test_paths, mcp_client, tmp_path):
    file_specs = [
        ("gamma.txt", 300, 3000.0),
        ("alpha.txt", 100, 1000.0),
        ("beta.txt", 200, 2000.0),
    ]
    setup_test_paths(file_specs)

    result = await mcp_client.call_tool("list_files", arguments={"path": str(tmp_path), "order_by": "name"})
    content = result.structured_content
    positions = {item["name"]: id for id, item in enumerate(content["nodes"])}

    alpha_pos = positions["alpha.txt"]
    beta_pos = positions["beta.txt"]
    gamma_pos = positions["gamma.txt"]
    assert alpha_pos < beta_pos < gamma_pos


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
async def test_list_files_by_size(setup_test_paths, mcp_client, tmp_path):
    file_specs = [
        ("small.txt", 100, 1000.0),
        ("large.txt", 300, 3000.0),
        ("medium.txt", 200, 2000.0),
    ]
    setup_test_paths(file_specs)
    result = await mcp_client.call_tool("list_files", arguments={"path": str(tmp_path), "order_by": "size"})
    content = result.structured_content
    names = [item["name"] for item in content["nodes"]]

    assert names == ["small.txt", "medium.txt", "large.txt"]


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
async def test_list_files_descending(setup_test_paths, mcp_client, tmp_path):
    file_specs = [
        ("alpha.txt", 100, 1000.0),
        ("beta.txt", 200, 2000.0),
        ("gamma.txt", 300, 3000.0),
    ]
    setup_test_paths(file_specs)
    result = await mcp_client.call_tool("list_files", arguments={"path": str(tmp_path), "sort": "descending"})
    content = result.structured_content
    positions = {dir["name"]: id for id, dir in enumerate(content["nodes"])}

    gamma_pos = positions["gamma.txt"]
    beta_pos = positions["beta.txt"]
    alpha_pos = positions["alpha.txt"]
    assert gamma_pos < beta_pos < alpha_pos


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
@pytest.mark.parametrize("order", ("size", "modified", "name"))
async def test_list_files_with_top_n(setup_test_paths, mcp_client, order, tmp_path):
    file_specs = [
        ("file1.txt", 100, 1000.0),
        ("file2.txt", 200, 2000.0),
        ("file3.txt", 300, 3000.0),
    ]
    setup_test_paths(file_specs)
    result = await mcp_client.call_tool("list_files", arguments={"path": str(tmp_path), "order_by": order, "top_n": 2})
    content = result.structured_content

    assert content["total"] == 2


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
async def test_list_files_nonexistent_path(tmp_path, mcp_client):
    nonexistent = tmp_path / "nonexistent"

    with pytest.raises(ToolError) as exc_info:
        await mcp_client.call_tool("list_files", arguments={"path": str(nonexistent)})

    assert "Error running command: command failed with return code 1" in str(exc_info.value)


async def test_list_files_remote(mock_execute_with_fallback, mcp_client):
    mock_execute_with_fallback.return_value = (0, "file1.txt\nfile2.txt\nfile3.txt", "")

    result = await mcp_client.call_tool("list_files", arguments={"path": "/remote/path", "host": "remote.host"})
    content = result.structured_content
    names = [item["name"] for item in content["nodes"]]

    assert names == [f"file{n}.txt" for n in range(1, 4)]

    mock_execute_with_fallback.assert_called_once()
    call_kwargs = mock_execute_with_fallback.call_args[1]
    assert call_kwargs["host"] == "remote.host"
