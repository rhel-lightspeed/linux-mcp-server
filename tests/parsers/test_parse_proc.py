import textwrap

from linux_mcp_server.parsers import parse_proc_net_dev
from linux_mcp_server.parsers import parse_proc_status


def test_parse_proc_net_dev_empty():
    """Test parsing empty output."""
    result = parse_proc_net_dev("")

    assert result == {}


def test_parse_proc_net_dev():
    """Test parsing /proc/net/dev content."""
    stdout = """Inter-|   Receive                                                |  Transmit
        face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
            lo: 1234567   12345    0    0    0     0          0         0  1234567   12345    0    0    0     0       0          0
        eth0: 9876543   98765   10    5    0     0          0       100  5432100   54321   20   10    0     0       0          0
    """
    result = parse_proc_net_dev(textwrap.dedent(stdout))
    lo = result["lo"]
    eth0 = result["eth0"]

    assert "lo" in result
    assert "eth0" in result
    assert lo.rx_bytes == 1234567
    assert lo.rx_packets == 12345
    assert eth0.rx_bytes == 9876543
    assert eth0.rx_errors == 10
    assert eth0.tx_bytes == 5432100


def test_parse_proc_status_empty():
    """Test parsing empty output."""
    result = parse_proc_status("")

    assert result == {}


def test_parse_proc_status():
    """Test parsing /proc/{pid}/status content."""
    stdout = """Name:	bash
        State:	S (sleeping)
        Tgid:	1234
        Pid:	1234
        PPid:	1000
        Threads:	1
        VmPeak:	    12000 kB
        VmSize:	    10000 kB
        VmRSS:	     5000 kB
        SigPnd:	0000000000000000
    """
    result = parse_proc_status(textwrap.dedent(stdout))

    assert result["Name"] == "bash"
    assert result["State"] == "S (sleeping)"
    assert result["Pid"] == "1234"
    assert result["PPid"] == "1000"
    assert result["Threads"] == "1"
    assert result["VmRSS"] == "5000 kB"
    assert "SigPnd" not in result
