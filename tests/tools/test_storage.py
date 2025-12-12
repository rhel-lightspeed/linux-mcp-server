"""Tests for storage tools."""

import base64
import json
import os
import sys

from collections.abc import Callable
from pathlib import Path
from typing import Literal
from unittest.mock import AsyncMock

import pytest

from mcp.server.fastmcp.exceptions import ToolError

from linux_mcp_server.server import mcp
from linux_mcp_server.tools.storage import NodeEntry


NodeType = Literal["directory", "file"]


@pytest.fixture
def setup_test_nodes(tmp_path) -> Callable[[list[tuple[str, int, float]], NodeType], tuple[Path, list[NodeEntry]]]:
    """
    Factory fixture for creating test directories or files with specific sizes and modification times.

    Returns a function that accepts a list of (name, size, modified_time) tuples and a node_type, and:
    - Creates directories or files with the specified sizes
    - Sets their modification times
    - Returns the directory path and list of expected NodeEntry objects
    """

    def _create_nodes(
        node_specs: list[tuple[str, int, float]],
        node_type: NodeType = "directory",
    ) -> tuple[Path, list[NodeEntry]]:
        """Create directories or files with specified attributes."""
        expected_entries = []

        for name, size, modified_time in node_specs:
            if node_type == "directory":
                node_path = tmp_path / name
                node_path.mkdir()
                # Create a file inside the directory to give it size
                if size > 0:
                    content_file = node_path / "content.txt"
                    content_file.write_text("x" * size)
            else:
                node_path = tmp_path / name
                node_path.touch()
                if size > 0:
                    node_path.write_text("x" * size)

            os.utime(node_path, (modified_time, modified_time))
            expected_entries.append(NodeEntry(name=name, size=size, modified=modified_time))

        return tmp_path, expected_entries

    return _create_nodes


@pytest.fixture
def restricted_path(tmp_path):
    restricted = tmp_path / "restricted"
    restricted.mkdir()
    restricted.chmod(0o000)

    yield restricted

    restricted.chmod(0o755)


def parse_node_result(result) -> list[NodeEntry]:
    """Parse tool result into list of NodeEntry objects."""
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[1], dict)
    return [NodeEntry(**entry) for entry in result[1]["result"]]


class TestListBlockDevices:
    @pytest.mark.parametrize(
        ("devices", "host"),
        [
            pytest.param(
                {
                    "sda": {"model": "SAMSUNG SSD", "size": "1.00 TB", "partitions": {"sda1": {"size": "512.00 GB"}}},
                    "nvme0n1": {"model": "Samsung NVMe", "size": "500.00 GB", "partitions": {}},
                },
                None,
                id="multiple_devices_local",
            ),
            pytest.param({}, None, id="no_devices"),
            pytest.param(
                {"vda": {"model": "Virtio", "size": "20.00 GB", "partitions": {}}},
                "remote.server.com",
                id="remote_host",
            ),
        ],
    )
    async def test_list_block_devices(self, mocker, devices, host):
        """Test list_block_devices returns JSON device info."""
        mock_execute_ansible = AsyncMock(return_value={"ansible_facts": {"ansible_devices": devices}})
        mocker.patch("linux_mcp_server.tools.storage.execute_ansible_module", mock_execute_ansible)

        params = {"host": host} if host else {}
        result = await mcp.call_tool("list_block_devices", params)

        assert isinstance(result, tuple)
        assert isinstance(result[0], list)
        output = json.loads(result[0][0].text)  # pyright: ignore[reportIndexIssue]
        assert output == devices

        call_kwargs = mock_execute_ansible.call_args[1]
        assert call_kwargs["module"] == "setup"
        assert call_kwargs["host"] == host


# Common test data for directories and files
ALPHA_BETA_GAMMA_SPECS = [
    ("alpha", 100, 1000.0),
    ("beta", 200, 2000.0),
    ("gamma", 300, 3000.0),
]

SIZE_ORDERED_SPECS = [
    ("small", 100, 1000.0),
    ("large", 300, 3000.0),
    ("medium", 200, 2000.0),
]

TIME_ORDERED_SPECS = [
    ("newest", 100, 3000.0),
    ("oldest", 100, 1000.0),
    ("middle", 100, 2000.0),
]


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
class TestListDirectories:
    async def test_list_directories_returns_structured_output(self, setup_test_nodes):
        """Test that list_directories returns structured output."""
        test_path, _ = setup_test_nodes(ALPHA_BETA_GAMMA_SPECS, "directory")

        result = await mcp.call_tool("list_directories", {"path": str(test_path), "order_by": "name"})

        got = parse_node_result(result)
        assert got is not None

    @pytest.mark.parametrize(
        ("order_by", "sort", "specs", "expected"),
        [
            pytest.param(
                "name",
                "ascending",
                ALPHA_BETA_GAMMA_SPECS,
                [
                    NodeEntry(name="alpha", size=0, modified=0.0),
                    NodeEntry(name="beta", size=0, modified=0.0),
                    NodeEntry(name="gamma", size=0, modified=0.0),
                ],
                id="name_ascending",
            ),
            pytest.param(
                "name",
                "descending",
                ALPHA_BETA_GAMMA_SPECS,
                [
                    NodeEntry(name="gamma", size=0, modified=0.0),
                    NodeEntry(name="beta", size=0, modified=0.0),
                    NodeEntry(name="alpha", size=0, modified=0.0),
                ],
                id="name_descending",
            ),
            pytest.param(
                "modified",
                "ascending",
                TIME_ORDERED_SPECS,
                [
                    NodeEntry(name="oldest", size=0, modified=1000.0),
                    NodeEntry(name="middle", size=0, modified=2000.0),
                    NodeEntry(name="newest", size=0, modified=3000.0),
                ],
                id="modified_ascending",
            ),
            pytest.param(
                "modified",
                "descending",
                TIME_ORDERED_SPECS,
                [
                    NodeEntry(name="newest", size=0, modified=3000.0),
                    NodeEntry(name="middle", size=0, modified=2000.0),
                    NodeEntry(name="oldest", size=0, modified=1000.0),
                ],
                id="modified_descending",
            ),
        ],
    )
    async def test_list_directories_ordering(self, setup_test_nodes, order_by, sort, specs, expected):
        """Test list_directories with various orderings and sort directions."""
        test_path, _ = setup_test_nodes(specs, "directory")

        result = await mcp.call_tool("list_directories", {"path": str(test_path), "order_by": order_by, "sort": sort})

        got = parse_node_result(result)
        assert got == expected

    @pytest.mark.parametrize("sort", ["ascending", "descending"])
    async def test_list_directories_by_size(self, setup_test_nodes, sort):
        """Test list_directories sorted by size returns all directories.

        Note: Ansible's find module returns directory inode size, not contents size.
        All directories have similar inode sizes, so we just verify all are returned.
        """
        test_path, _ = setup_test_nodes(SIZE_ORDERED_SPECS, "directory")

        result = await mcp.call_tool("list_directories", {"path": str(test_path), "order_by": "size", "sort": sort})

        got = parse_node_result(result)
        names = {entry.name for entry in got}
        assert names == {"small", "medium", "large"}

    @pytest.mark.parametrize(
        ("order_by", "specs", "top_n", "expected_names"),
        [
            pytest.param("name", ALPHA_BETA_GAMMA_SPECS, 2, ["alpha", "beta"], id="name_top_2"),
            pytest.param(
                "modified",
                TIME_ORDERED_SPECS,
                2,
                ["oldest", "middle"],
                id="modified_top_2",
            ),
        ],
    )
    async def test_list_directories_with_top_n(self, setup_test_nodes, order_by, specs, top_n, expected_names):
        """Test list_directories with top_n limit."""
        test_path, _ = setup_test_nodes(specs, "directory")

        result = await mcp.call_tool(
            "list_directories", {"path": str(test_path), "order_by": order_by, "sort": "ascending", "top_n": top_n}
        )

        got = parse_node_result(result)
        assert [entry.name for entry in got] == expected_names

    async def test_list_directories_by_size_with_top_n_descending(self, setup_test_nodes):
        """Test list_directories with size ordering, top_n limit, and descending order."""
        specs = [("small", 100, 1000.0), ("large", 300, 3000.0), ("medium", 200, 2000.0), ("tiny", 50, 500.0)]
        test_path, _ = setup_test_nodes(specs, "directory")

        result = await mcp.call_tool(
            "list_directories", {"path": str(test_path), "order_by": "size", "sort": "descending", "top_n": 2}
        )

        got = parse_node_result(result)
        assert len(got) == 2

    @pytest.mark.parametrize("order_by", ["name", "size", "modified"])
    async def test_list_directories_empty_directory(self, tmp_path, order_by):
        """Test list_directories with a directory containing no subdirectories."""
        result = await mcp.call_tool("list_directories", {"path": str(tmp_path), "order_by": order_by})

        got = parse_node_result(result)
        assert got == []

    @pytest.mark.parametrize(
        ("param", "value", "error_match"),
        [
            pytest.param("order_by", "invalid", "1 validation error", id="invalid_order_by"),
            pytest.param("sort", "invalid", "1 validation error", id="invalid_sort"),
        ],
    )
    async def test_list_directories_invalid_params(self, tmp_path, param, value, error_match):
        """Test that invalid parameters raise ValueError."""
        params = {"path": str(tmp_path), param: value}
        with pytest.raises(ToolError, match=error_match):
            await mcp.call_tool("list_directories", params)

    async def test_list_directories_invalid_path(self, tmp_path):
        """Test with non-existent path returns empty results via Ansible."""
        non_existent_path = tmp_path / "non_existent_directory"
        result = await mcp.call_tool("list_directories", {"path": str(non_existent_path), "order_by": "name"})

        got = parse_node_result(result)
        assert got == []

    async def test_list_directories_handles_permission_denied(self, restricted_path):
        """Test handling of permission denied returns empty results via Ansible."""
        result = await mcp.call_tool("list_directories", {"path": str(restricted_path)})

        got = parse_node_result(result)
        assert got == []

    async def test_list_directories_special_characters_in_names(self, tmp_path):
        """Test list_directories handles directory names with special characters."""
        special_names = ["dir with spaces", "dir-with-dashes", "dir_with_underscores"]
        for name in special_names:
            (tmp_path / name).mkdir()

        result = await mcp.call_tool("list_directories", {"path": str(tmp_path), "order_by": "name"})

        got = parse_node_result(result)
        names = [entry.name for entry in got]
        for expected in special_names:
            assert expected in names
        assert len(got) == 3

    @pytest.mark.parametrize(
        ("order_by", "files", "expected"),
        [
            pytest.param(
                "size",
                [
                    {"path": "/remote/path/small", "size": 100, "mtime": 1000.0},
                    {"path": "/remote/path/large", "size": 300, "mtime": 3000.0},
                    {"path": "/remote/path/medium", "size": 200, "mtime": 2000.0},
                ],
                [
                    NodeEntry(name="small", size=100, modified=0.0),
                    NodeEntry(name="medium", size=200, modified=0.0),
                    NodeEntry(name="large", size=300, modified=0.0),
                ],
                id="size_ordering",
            ),
            pytest.param(
                "name",
                [
                    {"path": "/remote/path/gamma", "size": 300, "mtime": 3000.0},
                    {"path": "/remote/path/alpha", "size": 100, "mtime": 1000.0},
                    {"path": "/remote/path/beta", "size": 200, "mtime": 2000.0},
                ],
                [
                    NodeEntry(name="alpha", size=0, modified=0.0),
                    NodeEntry(name="beta", size=0, modified=0.0),
                    NodeEntry(name="gamma", size=0, modified=0.0),
                ],
                id="name_ordering",
            ),
            pytest.param(
                "modified",
                [
                    {"path": "/remote/path/newest", "size": 100, "mtime": 3000.0},
                    {"path": "/remote/path/oldest", "size": 100, "mtime": 1000.0},
                    {"path": "/remote/path/middle", "size": 100, "mtime": 2000.0},
                ],
                [
                    NodeEntry(name="oldest", size=0, modified=1000.0),
                    NodeEntry(name="middle", size=0, modified=2000.0),
                    NodeEntry(name="newest", size=0, modified=3000.0),
                ],
                id="modified_ordering",
            ),
        ],
    )
    async def test_list_directories_ansible_execution(self, mocker, order_by, files, expected):
        """Test list_directories with Ansible execution for various orderings."""
        mock_ansible = AsyncMock(return_value={"files": files})
        mocker.patch("linux_mcp_server.tools.storage.execute_ansible_module", mock_ansible)

        result = await mcp.call_tool(
            "list_directories",
            {"path": "/remote/path", "order_by": order_by, "host": "remote.server.com"},
        )

        got = parse_node_result(result)
        assert got == expected

        call_kwargs = mock_ansible.call_args[1]
        assert call_kwargs["module"] == "find"
        assert call_kwargs["module_args"]["file_type"] == "directory"
        assert call_kwargs["host"] == "remote.server.com"

    async def test_list_directories_ansible_descending(self, mocker):
        """Test list_directories with Ansible and descending sort."""
        files = [
            {"path": "/remote/path/small", "size": 100, "mtime": 1000.0},
            {"path": "/remote/path/large", "size": 300, "mtime": 3000.0},
            {"path": "/remote/path/medium", "size": 200, "mtime": 2000.0},
        ]
        mock_ansible = AsyncMock(return_value={"files": files})
        mocker.patch("linux_mcp_server.tools.storage.execute_ansible_module", mock_ansible)

        result = await mcp.call_tool(
            "list_directories",
            {"path": "/remote/path", "order_by": "size", "sort": "descending", "host": "remote.server.com"},
        )

        got = parse_node_result(result)
        assert [e.name for e in got] == ["large", "medium", "small"]
        assert got[0].size == 300

    async def test_list_directories_ansible_with_top_n(self, mocker):
        """Test list_directories with Ansible and top_n limit."""
        files = [
            {"path": "/remote/path/small", "size": 100, "mtime": 1000.0},
            {"path": "/remote/path/large", "size": 300, "mtime": 3000.0},
            {"path": "/remote/path/medium", "size": 200, "mtime": 2000.0},
        ]
        mock_ansible = AsyncMock(return_value={"files": files})
        mocker.patch("linux_mcp_server.tools.storage.execute_ansible_module", mock_ansible)

        result = await mcp.call_tool(
            "list_directories",
            {"path": "/remote/path", "order_by": "size", "top_n": 2, "host": "remote.server.com"},
        )

        got = parse_node_result(result)
        assert len(got) == 2
        assert [e.name for e in got] == ["small", "medium"]

    async def test_list_directories_ansible_empty_results(self, mocker):
        """Test list_directories with Ansible returns empty list for no matches."""
        mock_ansible = AsyncMock(return_value={"files": []})
        mocker.patch("linux_mcp_server.tools.storage.execute_ansible_module", mock_ansible)

        result = await mcp.call_tool(
            "list_directories",
            {"path": "/remote/empty", "order_by": "name", "host": "remote.server.com"},
        )

        got = parse_node_result(result)
        assert got == []

    async def test_list_directories_ansible_missing_optional_fields(self, mocker):
        """Test list_directories handles missing optional fields from Ansible."""
        # Ansible find may return entries without size or mtime
        files = [
            {"path": "/remote/path/no_size"},  # Missing size and mtime
            {"path": "/remote/path/no_mtime", "size": 100},  # Missing mtime
        ]
        mock_ansible = AsyncMock(return_value={"files": files})
        mocker.patch("linux_mcp_server.tools.storage.execute_ansible_module", mock_ansible)

        # Test size ordering with missing size
        result = await mcp.call_tool(
            "list_directories",
            {"path": "/remote/path", "order_by": "size", "host": "remote.server.com"},
        )
        got = parse_node_result(result)
        assert len(got) == 2
        assert got[0].size == 0  # Default value
        assert got[1].size == 100

        # Test modified ordering with missing mtime
        result = await mcp.call_tool(
            "list_directories",
            {"path": "/remote/path", "order_by": "modified", "host": "remote.server.com"},
        )
        got = parse_node_result(result)
        assert len(got) == 2
        assert got[0].modified == 0.0  # Default value
        assert got[1].modified == 0.0  # Also missing mtime


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
class TestListFiles:
    async def test_list_files_returns_structured_output(self, setup_test_nodes):
        """Test that list_files returns structured output."""
        test_path, _ = setup_test_nodes(ALPHA_BETA_GAMMA_SPECS, "file")

        result = await mcp.call_tool("list_files", {"path": str(test_path), "order_by": "name"})

        got = parse_node_result(result)
        assert got is not None

    @pytest.mark.parametrize(
        ("order_by", "sort", "specs", "expected"),
        [
            pytest.param(
                "name",
                "ascending",
                ALPHA_BETA_GAMMA_SPECS,
                [
                    NodeEntry(name="alpha", size=0, modified=0.0),
                    NodeEntry(name="beta", size=0, modified=0.0),
                    NodeEntry(name="gamma", size=0, modified=0.0),
                ],
                id="name_ascending",
            ),
            pytest.param(
                "name",
                "descending",
                ALPHA_BETA_GAMMA_SPECS,
                [
                    NodeEntry(name="gamma", size=0, modified=0.0),
                    NodeEntry(name="beta", size=0, modified=0.0),
                    NodeEntry(name="alpha", size=0, modified=0.0),
                ],
                id="name_descending",
            ),
            pytest.param(
                "size",
                "ascending",
                SIZE_ORDERED_SPECS,
                [
                    NodeEntry(name="small", size=100, modified=0.0),
                    NodeEntry(name="medium", size=200, modified=0.0),
                    NodeEntry(name="large", size=300, modified=0.0),
                ],
                id="size_ascending",
            ),
            pytest.param(
                "size",
                "descending",
                SIZE_ORDERED_SPECS,
                [
                    NodeEntry(name="large", size=300, modified=0.0),
                    NodeEntry(name="medium", size=200, modified=0.0),
                    NodeEntry(name="small", size=100, modified=0.0),
                ],
                id="size_descending",
            ),
            pytest.param(
                "modified",
                "ascending",
                TIME_ORDERED_SPECS,
                [
                    NodeEntry(name="oldest", size=0, modified=1000.0),
                    NodeEntry(name="middle", size=0, modified=2000.0),
                    NodeEntry(name="newest", size=0, modified=3000.0),
                ],
                id="modified_ascending",
            ),
            pytest.param(
                "modified",
                "descending",
                TIME_ORDERED_SPECS,
                [
                    NodeEntry(name="newest", size=0, modified=3000.0),
                    NodeEntry(name="middle", size=0, modified=2000.0),
                    NodeEntry(name="oldest", size=0, modified=1000.0),
                ],
                id="modified_descending",
            ),
        ],
    )
    async def test_list_files_ordering(self, setup_test_nodes, order_by, sort, specs, expected):
        """Test list_files with various orderings and sort directions."""
        test_path, _ = setup_test_nodes(specs, "file")

        result = await mcp.call_tool("list_files", {"path": str(test_path), "order_by": order_by, "sort": sort})

        got = parse_node_result(result)
        assert got == expected

    @pytest.mark.parametrize(
        ("order_by", "specs", "top_n", "expected_names"),
        [
            pytest.param("name", ALPHA_BETA_GAMMA_SPECS, 2, ["alpha", "beta"], id="name_top_2"),
            pytest.param("modified", TIME_ORDERED_SPECS, 2, ["oldest", "middle"], id="modified_top_2"),
        ],
    )
    async def test_list_files_with_top_n(self, setup_test_nodes, order_by, specs, top_n, expected_names):
        """Test list_files with top_n limit."""
        test_path, _ = setup_test_nodes(specs, "file")

        result = await mcp.call_tool(
            "list_files", {"path": str(test_path), "order_by": order_by, "sort": "ascending", "top_n": top_n}
        )

        got = parse_node_result(result)
        assert [entry.name for entry in got] == expected_names

    async def test_list_files_by_size_with_top_n_descending(self, setup_test_nodes):
        """Test list_files with size ordering, top_n limit, and descending order."""
        specs = [("small", 100, 1000.0), ("large", 300, 3000.0), ("medium", 200, 2000.0), ("tiny", 50, 500.0)]
        test_path, _ = setup_test_nodes(specs, "file")

        expected = [
            NodeEntry(name="large", size=300, modified=0.0),
            NodeEntry(name="medium", size=200, modified=0.0),
        ]

        result = await mcp.call_tool(
            "list_files", {"path": str(test_path), "order_by": "size", "sort": "descending", "top_n": 2}
        )

        got = parse_node_result(result)
        assert got == expected

    @pytest.mark.parametrize("order_by", ["name", "size", "modified"])
    async def test_list_files_empty_directory(self, tmp_path, order_by):
        """Test list_files with a directory containing no files."""
        result = await mcp.call_tool("list_files", {"path": str(tmp_path), "order_by": order_by})

        got = parse_node_result(result)
        assert got == []

    @pytest.mark.parametrize(
        ("param", "value", "error_match"),
        [
            pytest.param("order_by", "invalid", "1 validation error", id="invalid_order_by"),
            pytest.param("sort", "invalid", "1 validation error", id="invalid_sort"),
        ],
    )
    async def test_list_files_invalid_params(self, tmp_path, param, value, error_match):
        """Test that invalid parameters raise ValueError."""
        params = {"path": str(tmp_path), param: value}
        with pytest.raises(ToolError, match=error_match):
            await mcp.call_tool("list_files", params)

    async def test_list_files_invalid_path(self, tmp_path):
        """Test with non-existent path returns empty results via Ansible."""
        non_existent_path = tmp_path / "non_existent_directory"
        result = await mcp.call_tool("list_files", {"path": str(non_existent_path), "order_by": "name"})

        got = parse_node_result(result)
        assert got == []

    async def test_list_files_handles_permission_denied(self, restricted_path):
        """Test handling of permission denied returns empty results via Ansible."""
        result = await mcp.call_tool("list_files", {"path": str(restricted_path)})

        got = parse_node_result(result)
        assert got == []

    async def test_list_files_special_characters_in_names(self, tmp_path):
        """Test list_files handles file names with special characters."""
        special_names = [
            "file with spaces",
            "file-with-dashes",
            "file_with_underscores",
            "file_with_@@$!($)@",
            "file_with_📁.txt",
            "file_with_✨.md",
            "file_with_question?.txt",
            "file_with_angle<test>.log",
            "file_with_pipe|symbol.txt",
            "file_with_colon:check.md",
        ]
        for name in special_names:
            (tmp_path / name).touch()

        result = await mcp.call_tool("list_files", {"path": str(tmp_path), "order_by": "name"})

        got = parse_node_result(result)
        names = [entry.name for entry in got]
        for expected in special_names:
            assert expected in names
        assert len(got) == 10

    @pytest.mark.parametrize(
        ("order_by", "files", "expected"),
        [
            pytest.param(
                "size",
                [
                    {"path": "/remote/path/small.txt", "size": 100, "mtime": 1000.0},
                    {"path": "/remote/path/large.txt", "size": 300, "mtime": 3000.0},
                    {"path": "/remote/path/medium.txt", "size": 200, "mtime": 2000.0},
                ],
                [
                    NodeEntry(name="small.txt", size=100, modified=0.0),
                    NodeEntry(name="medium.txt", size=200, modified=0.0),
                    NodeEntry(name="large.txt", size=300, modified=0.0),
                ],
                id="size_ordering",
            ),
            pytest.param(
                "name",
                [
                    {"path": "/remote/path/gamma.txt", "size": 300, "mtime": 3000.0},
                    {"path": "/remote/path/alpha.txt", "size": 100, "mtime": 1000.0},
                    {"path": "/remote/path/beta.txt", "size": 200, "mtime": 2000.0},
                ],
                [
                    NodeEntry(name="alpha.txt", size=0, modified=0.0),
                    NodeEntry(name="beta.txt", size=0, modified=0.0),
                    NodeEntry(name="gamma.txt", size=0, modified=0.0),
                ],
                id="name_ordering",
            ),
            pytest.param(
                "modified",
                [
                    {"path": "/remote/path/newest.txt", "size": 100, "mtime": 3000.0},
                    {"path": "/remote/path/oldest.txt", "size": 100, "mtime": 1000.0},
                    {"path": "/remote/path/middle.txt", "size": 100, "mtime": 2000.0},
                ],
                [
                    NodeEntry(name="oldest.txt", size=0, modified=1000.0),
                    NodeEntry(name="middle.txt", size=0, modified=2000.0),
                    NodeEntry(name="newest.txt", size=0, modified=3000.0),
                ],
                id="modified_ordering",
            ),
        ],
    )
    async def test_list_files_ansible_execution(self, mocker, order_by, files, expected):
        """Test list_files with Ansible execution for various orderings."""
        mock_ansible = AsyncMock(return_value={"files": files})
        mocker.patch("linux_mcp_server.tools.storage.execute_ansible_module", mock_ansible)

        result = await mcp.call_tool(
            "list_files",
            {"path": "/remote/path", "order_by": order_by, "host": "remote.server.com"},
        )

        got = parse_node_result(result)
        assert got == expected

        call_kwargs = mock_ansible.call_args[1]
        assert call_kwargs["module"] == "find"
        assert call_kwargs["module_args"]["file_type"] == "file"
        assert call_kwargs["host"] == "remote.server.com"

    async def test_list_files_ansible_descending(self, mocker):
        """Test list_files with Ansible and descending sort."""
        files = [
            {"path": "/remote/path/small.txt", "size": 100, "mtime": 1000.0},
            {"path": "/remote/path/large.txt", "size": 300, "mtime": 3000.0},
            {"path": "/remote/path/medium.txt", "size": 200, "mtime": 2000.0},
        ]
        mock_ansible = AsyncMock(return_value={"files": files})
        mocker.patch("linux_mcp_server.tools.storage.execute_ansible_module", mock_ansible)

        result = await mcp.call_tool(
            "list_files",
            {"path": "/remote/path", "order_by": "size", "sort": "descending", "host": "remote.server.com"},
        )

        got = parse_node_result(result)
        assert [e.name for e in got] == ["large.txt", "medium.txt", "small.txt"]
        assert got[0].size == 300

    async def test_list_files_ansible_with_top_n(self, mocker):
        """Test list_files with Ansible and top_n limit."""
        files = [
            {"path": "/remote/path/small.txt", "size": 100, "mtime": 1000.0},
            {"path": "/remote/path/large.txt", "size": 300, "mtime": 3000.0},
            {"path": "/remote/path/medium.txt", "size": 200, "mtime": 2000.0},
        ]
        mock_ansible = AsyncMock(return_value={"files": files})
        mocker.patch("linux_mcp_server.tools.storage.execute_ansible_module", mock_ansible)

        result = await mcp.call_tool(
            "list_files",
            {"path": "/remote/path", "order_by": "size", "top_n": 2, "host": "remote.server.com"},
        )

        got = parse_node_result(result)
        assert len(got) == 2
        assert [e.name for e in got] == ["small.txt", "medium.txt"]

    async def test_list_files_ansible_empty_results(self, mocker):
        """Test list_files with Ansible returns empty list for no matches."""
        mock_ansible = AsyncMock(return_value={"files": []})
        mocker.patch("linux_mcp_server.tools.storage.execute_ansible_module", mock_ansible)

        result = await mcp.call_tool(
            "list_files",
            {"path": "/remote/empty", "order_by": "name", "host": "remote.server.com"},
        )

        got = parse_node_result(result)
        assert got == []


class TestReadFile:
    @pytest.mark.parametrize(
        ("content", "description"),
        [
            pytest.param("Hello, World!\nThis is a test file.\nLine 3.", "normal text", id="normal"),
            pytest.param("", "empty file", id="empty"),
            pytest.param(
                "Line with\ttabs\nLine with 'quotes'\nLine with \"double quotes\"\n$pecial ch@rs: !@#$%",
                "special characters",
                id="special_chars",
            ),
            pytest.param("Hello 世界\nBonjour 🌍\n한글", "unicode content", id="unicode"),
            pytest.param("\n".join([f"Line {i}" for i in range(1000)]), "large file", id="large"),
        ],
    )
    async def test_read_file_content(self, tmp_path, content, description):
        """Test read_file with various content types."""
        test_file = tmp_path / "test.txt"
        test_file.write_text(content)

        result = await mcp.call_tool("read_file", {"path": str(test_file)})

        assert isinstance(result, tuple)
        assert len(result) == 2
        output = result[0][0].text  # pyright: ignore[reportIndexIssue]
        assert output == content

    @pytest.mark.parametrize(
        ("setup_fn", "error_match"),
        [
            pytest.param(lambda p: p / "nonexistent.txt", "Error executing tool read_file", id="nonexistent"),
            pytest.param(lambda p: p, "Error executing tool read_file", id="directory_not_file"),
        ],
    )
    async def test_read_file_errors(self, tmp_path, setup_fn, error_match):
        """Test read_file error cases."""
        path = setup_fn(tmp_path)
        with pytest.raises(ToolError, match=error_match):
            await mcp.call_tool("read_file", {"path": str(path)})

    async def test_read_file_permission_denied(self, tmp_path):
        """Test read_file with a file that has no read permissions raises ToolError."""
        restricted_file = tmp_path / "restricted.txt"
        restricted_file.write_text("secret content")
        restricted_file.chmod(0o000)

        try:
            with pytest.raises(ToolError, match="Error executing tool read_file"):
                await mcp.call_tool("read_file", {"path": str(restricted_file)})
        finally:
            restricted_file.chmod(0o644)

    async def test_read_file_with_symlink(self, tmp_path):
        """Test read_file follows symlinks correctly."""
        real_file = tmp_path / "real.txt"
        test_content = "Real content"
        real_file.write_text(test_content)

        symlink_file = tmp_path / "link.txt"
        symlink_file.symlink_to(real_file)

        result = await mcp.call_tool("read_file", {"path": str(symlink_file)})

        assert isinstance(result, tuple)
        output = result[0][0].text  # pyright: ignore[reportIndexIssue]
        assert output == test_content

    @pytest.mark.parametrize(
        ("content", "description"),
        [
            pytest.param("Remote file content\nLine 2\nLine 3", "normal text", id="normal"),
            pytest.param("", "empty file", id="empty"),
            pytest.param("Hello 世界\nBonjour 🌍\n한글", "unicode content", id="unicode"),
        ],
    )
    async def test_read_file_ansible_execution(self, mocker, content, description):
        """Test read_file with Ansible slurp module."""
        content_b64 = base64.b64encode(content.encode()).decode()
        mock_ansible = AsyncMock(return_value={"content": content_b64})
        mocker.patch("linux_mcp_server.tools.storage.execute_ansible_module", mock_ansible)

        result = await mcp.call_tool("read_file", {"path": "/remote/path/file.txt", "host": "remote.server.com"})

        assert isinstance(result, tuple)
        output = result[0][0].text  # pyright: ignore[reportIndexIssue]
        assert output == content

        call_kwargs = mock_ansible.call_args[1]
        assert call_kwargs["module"] == "slurp"
        assert call_kwargs["module_args"]["src"] == "/remote/path/file.txt"
        assert call_kwargs["host"] == "remote.server.com"

    @pytest.mark.parametrize(
        ("content_b64", "error_match"),
        [
            pytest.param("invalid!!!base64", "Failed to decode file content", id="invalid_base64"),
            pytest.param(
                base64.b64encode(b"\xff\xfe\xfd").decode(),
                "Failed to decode file content",
                id="binary_decode_error",
            ),
        ],
    )
    async def test_read_file_ansible_decode_errors(self, mocker, content_b64, error_match):
        """Test read_file handles decode errors from Ansible."""
        mock_ansible = AsyncMock(return_value={"content": content_b64})
        mocker.patch("linux_mcp_server.tools.storage.execute_ansible_module", mock_ansible)

        with pytest.raises(ToolError, match=error_match):
            await mcp.call_tool("read_file", {"path": "/remote/file.txt", "host": "remote.server.com"})
