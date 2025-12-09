import pytest

from linux_mcp_server.utils.format import format_bytes
from linux_mcp_server.utils.format import is_ipv6_link_local


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


@pytest.mark.parametrize(
    ("address", "expected"),
    (
        # Link-local addresses - fe80::/10 covers fe80:: through febf::
        ("fe80::1", True),
        ("fe80::1%eth0", True),  # With scope identifier
        ("fe80::abcd:1234%enp0s3", True),
        ("FE80::1", True),  # Uppercase
        ("fe80::", True),
        ("fe81::1", True),  # fe8x range
        ("fe8f::1", True),
        ("fe90::1", True),  # fe9x range
        ("fe9f::1", True),
        ("fea0::1", True),  # feax range
        ("feaf::1", True),
        ("feb0::1", True),  # febx range
        ("febf::1", True),  # Last in range
        ("fe80::1:2:3:4", True),  # Full link-local address
        ("fe80:0000:0000:0000:0000:0000:0000:0001", True),  # Expanded form
        ("febf:ffff:ffff:ffff:ffff:ffff:ffff:ffff", True),  # Upper boundary
        # Non-link-local addresses (should return False)
        ("fec0::1", False),  # Site-local (just outside range)
        ("ff00::1", False),  # Multicast
        ("::1", False),  # Loopback
        ("2001:db8::1", False),  # Documentation range
        ("2001:0db8:85a3:0000:0000:8a2e:0370:7334", False),
        ("", False),  # Empty string
        # IPv4 addresses (should return False)
        ("192.168.1.1", False),
        ("127.0.0.1", False),
        ("169.254.1.1", False),  # IPv4 link-local (different from IPv6)
        # Malformed inputs (should return False gracefully)
        ("fe80::xyz", False),  # Invalid hex characters
        ("fe80:::1", False),  # Malformed triple colon
        ("not-an-ip", False),  # Completely invalid
        ("fe80::1::2", False),  # Multiple :: compressions
        ("fe80:ghij::1", False),  # Invalid hex in middle
    ),
)
def test_is_ipv6_link_local(address, expected):
    result = is_ipv6_link_local(address)

    assert result == expected
