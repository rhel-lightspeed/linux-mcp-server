from collections.abc import Callable

import pytest

from linux_mcp_server.models import NodeEntry
from linux_mcp_server.parsers import parse_directory_listing
from linux_mcp_server.parsers import parse_file_listing


@pytest.mark.parametrize(
    "stdout, order_by, expected_count, expected",
    [
        (
            "",
            "name",
            0,
            "result == []",
        ),
        (
            """4096\t/path/alpha
            8192\t/path/beta
            2048\t/path/gamma
            12448\t/path/""",
            "size",
            3,
            "result[0].size == 4096 and result[0].name == 'alpha' and result[1].size == 8192 and result[1].name == 'beta'",
        ),
        (
            """4096\t/path/subdir/alpha
            8192\t/path/subdir/beta
            2048\t/path/subdir/gamma
            12448\t/path/subdir/""",
            "size",
            3,
            "result[0].size == 4096 and result[0].name == 'alpha' and result[1].size == 8192 and result[1].name == 'beta'",
        ),
        (
            "1700000000.0:+0000\talpha\n1700100000.0:+0000\tbeta\n1700200000.0:+0000\tgamma",
            "modified",
            3,
            "result[0].modified.timestamp() == 1700000000.0 and result[0].name == 'alpha'",
        ),
    ],
    ids=["name", "size", "size_subdirs", "modified"],
)
def test_parse_directory_listing(stdout, order_by, expected_count, expected):
    result = parse_directory_listing(stdout, order_by)

    assert len(result) == expected_count
    assert eval(expected)


@pytest.mark.parametrize(
    "stdout, order_by, expected_count, expected",
    [
        (
            "",
            "name",
            0,
            "result == []",
        ),
        (
            "file1.txt\nfile2.txt\nfile3.txt",
            "name",
            3,
            "[e.name for e in result] == ['file1.txt', 'file2.txt', 'file3.txt']",
        ),
        (
            "1024\tfile1.txt\n2048\tfile2.txt\n512\tfile3.txt",
            "size",
            3,
            "result[0].size == 1024 and result[0].name == 'file1.txt'",
        ),
        (
            "1700000000.0:+0000\tfile1.txt\n1700100000.0:+0000\tfile2.txt",
            "modified",
            2,
            "result[0].modified.timestamp() == 1700000000.0 and result[0].name == 'file1.txt'",
        ),
    ],
)
def test_parse_file_listing(stdout, order_by, expected_count, expected):
    result = parse_file_listing(stdout, order_by)

    assert len(result) == expected_count
    assert eval(expected)


@pytest.mark.parametrize("parser", [parse_directory_listing, parse_file_listing])
@pytest.mark.parametrize("value", ["invalid", "0:", "0:+2500", "nope:+0000", "nan:+0000", "inf:+0000", "1e30:+0000"])
def test_invalid_modified(parser: Callable[[str, str], list[NodeEntry]], value: str) -> None:
    assert parser(f"{value}\tbad\n0:+0000\tvalid", "modified")[0].name == "valid"
    assert len(parser(f"{value}\tbad", "modified")) == 0
