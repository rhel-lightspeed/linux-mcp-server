import pytest

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
            "4096\t/path/alpha\n8192\t/path/beta\n2048\t/path/gamma",
            "size",
            3,
            "result[0].size == 4096 and result[0].name == 'alpha' and result[1].size == 8192 and result[1].name == 'beta'",
        ),
        (
            "1700000000.0\talpha\n1700100000.0\tbeta\n1700200000.0\tgamma",
            "modified",
            3,
            "result[0].modified == 1700000000.0 and result[0].name == 'alpha'",
        ),
    ],
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
            "1700000000.0\tfile1.txt\n1700100000.0\tfile2.txt",
            "modified",
            2,
            "result[0].modified == 1700000000.0 and result[0].name == 'file1.txt'",
        ),
    ],
)
def test_parse_file_listing(stdout, order_by, expected_count, expected):
    result = parse_file_listing(stdout, order_by)

    assert len(result) == expected_count
    assert eval(expected)
