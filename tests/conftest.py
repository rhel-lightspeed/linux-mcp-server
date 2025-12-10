import socket

import pytest

from linux_mcp_server.audit import log_tool_call


# =============================================================================
# Shared test constants for IPv6 link-local filtering tests
# =============================================================================
LINK_LOCAL_IPV6 = "fe80::1%eth0"
GLOBAL_IPV6 = "2001:db8::1"
IPV4_ADDR = "192.168.1.100"

# Parameterized test cases for link-local address filtering (process tests)
# Format: (laddr_ip, raddr_ip, expectation)
# Each expectation is a string that will be eval'd with result, laddr_ip in scope
LINK_LOCAL_FILTER_CASES_PROCESS = [
    pytest.param(LINK_LOCAL_IPV6, IPV4_ADDR, '"Network Connections" not in result', id="laddr-link-local"),
    pytest.param(IPV4_ADDR, LINK_LOCAL_IPV6, '"Network Connections" not in result', id="raddr-link-local"),
    pytest.param(LINK_LOCAL_IPV6, LINK_LOCAL_IPV6, '"Network Connections" not in result', id="both-link-local"),
    pytest.param(IPV4_ADDR, GLOBAL_IPV6, '"Network Connections (1)" in result', id="no-link-local-header"),
    pytest.param(IPV4_ADDR, GLOBAL_IPV6, 'f"{laddr_ip}:8080" in result', id="no-link-local-addr"),
    pytest.param(GLOBAL_IPV6, IPV4_ADDR, '"Network Connections (1)" in result', id="global-ipv6-header"),
    pytest.param(GLOBAL_IPV6, IPV4_ADDR, 'f"{laddr_ip}:8080" in result', id="global-ipv6-addr"),
]

# Parameterized test cases for link-local address filtering (network tests)
# Format: (laddr_ip, raddr_ip, expectation)
# Each expectation is a string that will be eval'd with output in scope
LINK_LOCAL_FILTER_CASES_NETWORK = [
    pytest.param(LINK_LOCAL_IPV6, IPV4_ADDR, '"filtered 1 link-local" in output', id="laddr-link-local-filtered"),
    pytest.param(LINK_LOCAL_IPV6, IPV4_ADDR, '"Total connections: 0" in output', id="laddr-link-local-count"),
    pytest.param(IPV4_ADDR, LINK_LOCAL_IPV6, '"filtered 1 link-local" in output', id="raddr-link-local-filtered"),
    pytest.param(IPV4_ADDR, LINK_LOCAL_IPV6, '"Total connections: 0" in output', id="raddr-link-local-count"),
    pytest.param(LINK_LOCAL_IPV6, LINK_LOCAL_IPV6, '"filtered 1 link-local" in output', id="both-link-local-filtered"),
    pytest.param(LINK_LOCAL_IPV6, LINK_LOCAL_IPV6, '"Total connections: 0" in output', id="both-link-local-count"),
    pytest.param(IPV4_ADDR, GLOBAL_IPV6, '"filtered" not in output', id="no-link-local-not-filtered"),
    pytest.param(IPV4_ADDR, GLOBAL_IPV6, '"Total connections: 1" in output', id="no-link-local-count"),
    pytest.param(GLOBAL_IPV6, IPV4_ADDR, '"filtered" not in output', id="global-ipv6-not-filtered"),
    pytest.param(GLOBAL_IPV6, IPV4_ADDR, '"Total connections: 1" in output', id="global-ipv6-count"),
]


# =============================================================================
# Shared mock classes for network/connection testing
# =============================================================================
class MockAddr:
    """Mock address for network connections (ip:port)."""

    def __init__(self, ip: str, port: int):
        self.ip = ip
        self.port = port


class MockConnectionType:
    """Mock socket type with name attribute (for process connections)."""

    def __init__(self, name: str):
        self.name = name


class MockConnection:
    """Mock network connection - works for both network tools and process tools.

    For network tools: pass type_ as socket.SOCK_STREAM/SOCK_DGRAM
    For process tools: pass type_name as "SOCK_STREAM"/"SOCK_DGRAM"
    """

    def __init__(
        self,
        type_=None,
        type_name: str | None = None,
        laddr: MockAddr | None = None,
        raddr: MockAddr | None = None,
        status: str | None = "ESTABLISHED",
        pid: int | None = None,
    ):
        # Support both network-style (type_) and process-style (type_name)
        if type_name is not None:
            self.type = MockConnectionType(type_name)
        else:
            self.type = type_ if type_ is not None else socket.SOCK_STREAM
        self.laddr = laddr
        self.raddr = raddr
        self.status = status
        self.pid = pid


# =============================================================================
# Shared test data for mixed link-local filtering scenarios
# =============================================================================
def make_mixed_connections_network():
    """Create mixed connections for network tool tests (with pid)."""
    return [
        # Should be filtered (link-local laddr)
        MockConnection(
            type_=socket.SOCK_STREAM,
            laddr=MockAddr(LINK_LOCAL_IPV6, 8080),
            raddr=MockAddr(IPV4_ADDR, 54321),
            status="ESTABLISHED",
            pid=1234,
        ),
        # Should be shown (IPv4 -> global IPv6)
        MockConnection(
            type_=socket.SOCK_STREAM,
            laddr=MockAddr(IPV4_ADDR, 80),
            raddr=MockAddr(GLOBAL_IPV6, 12345),
            status="ESTABLISHED",
            pid=5678,
        ),
        # Should be filtered (link-local raddr)
        MockConnection(
            type_=socket.SOCK_DGRAM,
            laddr=MockAddr(IPV4_ADDR, 53),
            raddr=MockAddr(LINK_LOCAL_IPV6, 9999),
            status=None,
            pid=9999,
        ),
    ]


def make_mixed_listening_ports():
    """Create mixed listening ports for filtering tests (with pid)."""
    return [
        # Should be filtered (link-local)
        MockConnection(
            type_=socket.SOCK_STREAM,
            laddr=MockAddr(LINK_LOCAL_IPV6, 8080),
            raddr=None,
            status="LISTEN",
            pid=1234,
        ),
        # Should be shown (IPv4)
        MockConnection(
            type_=socket.SOCK_STREAM,
            laddr=MockAddr(IPV4_ADDR, 80),
            raddr=None,
            status="LISTEN",
            pid=5678,
        ),
        # Should be shown (global IPv6)
        MockConnection(
            type_=socket.SOCK_DGRAM,
            laddr=MockAddr(GLOBAL_IPV6, 53),
            raddr=None,
            status=None,
            pid=9999,
        ),
    ]


def make_mixed_connections_process():
    """Create mixed connections for process tool tests (with type_name)."""
    return [
        # Should be filtered (link-local laddr)
        MockConnection(
            type_name="SOCK_STREAM",
            laddr=MockAddr(LINK_LOCAL_IPV6, 8080),
            raddr=MockAddr(IPV4_ADDR, 54321),
            status="ESTABLISHED",
        ),
        # Should be shown
        MockConnection(
            type_name="SOCK_STREAM",
            laddr=MockAddr(IPV4_ADDR, 80),
            raddr=MockAddr(GLOBAL_IPV6, 12345),
            status="ESTABLISHED",
        ),
        # Should be filtered (link-local raddr)
        MockConnection(
            type_name="SOCK_DGRAM",
            laddr=MockAddr(IPV4_ADDR, 53),
            raddr=MockAddr(LINK_LOCAL_IPV6, 9999),
            status="NONE",
        ),
    ]


@pytest.fixture
def decorated():
    @log_tool_call
    def list_services(*args, **kwargs):
        return args, kwargs

    return list_services


@pytest.fixture
def adecorated():
    @log_tool_call
    async def list_services(*args, **kwargs):
        return args, kwargs

    return list_services


@pytest.fixture
async def decorated_fail():
    @log_tool_call
    def list_services(*args, **kwargs):
        raise ValueError("Raised intentionally")

    return list_services


@pytest.fixture
async def adecorated_fail():
    @log_tool_call
    async def list_services(*args, **kwargs):
        raise ValueError("Raised intentionally")

    return list_services
