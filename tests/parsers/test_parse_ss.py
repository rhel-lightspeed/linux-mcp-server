import textwrap

import pytest

from linux_mcp_server.parsers import parse_ss_connections
from linux_mcp_server.parsers import parse_ss_listening


@pytest.mark.parametrize(
    "stdout",
    [
        "",
        "Netid  State      Recv-Q Send-Q Local Address:Port               Peer Address:Port",
    ],
)
def test_parse_ss_connections_empty_or_header_only(stdout):
    result = parse_ss_connections(stdout)

    assert result == []


@pytest.mark.parametrize(
    "stdout, protocol, state, local_address, local_port",
    [
        (
            """Netid  State      Recv-Q Send-Q Local Address:Port               Peer Address:Port
               tcp    ESTAB      0      0      192.168.1.100:22                 192.168.1.1:54321
            """,
            "TCP",
            "ESTAB",
            "192.168.1.100",
            "22",
        ),
        (
            """Netid  State      Recv-Q Send-Q Local Address:Port               Peer Address:Port
               udp    UNCONN     0      0      0.0.0.0:68                       0.0.0.0:*
            """,
            "UDP",
            "UNCONN",
            "0.0.0.0",
            "68",
        ),
    ],
)
def test_parse_ss_connections_connection(stdout, protocol, state, local_address, local_port):
    result = parse_ss_connections(textwrap.dedent(stdout))
    conn = result[0]

    assert len(result) == 1
    assert conn.protocol == protocol
    assert conn.state == state
    assert conn.local_address == local_address
    assert conn.local_port == local_port


def test_parse_ss_listening_empty_output():
    """Test parsing empty output."""
    result = parse_ss_listening("")

    assert result == []


def test_parse_ss_listening_listening_port():
    """Test parsing a listening port."""
    stdout = """Netid  State      Recv-Q Send-Q Local Address:Port               Peer Address:Port
        tcp    LISTEN     0      128    0.0.0.0:22                       0.0.0.0:*
    """
    result = parse_ss_listening(textwrap.dedent(stdout))
    port = result[0]

    assert len(result) == 1
    assert port.protocol == "TCP"
    assert port.local_address == "0.0.0.0"
    assert port.local_port == "22"
