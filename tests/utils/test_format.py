import pytest

from linux_mcp_server.utils.format import format_bytes


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        (512, "512.0B"),
        (1024, "1.0KB"),
        (2048, "2.0KB"),
        (1536, "1.5KB"),
        (1_073_741_824, "1.0GB"),
        (201_073_741_824, "187.3GB"),
        (5_201_073_741_824, "4.7TB"),
        (10_105_201_073_741_824, "9.0PB"),
    ),
)
def test_format_bytes(value, expected):
    result = format_bytes(value)

    assert result == expected
