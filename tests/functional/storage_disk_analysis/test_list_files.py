# Copyright Red Hat
import json


async def _call_list_files(mcp_session, **kwargs):
    """Helper to call list_files, assert basic validity, and parse JSON if possible."""
    response = await mcp_session.call_tool("list_files", arguments=kwargs)
    assert response is not None

    text = response.content[0].text
    assert text is not None

    try:
        data = json.loads(text.strip())
        node_names = [n["name"] for n in data.get("nodes", [])]
        assert data.get("total") == len(node_names)
        return text, data, node_names
    except json.JSONDecodeError:
        return text, None, []


async def test_list_files_happy_path(mcp_session, tmp_path):
    """
    Verify that the server lists files under a given path.
    Uses tmp_path as a common directory that should exist.
    """
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test")

    _, data, node_names = await _call_list_files(mcp_session, path=str(tmp_path))
    assert data is not None
    assert "nodes" in data

    assert node_names == ["test_file.txt"]


async def test_list_files_order_by_name(mcp_session, tmp_path):
    """
    Verify that files can be listed and ordered by name.
    """
    # Create files
    (tmp_path / "alpha_file.txt").touch()
    (tmp_path / "beta_file.txt").touch()
    (tmp_path / "gamma_file.txt").touch()

    # 1. Verify that the files are listed in ascending order
    _, data, node_names = await _call_list_files(
        mcp_session, path=str(tmp_path), order_by="name", sort="ascending"
    )
    assert node_names == ["alpha_file.txt", "beta_file.txt", "gamma_file.txt"]
    assert data.get("total") == 3

    # 2. Verify that the files are listed in descending order
    _, data, node_names = await _call_list_files(
        mcp_session, path=str(tmp_path), order_by="name", sort="descending"
    )
    assert node_names == ["gamma_file.txt", "beta_file.txt", "alpha_file.txt"]
    assert data.get("total") == 3


async def test_list_files_order_by_size(mcp_session, tmp_path):
    """
    Verify that files can be listed and ordered by size.
    """
    small_file = tmp_path / "small_file.txt"
    large_file = tmp_path / "large_file.txt"

    small_file.write_text("x")
    large_file.write_text("x" * 10000)

    # 1. Verify that the files are listed in descending order by size
    _, data, node_names = await _call_list_files(
        mcp_session, path=str(tmp_path), order_by="size", sort="descending"
    )
    assert node_names == ["large_file.txt", "small_file.txt"]
    assert data.get("total") == 2

    # 2. Verify that the files are listed in ascending order by size
    _, data, node_names = await _call_list_files(
        mcp_session, path=str(tmp_path), order_by="size", sort="ascending"
    )
    assert node_names == ["small_file.txt", "large_file.txt"]
    assert data.get("total") == 2


async def test_list_files_with_top_n(mcp_session, tmp_path):
    """
    Verify that the top_n parameter limits the number of results.
    """
    for i in range(5):
        (tmp_path / f"file_{i}.txt").touch()

    _, _, node_names = await _call_list_files(
        mcp_session, path=str(tmp_path), order_by="name", top_n=2
    )

    assert len(node_names) == 2


async def test_list_files_non_existing_path(mcp_session):
    """
    Verify the response contains error when path does not exist.
    """
    text, _, _ = await _call_list_files(mcp_session, path="/nonexistent/path/xyz123")
    assert "No such file or directory" in text


async def test_list_files_empty_argument(mcp_session):
    """
    Verify the response contains validation error when called without path.
    """
    text, _, _ = await _call_list_files(mcp_session)
    assert "path" in text
    assert "Missing required argument" in text
