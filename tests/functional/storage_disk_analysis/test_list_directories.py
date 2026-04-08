# Copyright Contributors to the linux-mcp-server project
# SPDX-License-Identifier: Apache-2.0
import json
import os
import tempfile

from utils.shell import shell


async def test_list_directories_happy_path(mcp_session):
    """
    Verify that the server lists directories under a given path.
    Uses /tmp as a common directory that should exist on all systems.
    """
    shell("echo 'test' > /tmp/test.txt", silent=True)
    response = await mcp_session.call_tool("list_directories", arguments={"path": "/tmp"})
    assert response is not None

    response_text = response.content[0].text
    assert response_text is not None

    data = json.loads(response_text)
    assert "nodes" in data

    actual_content = shell("find /tmp/ -maxdepth 1 -mindepth 1 -type d", silent=True).stdout.strip()
    actual_content = actual_content.replace("/tmp/", "").split("\n")

    node_names = {n["name"] for n in data["nodes"]}
    for item in actual_content:
        if item:
            assert item in node_names

    assert "test.txt" not in node_names


async def test_list_directories_order_by_name(mcp_session):
    """
    Verify that directories can be listed and ordered by name.
    """
    # Create a temporary directory structure for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create subdirectories
        os.makedirs(os.path.join(tmpdir, "alpha_dir"))
        os.makedirs(os.path.join(tmpdir, "beta_dir"))
        os.makedirs(os.path.join(tmpdir, "gamma_dir"))

        # 1. Verify that the directories are listed in ascending order
        response = await mcp_session.call_tool(
            "list_directories",
            arguments={"path": tmpdir, "order_by": "name", "sort": "ascending"},
        )
        assert response is not None

        data = json.loads(response.content[0].text.strip())
        node_names = [n["name"] for n in data["nodes"]]

        assert node_names == ["alpha_dir", "beta_dir", "gamma_dir"]
        assert data.get("total") == 3

        # 2. Verify that the directories are listed in descending order
        response = await mcp_session.call_tool(
            "list_directories",
            arguments={"path": tmpdir, "order_by": "name", "sort": "descending"},
        )
        assert response is not None

        data = json.loads(response.content[0].text.strip())
        node_names = [n["name"] for n in data["nodes"]]

        assert node_names == ["gamma_dir", "beta_dir", "alpha_dir"]
        assert data.get("total") == 3


async def test_list_directories_order_by_size(mcp_session):
    """
    Verify that directories can be listed and ordered by size.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create subdirectories with different sizes
        small_dir = os.path.join(tmpdir, "small_dir")
        large_dir = os.path.join(tmpdir, "large_dir")
        os.makedirs(small_dir)
        os.makedirs(large_dir)

        # Add some content to make sizes different
        with open(os.path.join(large_dir, "bigfile.txt"), "w") as f:
            f.write("x" * 10000)

        # 1. Verify that the directories are listed in descending order by size
        response = await mcp_session.call_tool(
            "list_directories",
            arguments={"path": tmpdir, "order_by": "size", "sort": "descending"},
        )
        assert response is not None

        data = json.loads(response.content[0].text)
        node_names = [n["name"] for n in data["nodes"]]

        large_dir_pos = node_names.index("large_dir")
        small_dir_pos = node_names.index("small_dir")

        assert large_dir_pos < small_dir_pos
        assert data.get("total") == 2

        # 2. Verify that the directories are listed in ascending order by size
        response = await mcp_session.call_tool(
            "list_directories",
            arguments={"path": tmpdir, "order_by": "size", "sort": "ascending"},
        )
        assert response is not None

        data = json.loads(response.content[0].text)
        node_names = [n["name"] for n in data["nodes"]]

        large_dir_pos = node_names.index("large_dir")
        small_dir_pos = node_names.index("small_dir")

        assert small_dir_pos < large_dir_pos
        assert data.get("total") == 2


async def test_list_directories_with_top_n(mcp_session):
    """
    Verify that the top_n parameter limits the number of results.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create multiple subdirectories
        for i in range(5):
            os.makedirs(os.path.join(tmpdir, f"dir_{i}"))

        response = await mcp_session.call_tool(
            "list_directories",
            arguments={"path": tmpdir, "order_by": "name", "top_n": 2},
        )
        assert response is not None

        data = json.loads(response.content[0].text)
        node_names = [n["name"] for n in data["nodes"]]

        # Count occurrences - should be limited to 2
        dir_count = sum(1 for i in range(5) if f"dir_{i}" in node_names)
        assert dir_count <= 2, f"Expected at most 2 directories, got {dir_count}"


async def test_list_directories_non_existing_path(mcp_session):
    """
    Verify the response contains error when path does not exist.
    """
    non_existing_path = "/nonexistent/path/xyz123"
    response = await mcp_session.call_tool("list_directories", arguments={"path": non_existing_path})
    assert response is not None

    response_text = response.content[0].text
    # Should indicate path doesn't exist or cannot be resolved
    assert "No such file or directory" in response_text


async def test_list_directories_empty_argument(mcp_session):
    """
    Verify the response contains validation error when called without path.
    """
    response = await mcp_session.call_tool("list_directories", arguments={})
    assert response is not None
    assert "1 validation error for call[list_directories]" in response.content[0].text
    assert "Missing required argument" in response.content[0].text
