import textwrap

from linux_mcp_server.parsers import parse_ip_brief


def test_parse_ip_brief_empty():
    """Test parsing empty output."""
    result = parse_ip_brief("")

    assert result == {}


def test_parse_ip_brief():
    """Test parsing ip -brief address output."""
    stdout = """lo               UNKNOWN        127.0.0.1/8 ::1/128
        eth0             UP             192.168.1.100/24 fe80::1/64
    """
    result = parse_ip_brief(textwrap.dedent(stdout))
    lo = result["lo"]
    eth0 = result["eth0"]

    assert "lo" in result
    assert "eth0" in result
    assert lo.status == "UNKNOWN"
    assert "127.0.0.1/8" in lo.addresses
    assert eth0.status == "UP"
    assert "192.168.1.100/24" in eth0.addresses
